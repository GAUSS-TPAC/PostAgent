"""
Client de publication LinkedIn, sans état.

Ne connaît ni la queue, ni MCP, ni GitHub Actions (NF8). Deux fonctions
publiques : publish() et me().

Identifiants lus dans cet ordre :
    1. variables d'environnement LINKEDIN_ACCESS_TOKEN + LINKEDIN_PERSON_URN (CI)
    2. token.json écrit par auth.py (local)

Usage manuel :
    python linkedin.py --me
    python linkedin.py --publish "Texte du post"
"""

import json
import os
import re
import sys
from pathlib import Path

import requests

# Vérifié sur Microsoft Learn le 14/09/2026 : dernière version publiée.
# Chaque version est supportée au moins un an ; à remonter avant l'été 2027.
LINKEDIN_VERSION = "202608"

POSTS_URL = "https://api.linkedin.com/rest/posts"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
TOKEN_FILE = Path(__file__).parent / "token.json"

# Caractères réservés du format "little" utilisé par le champ commentary.
# Non échappés, LinkedIn tronque ou avale silencieusement une partie du texte.
# '#' est volontairement laissé tel quel pour que les hashtags restent actifs.
_LITTLE_RESERVED = re.compile(r"([\\|{}@\[\]()<>*_~])")


class LinkedInError(RuntimeError):
    """Réponse inattendue de l'API. Porte le code HTTP et le corps brut."""

    def __init__(self, status, body):
        super().__init__(f"LinkedIn a répondu {status} : {body}")
        self.status = status
        self.body = body


def _credentials():
    """Retourne (access_token, person_urn).

    Les deux valeurs viennent toujours de la même source : mélanger un token
    d'environnement et un URN de fichier pourrait publier au nom du mauvais
    membre, ou échouer de façon incompréhensible.
    """
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    if token:
        urn = os.getenv("LINKEDIN_PERSON_URN")
        if not urn:
            raise RuntimeError("LINKEDIN_ACCESS_TOKEN défini sans LINKEDIN_PERSON_URN")
        return token, urn

    if not TOKEN_FILE.exists():
        raise RuntimeError("Aucun identifiant : ni variables d'environnement, ni token.json")
    data = json.loads(TOKEN_FILE.read_text())
    return data["access_token"], data["person_urn"]


def escape_little(text):
    """Échappe le texte brut pour le champ commentary."""
    return _LITTLE_RESERVED.sub(r"\\\1", text)


def publish(text, visibility="PUBLIC"):
    """Publie un post texte sur le profil du membre. Retourne le post_id.

    Aucune nouvelle tentative en cas d'échec : un 5xx peut masquer un post
    réellement créé, et rejouer risquerait un doublon (NF5). L'erreur remonte,
    l'appelant tranche.
    """
    if not text or not text.strip():
        raise ValueError("Texte de post vide")
    if visibility not in ("PUBLIC", "CONNECTIONS"):
        raise ValueError(f"Visibilité invalide : {visibility}")

    token, urn = _credentials()
    response = requests.post(
        POSTS_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "LinkedIn-Version": LINKEDIN_VERSION,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        },
        json={
            "author": urn,
            "commentary": escape_little(text),
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        },
        timeout=30,
    )
    if response.status_code != 201:
        raise LinkedInError(response.status_code, response.text)

    post_id = response.headers.get("x-restli-id")
    if not post_id:
        # Le post est probablement parti : on le signale plutôt que de réessayer.
        raise LinkedInError(201, "réponse sans en-tête x-restli-id, vérifier le profil")
    return post_id


def me():
    """Interroge LinkedIn sur le membre du token. Retourne {person_urn, name}.

    Sert aussi de test de validité du token : un token expiré ou révoqué
    lève LinkedInError(401).
    """
    token, _ = _credentials()
    response = requests.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if response.status_code != 200:
        raise LinkedInError(response.status_code, response.text)
    data = response.json()
    return {"person_urn": f"urn:li:person:{data['sub']}", "name": data.get("name")}


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--me":
        print(me())
    elif len(sys.argv) == 3 and sys.argv[1] == "--publish":
        print(f"Publié : {publish(sys.argv[2])}")
    else:
        print(__doc__)
        sys.exit(2)
