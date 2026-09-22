"""
Opérations git sur la file versionnée.

Séparé de publisher.py pour deux raisons : le serveur MCP en a besoin sans
vouloir la logique de publication, et chaque module doit rester lisible d'une
traite (NF7).

Toute commande est bornée dans le temps. Sans cela, une demande de phrase de
passe GPG bloquerait le serveur MCP indéfiniment : un agent qui attend un
prompt invisible est pire qu'un agent qui échoue.
"""

import subprocess

LOCAL_TIMEOUT = 30    # add, commit : local, mais gpg peut réclamer une saisie
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
            "Cause probable : GPG attend une phrase de passe qu'aucun terminal "
            "ne peut saisir ici. Lance la commande à la main, ou débloque l'agent gpg."
        ) from None


def pull():
    """Rejoue l'historique distant par-dessus le local.

    La CI commite dans ce dépôt à chaque publication : sans ce pull, la file
    lue est périmée et une annulation pourrait porter sur un post déjà parti.
    Un rebase en conflit remonte comme une erreur, jamais comme un silence.
    """
    _git("pull", "-q", "--rebase", timeout=NETWORK_TIMEOUT)


def sync(message, sign):
    """Commite et pousse l'état de la file. Lève une exception en cas d'échec.

    En CI, un déplacement non poussé n'existe pas : le run suivant repart du
    dépôt distant et verrait encore le fichier dans queue/. Le verrou réel est
    donc le push qui précède l'appel API, pas le déplacement local.

    `sign` est explicite, sans valeur par défaut : le runner GitHub n'a pas de
    clé et doit passer False, tandis qu'un commit fait sur le poste de l'auteur
    doit être signé comme les siens. Se tromper de côté doit se voir à l'appel.
    """
    _git("add", "-A", *SUIVIS, timeout=LOCAL_TIMEOUT)
    commit = ["commit", "-q", "-m", message]
    if not sign:
        commit.insert(2, "--no-gpg-sign")
    _git(*commit, timeout=LOCAL_TIMEOUT)
    if _git("push", "-q", timeout=NETWORK_TIMEOUT, check=False).returncode != 0:
        # Quelqu'un a poussé entre-temps (nouveau post programmé, annulation).
        # Si le rebase entre en conflit, on s'arrête : pas de publication.
        _git("pull", "-q", "--rebase", timeout=NETWORK_TIMEOUT)
        _git("push", "-q", timeout=NETWORK_TIMEOUT)
