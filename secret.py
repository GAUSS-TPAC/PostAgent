"""
Synchronisation du token LinkedIn avec le secret GitHub Actions.

Deux copies du token existent : token.json en local, le secret LINKEDIN_ACCESS_TOKEN
en CI. Si elles divergent, la publication programmée casse le jour de l'expiration
sans aucun signal — le workflow tourne vert jusqu'au premier post dû, puis échoue
au pire moment. Ce module maintient les deux alignées et sait dire si elles le sont.

Ne dépend pas de auth.py : `in_sync` reçoit le token déjà chargé, ce qui évite
un import circulaire et garde ce module testable seul.
"""

import subprocess
from datetime import datetime, timedelta

SECRET_NAME = "LINKEDIN_ACCESS_TOKEN"

# Durée de vie d'un access token LinkedIn : 2 mois. Sert à retrouver la date
# d'obtention d'un token.json antérieur à l'ajout du champ `obtained_at`.
TOKEN_LIFETIME_DAYS = 60


def push(access_token):
    """Copie le token dans le secret GitHub. Lève une exception en cas d'échec.

    La valeur passe par l'entrée standard, jamais par la ligne de commande :
    les arguments d'un processus sont lisibles par les autres utilisateurs.
    """
    try:
        r = subprocess.run(
            ["gh", "secret", "set", SECRET_NAME],
            input=access_token, text=True, capture_output=True, timeout=120,
        )
    except FileNotFoundError:
        raise RuntimeError("gh introuvable : installe GitHub CLI, puis relance") from None
    except subprocess.TimeoutExpired:
        raise RuntimeError("gh secret set n'a pas rendu la main en 120 s") from None
    if r.returncode != 0:
        raise RuntimeError(f"gh secret set a échoué : {r.stderr.strip()}")


def updated_on():
    """Date de dernière mise à jour du secret, ou None si gh est injoignable.

    None veut dire « inconnu », jamais « pas à jour » : l'état doit rester
    consultable hors ligne, et une connexion coupée n'est pas une divergence.
    """
    try:
        r = subprocess.run(["gh", "secret", "list"], capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    for ligne in r.stdout.splitlines():
        champs = ligne.split()
        if len(champs) > 1 and champs[0] == SECRET_NAME:
            try:
                return datetime.fromisoformat(champs[1]).date()
            except ValueError:
                return None
    return None


def in_sync(token):
    """True, False, ou None si l'état du secret n'a pas pu être lu."""
    if not token:
        return None
    maj = updated_on()
    if maj is None:
        return None
    obtenu = token.get("obtained_at")
    if obtenu:
        obtenu = datetime.fromisoformat(obtenu).date()
    else:
        # token.json d'avant l'ajout du champ : on déduit de l'expiration.
        obtenu = (datetime.fromisoformat(token["expires_at"])
                  - timedelta(days=TOKEN_LIFETIME_DAYS)).date()
    return maj >= obtenu
