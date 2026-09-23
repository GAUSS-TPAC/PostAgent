"""
Opérations sur la file de publication : programmer, lister, annuler.

Séparé de publisher.py, qui est le programme exécuté par la CI. Ici vivent les
gestes que l'humain déclenche par la conversation. Les deux partagent repo.py
et les mêmes dossiers, mais pas le même moment ni le même acteur.

Chaque fonction commence par un `repo.pull()` : la CI commite dans ce dépôt à
chaque publication, donc un clone local non rafraîchi ment sur l'état de la file.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import repo

ROOT = Path(__file__).parent
QUEUE = ROOT / "queue"
PUBLISHING = ROOT / "publishing"
PUBLISHED = ROOT / "published"
STALE = ROOT / "stale"

VISIBILITES = ("PUBLIC", "CONNECTIONS")


def _resume(path, champs=("scheduled_at", "visibility", "post_id", "published_at")):
    """Lit un fichier de file et n'en garde que de quoi décider. Jamais le texte entier."""
    try:
        post = json.loads(path.read_text())
    except ValueError as exc:
        return {"file": path.name, "erreur": f"illisible : {exc}"}
    resume = {"file": path.name}
    texte = post.get("text", "")
    resume["extrait"] = texte[:80] + ("…" if len(texte) > 80 else "")
    for champ in champs:
        if champ in post:
            resume[champ] = post[champ]
    return resume


def schedule_post(text, scheduled_at, visibility):
    """Écrit un post dans la file, le commite et le pousse. Retourne un compte rendu.

    Le push fait partie de l'opération, il n'en est pas la suite : un fichier
    écrit et non poussé n'existe pour personne. Le 22/09/2026, un post préparé
    ainsi n'est jamais parti et rien ne l'a signalé.
    """
    if not text or not text.strip():
        raise ValueError("Texte de post vide")
    if visibility not in VISIBILITES:
        raise ValueError(f"visibility doit valoir {' ou '.join(VISIBILITES)}, reçu : {visibility!r}")

    try:
        quand = datetime.fromisoformat(scheduled_at)
    except ValueError:
        raise ValueError(
            f"scheduled_at illisible : {scheduled_at!r}. Format attendu : 2026-09-24T09:00:00+01:00"
        ) from None
    if quand.tzinfo is None:
        raise ValueError(
            f"scheduled_at sans fuseau horaire : {scheduled_at!r}. "
            "Ajoute le décalage, par exemple +01:00 — sans lui, l'heure de publication est ambiguë."
        )
    if quand <= datetime.now(timezone.utc):
        raise ValueError(f"scheduled_at est dans le passé : {quand.isoformat()}")

    repo.pull()
    cible = QUEUE / f"{quand.astimezone():%Y-%m-%dT%H%M}.json"
    if cible.exists():
        raise ValueError(f"{cible.name} existe déjà : un post est déjà programmé à cette minute")

    cible.write_text(json.dumps({
        "text": text,
        "scheduled_at": quand.isoformat(),
        "visibility": visibility,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2, ensure_ascii=False) + "\n")
    repo.sync(f"Programme : {cible.name}", sign=True)
    return {"file": cible.name, "scheduled_at": quand.isoformat(),
            "visibility": visibility, "pushed": True}


def list_queue():
    """État complet de la file. Retourne les quatre dossiers, pas seulement queue/.

    `publishing/` et `stale/` sont les deux états qui réclament un arbitrage
    humain : les masquer reviendrait à cacher les pannes.
    """
    repo.pull()
    published = sorted(PUBLISHED.glob("*.json"))[-5:]
    return {
        "queue": [_resume(p) for p in sorted(QUEUE.glob("*.json"))],
        "publishing": [_resume(p) for p in sorted(PUBLISHING.glob("*.json"))],
        "stale": [_resume(p) for p in sorted(STALE.glob("*.json"))],
        "published_recent": [_resume(p) for p in published],
    }


def cancel_post(filename):
    """Retire un post programmé de la file. Retourne un compte rendu.

    Le fichier est supprimé, pas archivé : git est déjà l'archive, c'est la
    raison d'être d'une file versionnée. `git show` retrouve le contenu.

    Un fichier déjà passé dans publishing/ n'est plus annulable : il est
    verrouillé, voire déjà publié. On refuse plutôt que de laisser croire à
    une annulation qui n'annule rien.
    """
    repo.pull()
    cible = QUEUE / filename
    if not cible.exists():
        if (PUBLISHING / filename).exists():
            raise RuntimeError(
                f"{filename} est déjà en cours de publication, trop tard pour annuler. "
                "Vérifie le profil avant toute action."
            )
        if (PUBLISHED / filename).exists():
            raise RuntimeError(f"{filename} est déjà publié, l'annulation n'a plus de sens.")
        raise FileNotFoundError(f"{filename} est introuvable dans queue/")

    cible.unlink()
    repo.sync(f"Annulation : {filename}", sign=True)
    return {"cancelled": filename, "pushed": True}
