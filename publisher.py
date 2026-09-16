"""
Publie les posts dont l'heure est passée. Exécuté par GitHub Actions.

Cycle d'un fichier : queue/ -> publishing/ -> published/ (voir ARCHITECTURE.md).

Usage:
    python publisher.py              # local : déplace les fichiers, sans git
    python publisher.py --commit     # CI : chaque étape est poussée avant la suivante
    python publisher.py --days-left  # jours restants avant expiration du token
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import linkedin

ROOT = Path(__file__).parent
QUEUE = ROOT / "queue"
PUBLISHING = ROOT / "publishing"
PUBLISHED = ROOT / "published"


def git_sync(message):
    """Commite et pousse l'état des trois dossiers. Lève une exception en cas d'échec.

    En CI, un déplacement non poussé n'existe pas : le run suivant repart du
    dépôt distant et verrait encore le fichier dans queue/. Le verrou réel est
    donc le push qui précède l'appel API, pas le déplacement local.
    """
    subprocess.run(["git", "add", "-A", "queue", "publishing", "published"], check=True)
    # --no-gpg-sign : ni le runner GitHub ni le bot n'ont de clé, et une config
    # locale commit.gpgsign=true ferait échouer la publication.
    subprocess.run(["git", "commit", "-q", "--no-gpg-sign", "-m", message], check=True)
    if subprocess.run(["git", "push", "-q"]).returncode != 0:
        # Quelqu'un a poussé entre-temps (nouveau post programmé, annulation).
        # Si le rebase entre en conflit sur ce fichier, on s'arrête : pas de publication.
        subprocess.run(["git", "pull", "-q", "--rebase"], check=True)
        subprocess.run(["git", "push", "-q"], check=True)


def load_due(now):
    """Retourne (posts dus, fichiers invalides) sans rien déplacer."""
    due, errors = [], []
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
        if scheduled <= now:
            due.append((path, post))
    return due, errors


def publish_due(commit):
    due, errors = load_due(datetime.now(timezone.utc))

    # Un fichier illisible est mis de côté dans publishing/ plutôt que laissé
    # dans queue/ : sinon il ferait échouer le workflow toutes les 15 minutes,
    # et l'alerte se noierait dans son propre bruit. Il échoue une fois, fort.
    for path, error in errors:
        print(f"::error::Fichier de queue invalide, mis de côté dans publishing/ : {error}")
        path.rename(PUBLISHING / path.name)
    if errors and commit:
        git_sync(f"Mise de côté de {len(errors)} fichier(s) de queue invalide(s)")

    if due:
        # Token expiré ou révoqué : on échoue ici, avant d'avoir verrouillé un fichier.
        linkedin.me()

    for path, post in due:
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
    return 1 if errors else 0


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
