"""
Publie les posts dont l'heure est venue. Exécuté par GitHub Actions.

Cycle d'un fichier : queue/ -> publishing/ -> published/ (voir ARCHITECTURE.md).

Le cron GitHub étant très imprécis, l'horloge est ici, pas dans le cron : un
run qui démarre en avance attend l'heure exacte du post, dans la limite de
WAIT_WINDOW. Au-delà de STALE_AFTER, le post est périmé et n'est plus publié.

Usage:
    python publisher.py              # local : déplace les fichiers, sans git
    python publisher.py --commit     # CI : chaque étape est poussée avant la suivante
    python publisher.py --days-left  # jours restants avant expiration du token
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import linkedin

ROOT = Path(__file__).parent
QUEUE = ROOT / "queue"
PUBLISHING = ROOT / "publishing"
PUBLISHED = ROOT / "published"
STALE = ROOT / "stale"

# Attente maximale d'un run pour un post à venir. Bornée à 20 minutes, soit
# bien moins que l'intervalle réel entre deux runs (2 h à 5 h 30 mesurées) :
# deux runs ne peuvent donc pas convoiter le même post, et la concurrence
# reste théorique plutôt que subie.
WAIT_WINDOW = timedelta(minutes=20)

# Au-delà, le post a raté sa fenêtre. Le publier des heures plus tard serait
# pire que ne pas le publier : le contexte visé (une heure de forte audience,
# une actualité) n'existe plus. Décision rendue à l'humain.
STALE_AFTER = timedelta(hours=3)


def git_sync(message):
    """Commite et pousse l'état des trois dossiers. Lève une exception en cas d'échec.

    En CI, un déplacement non poussé n'existe pas : le run suivant repart du
    dépôt distant et verrait encore le fichier dans queue/. Le verrou réel est
    donc le push qui précède l'appel API, pas le déplacement local.
    """
    subprocess.run(["git", "add", "-A", "queue", "publishing", "published", "stale"], check=True)
    # --no-gpg-sign : ni le runner GitHub ni le bot n'ont de clé, et une config
    # locale commit.gpgsign=true ferait échouer la publication.
    subprocess.run(["git", "commit", "-q", "--no-gpg-sign", "-m", message], check=True)
    if subprocess.run(["git", "push", "-q"]).returncode != 0:
        # Quelqu'un a poussé entre-temps (nouveau post programmé, annulation).
        # Si le rebase entre en conflit sur ce fichier, on s'arrête : pas de publication.
        subprocess.run(["git", "pull", "-q", "--rebase"], check=True)
        subprocess.run(["git", "push", "-q"], check=True)


def load_due(now):
    """Trie la queue sans rien déplacer. Retourne (dus, périmés, invalides).

    « Dus » inclut les posts à venir dans les WAIT_WINDOW minutes : c'est le run
    qui attendra l'heure exacte, faute de pouvoir compter sur le cron.
    """
    due, stale, errors = [], [], []
    for path in sorted(QUEUE.glob("*.json")):
        try:
            post = json.loads(path.read_text())
            scheduled = datetime.fromisoformat(post["scheduled_at"])
            if scheduled.tzinfo is None:
                raise ValueError("scheduled_at sans fuseau horaire")
            if not post.get("text", "").strip():
                raise ValueError("text vide")
            if post.get("visibility", "PUBLIC") not in ("PUBLIC", "CONNECTIONS"):
                raise ValueError(f"visibility invalide : {post['visibility']}")
        except (ValueError, KeyError, TypeError) as exc:
            errors.append((path, f"{path.name} : {exc}"))
            continue

        if scheduled < now - STALE_AFTER:
            stale.append((path, scheduled))
        elif scheduled <= now + WAIT_WINDOW:
            due.append((path, post, scheduled))
    return due, stale, errors


def publish_due(commit):
    now = datetime.now(timezone.utc)
    due, stale, errors = load_due(now)

    # Un fichier illisible est mis de côté dans publishing/ plutôt que laissé
    # dans queue/ : sinon il ferait échouer le workflow à chaque run, et
    # l'alerte se noierait dans son propre bruit. Il échoue une fois, fort.
    for path, error in errors:
        print(f"::error::Fichier de queue invalide, mis de côté dans publishing/ : {error}")
        path.rename(PUBLISHING / path.name)
    if errors and commit:
        git_sync(f"Mise de côté de {len(errors)} fichier(s) de queue invalide(s)")

    # Périmés : sortis de la queue pour qu'ils ne soient plus jamais candidats,
    # mais jamais publiés. Republier à contretemps est un dégât public.
    for path, scheduled in stale:
        late = now - scheduled
        print(
            f"::error::{path.name} périmé : dû depuis {late.total_seconds() / 3600:.1f} h "
            f"(> {STALE_AFTER.total_seconds() / 3600:.0f} h), déplacé dans stale/, non publié"
        )
        path.rename(STALE / path.name)
    if stale and commit:
        git_sync(f"Péremption de {len(stale)} post(s) non publié(s)")

    if due:
        # Token expiré ou révoqué : on échoue ici, avant d'avoir verrouillé un fichier.
        linkedin.me()

    for path, post, scheduled in sorted(due, key=lambda item: item[2]):
        # Attente avant le verrou, jamais après : un run interrompu pendant
        # l'attente laisse le fichier dans queue/, prêt pour le run suivant.
        delay = (scheduled - datetime.now(timezone.utc)).total_seconds()
        if delay > 0:
            print(f"Attente de {delay / 60:.1f} min avant {path.name} ({scheduled:%H:%M %Z})")
            time.sleep(delay)

        locked = PUBLISHING / path.name
        path.rename(locked)
        if commit:
            git_sync(f"Publication en cours : {path.name}")

        try:
            post["post_id"] = linkedin.publish(post["text"], post.get("visibility", "PUBLIC"))
        except Exception as exc:
            # On s'arrête au premier échec : les posts suivants restent dans queue/.
            print(f"::error::{path.name} laissé dans publishing/, arbitrage manuel : {exc}")
            return 1

        post["published_at"] = datetime.now(timezone.utc).isoformat()
        (PUBLISHED / path.name).write_text(json.dumps(post, indent=2, ensure_ascii=False) + "\n")
        locked.unlink()
        if commit:
            git_sync(f"Publié : {path.name}")
        print(f"Publié : {path.name} -> {post['post_id']}")

    if not due:
        print("Aucun post dû.")
    return 1 if (errors or stale) else 0


def days_left():
    """Jours avant expiration du token, lus dans token_expiry.json.

    Ce fichier ne contient que la date, pas le token : il est versionné, donc
    le workflow peut alerter sans secret supplémentaire. auth.py le réécrit à
    chaque authentification.
    """
    expiry = ROOT / "token_expiry.json"
    if not expiry.exists():
        raise RuntimeError("token_expiry.json absent : relancer python auth.py")
    raw = json.loads(expiry.read_text())["expires_at"]
    return (datetime.fromisoformat(raw) - datetime.now(timezone.utc)).days


if __name__ == "__main__":
    if "--days-left" in sys.argv:
        print(days_left())
        sys.exit(0)
    sys.exit(publish_due(commit="--commit" in sys.argv))
