"""
Opérations git sur la file versionnée.

Séparé de publisher.py pour deux raisons : le serveur MCP en a besoin sans
vouloir la logique de publication, et chaque module doit rester lisible d'une
traite (NF7).

Toute commande est bornée dans le temps : un agent qui attend un prompt
invisible (identifiants, phrase de passe) est pire qu'un agent qui échoue.
"""

import subprocess

LOCAL_TIMEOUT = 30    # add, commit : local
NETWORK_TIMEOUT = 180  # pull, push : connexion lente assumée

# Dossiers de la file, seuls à être commités par ces fonctions.
SUIVIS = ["queue", "publishing", "published", "stale"]


def _git(*args, timeout, check=True):
    """Exécute une commande git bornée. Traduit un blocage en erreur explicite."""
    try:
        return subprocess.run(["git", *args], check=check, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"git {' '.join(args)} n'a pas rendu la main en {timeout} s. "
            "Cause probable : connexion trop lente, ou git attend une saisie "
            "(identifiants) qu'aucun terminal ne peut fournir ici. "
            "Lance la commande à la main pour voir ce qu'il demande."
        ) from None


def pull():
    """Rejoue l'historique distant par-dessus le local.

    La CI commite dans ce dépôt à chaque publication : sans ce pull, la file
    lue est périmée et une annulation pourrait porter sur un post déjà parti.
    Un rebase en conflit remonte comme une erreur, jamais comme un silence.
    """
    _git("pull", "-q", "--rebase", timeout=NETWORK_TIMEOUT)


def sync(message):
    """Commite et pousse l'état de la file. Lève une exception en cas d'échec.

    En CI, un déplacement non poussé n'existe pas : le run suivant repart du
    dépôt distant et verrait encore le fichier dans queue/. Le verrou réel est
    donc le push qui précède l'appel API, pas le déplacement local.

    Ces commits ne sont jamais signés, ni en CI ni sur le poste de l'auteur.
    Une signature atteste qu'un humain a fait le commit à son clavier ; ceux-ci
    sont des opérations machine. Et le serveur MCP n'a pas de terminal : le
    02/10/2026, pinentry y attendait une phrase de passe que personne ne
    pouvait saisir, et un post programmé depuis la conversation n'est jamais
    parti. Dans publish_now, le même blocage survenait APRÈS la publication.
    """
    _git("add", "-A", *SUIVIS, timeout=LOCAL_TIMEOUT)
    _git("commit", "-q", "--no-gpg-sign", "-m", message, timeout=LOCAL_TIMEOUT)
    if _git("push", "-q", timeout=NETWORK_TIMEOUT, check=False).returncode != 0:
        # Quelqu'un a poussé entre-temps (nouveau post programmé, annulation).
        # Si le rebase entre en conflit, on s'arrête : pas de publication.
        _git("pull", "-q", "--rebase", timeout=NETWORK_TIMEOUT)
        _git("push", "-q", timeout=NETWORK_TIMEOUT)
