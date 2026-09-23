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
    python publisher.py --publish-now "texte" --visibility CONNECTIONS
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import linkedin
import repo

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
            # Pas de valeur par défaut : l'omission est une erreur, pas un
            # consentement à publier en public.
            if post.get("visibility") not in ("PUBLIC", "CONNECTIONS"):
                raise ValueError(f"visibility absente ou invalide : {post.get('visibility')!r}")
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
        repo.sync(f"Mise de côté de {len(errors)} fichier(s) de queue invalide(s)", sign=False)

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
        repo.sync(f"Péremption de {len(stale)} post(s) non publié(s)", sign=False)

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
            repo.sync(f"Publication en cours : {path.name}", sign=False)

        try:
            post["post_id"] = linkedin.publish(post["text"], post["visibility"])
        except Exception as exc:
            # On s'arrête au premier échec : les posts suivants restent dans queue/.
            print(f"::error::{path.name} laissé dans publishing/, arbitrage manuel : {exc}")
            return 1

        post["published_at"] = datetime.now(timezone.utc).isoformat()
        (PUBLISHED / path.name).write_text(json.dumps(post, indent=2, ensure_ascii=False) + "\n")
        locked.unlink()
        if commit:
            repo.sync(f"Publié : {path.name}", sign=False)
        print(f"Publié : {path.name} -> {post['post_id']}")

    if not due:
        print("Aucun post dû.")
    return 1 if (errors or stale) else 0


def publish_now(text, visibility):
    """Publie immédiatement et journalise. Retourne un compte rendu, jamais une exception
    après une publication réussie.

    Le journal n'est pas un confort : un post publié sans trace est un post
    qu'on ne sait plus supprimer. Le 14/09/2026, un post de test est resté une
    semaine en ligne faute d'avoir noté son identifiant.

    Point délicat : une fois LinkedIn appelé, le post existe. Si le commit ou
    le push échoue ensuite, remonter une exception nue ferait croire que rien
    n'est parti — et la relance publierait en double. On rend donc toujours le
    post_id, avec `pushed` à faux et ce qu'il reste à faire. C'est NF5 au
    niveau de l'appelant.
    """
    post_id = linkedin.publish(text, visibility)

    # À partir d'ici le post existe. TOUT ce qui suit est protégé : une
    # exception qui s'échapperait ferait croire que rien n'est parti, et la
    # relance publierait en double. Y compris le calcul du chemin, qui a l'air
    # inoffensif — c'est justement celui qui a levé en test.
    resultat = {"post_id": post_id, "pushed": False,
                "delete_command": f".venv/bin/python linkedin.py --delete {post_id}"}
    try:
        now = datetime.now(timezone.utc)
        path = PUBLISHED / f"manuel-{now:%Y-%m-%dT%H%M%S}.json"
        path.write_text(json.dumps({
            "text": text, "visibility": visibility, "post_id": post_id,
            "published_at": now.isoformat(), "source": "publish_now",
        }, indent=2, ensure_ascii=False) + "\n")
        resultat["journal"] = str(path)
        repo.sync(f"Publié (manuel) : {post_id}", sign=True)
        resultat["pushed"] = True
        resultat["message"] = f"Publié et journalisé : {post_id}"
    except Exception as exc:
        resultat["warning"] = (
            f"PUBLIÉ, post_id={post_id} — mais le journal n'est pas poussé : {exc}. "
            "Le post EST en ligne : ne relance pas, tu publierais en double. "
            f"Pousse le journal à la main, ou supprime le post avec : {resultat['delete_command']}"
        )
        resultat["message"] = f"Publié ({post_id}), journal non poussé"
    return resultat


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

    if "--publish-now" in sys.argv:
        args = sys.argv[sys.argv.index("--publish-now") + 1:]
        # La visibilité est exigée explicitement : c'est l'omission qui a
        # causé l'incident du 14/09/2026, pas une erreur de frappe.
        if len(args) != 3 or args[1] != "--visibility":
            print('Usage: python publisher.py --publish-now "<texte>" '
                  "--visibility PUBLIC|CONNECTIONS")
            sys.exit(2)
        r = publish_now(args[0], args[2])
        print(r["message"])
        print(f"Journal : {r.get('journal', 'NON ECRIT')}")
        print(f"Pour supprimer : {r['delete_command']}")
        if r.get("warning"):
            print(f"::error::{r['warning']}")
        sys.exit(0 if r["pushed"] else 1)

    sys.exit(publish_due(commit="--commit" in sys.argv))
