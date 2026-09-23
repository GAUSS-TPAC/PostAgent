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
    """Horodatage de dernière mise à jour du secret, ou None si gh est injoignable.

    Passe par l'API REST et non par `gh secret list`, qui n'affiche qu'une date
    sans heure : une divergence créée et corrigée le même jour serait invisible.
    (`gh secret list --json` donnerait aussi l'heure, mais n'existe pas avant
    les versions récentes de gh — l'API, elle, ne bouge pas.)

    None veut dire « inconnu », jamais « pas à jour » : l'état doit rester
    consultable hors ligne, et une connexion coupée n'est pas une divergence.
    """
    try:
        r = subprocess.run(
            ["gh", "api", f"repos/{{owner}}/{{repo}}/actions/secrets/{SECRET_NAME}",
             "--jq", ".updated_at"],
            capture_output=True, text=True, timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    try:
        return datetime.fromisoformat(r.stdout.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def in_sync(token):
    """True, False, ou None si l'état du secret n'a pas pu être lu.

    Deux précisions de comparaison, selon ce que le token sait de lui-même :
    avec `obtained_at`, on compare à la seconde ; sans lui, la date d'obtention
    est déduite de l'expiration et ne vaut qu'au jour près — comparer à la
    seconde une valeur approchée produirait de fausses alertes.
    """
    if not token:
        return None
    maj = updated_on()
    if maj is None:
        return None

    obtenu = token.get("obtained_at")
    if obtenu:
        return maj >= datetime.fromisoformat(obtenu)
    # token.json d'avant l'ajout du champ : précision limitée au jour.
    approx = datetime.fromisoformat(token["expires_at"]) - timedelta(days=TOKEN_LIFETIME_DAYS)
    return maj.date() >= approx.date()
