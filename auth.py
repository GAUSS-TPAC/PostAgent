"""
Authentification OAuth 2.0 auprès de LinkedIn.

Lance le flow d'autorisation, récupère un access token et l'URN du membre,
puis les enregistre dans token.json.

Usage:
    python auth.py           # nouvelle authentification
    python auth.py --status  # état du token existant
"""

import json
import os
import secrets
import sys
import subprocess
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

import repo
import secret

load_dotenv()

CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = "openid profile email w_member_social"

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

TOKEN_FILE = Path(__file__).parent / "token.json"

# Date d'expiration seule, sans le token : versionnée pour que le workflow
# puisse alerter avant l'échéance sans qu'on ait à gérer un secret de plus.
EXPIRY_FILE = Path(__file__).parent / "token_expiry.json"

# Rempli par le handler HTTP, lu par le thread principal.
_result = {}


class CallbackHandler(BaseHTTPRequestHandler):
    """Capture le code d'autorisation renvoyé par LinkedIn."""

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)
        _result["code"] = params.get("code", [None])[0]
        _result["state"] = params.get("state", [None])[0]
        _result["error"] = params.get("error_description", params.get("error", [None]))[0]

        ok = _result["code"] is not None
        body = (
            "<h2>Authentification reussie</h2><p>Tu peux fermer cet onglet.</p>"
            if ok
            else f"<h2>Echec</h2><p>{_result['error']}</p>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args):
        pass  # silence les logs du serveur


def wait_for_callback(url, timeout=300):
    """Ouvre le serveur local, puis le navigateur, et attend le callback.

    Le serveur écoute avant l'ouverture du navigateur, sinon une redirection
    rapide pourrait arriver sur un port fermé. Les requêtes hors /callback
    (favicon, préchargement) sont ignorées : on attend le vrai callback.
    """
    server = HTTPServer(("localhost", 8000), CallbackHandler)
    server.timeout = 1  # handle_request rend la main chaque seconde
    webbrowser.open(url)
    deadline = time.monotonic() + timeout
    try:
        while not _result and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    return _result


def exchange_code(code):
    """Echange le code d'autorisation contre un access token."""
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Echange du code refuse ({response.status_code}): {response.text}")
    return response.json()


def fetch_member_urn(access_token):
    """Recupere l'identifiant du membre via OpenID Connect."""
    response = requests.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"userinfo a echoue ({response.status_code}): {response.text}")
    data = response.json()
    return f"urn:li:person:{data['sub']}", data.get("name", "inconnu")


def save_token(payload):
    # Créé directement en 600 : le token n'est jamais lisible par un autre
    # utilisateur, même un instant. Le chmod couvre un fichier préexistant.
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(payload, f, indent=2)
    os.chmod(TOKEN_FILE, 0o600)
    EXPIRY_FILE.write_text(json.dumps({"expires_at": payload["expires_at"]}, indent=2) + "\n")


def load_token():
    if not TOKEN_FILE.exists():
        return None
    return json.loads(TOKEN_FILE.read_text())


def show_status():
    token = load_token()
    if not token:
        print("Aucun token. Lance: python auth.py")
        return 1

    expires_at = datetime.fromisoformat(token["expires_at"])
    remaining = expires_at - datetime.now(timezone.utc)
    days = remaining.days

    print(f"Membre     : {token['name']}")
    print(f"URN        : {token['person_urn']}")
    print(f"Expire le  : {expires_at:%Y-%m-%d}")

    sync = secret.in_sync(token)
    etat = {True: "a jour", False: "DIVERGENT - relance python auth.py", None: "inconnu (gh injoignable)"}
    print(f"Secret CI  : {etat[sync]}")

    if days < 0:
        print("Statut     : EXPIRE - relance python auth.py")
        return 1
    if days < 7:
        print(f"Statut     : expire dans {days} jours - pense a renouveler")
    else:
        print(f"Statut     : valide ({days} jours restants)")
    return 0


def authenticate():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("LINKEDIN_CLIENT_ID ou LINKEDIN_CLIENT_SECRET manquant dans .env")
        return 1

    state = secrets.token_urlsafe(16)
    url = f"{AUTH_URL}?" + urlencode(
        {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "state": state,
            "scope": SCOPES,
        }
    )

    print("Ouverture du navigateur pour autoriser l'application...")
    print(f"Si rien ne s'ouvre, copie cette URL :\n{url}\n")

    result = wait_for_callback(url)

    if not result.get("code"):
        print(f"Echec : {result.get('error', 'aucune reponse recue')}")
        return 1
    if result.get("state") != state:
        print("Echec : state invalide, tentative de CSRF ou session croisee")
        return 1

    token_data = exchange_code(result["code"])
    access_token = token_data["access_token"]
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])

    person_urn, name = fetch_member_urn(access_token)

    save_token(
        {
            "access_token": access_token,
            "expires_at": expires_at.isoformat(),
            "obtained_at": datetime.now(timezone.utc).isoformat(),
            "person_urn": person_urn,
            "name": name,
        }
    )

    print(f"\nAuthentifie en tant que {name}")
    print(f"URN        : {person_urn}")
    print(f"Token valide jusqu'au {expires_at:%Y-%m-%d}")
    print(f"Enregistre dans {TOKEN_FILE}")

    # Les deux copies sont mises a jour dans la foulee, jamais "plus tard" :
    # c'est l'ecart entre les deux qui casse la publication en CI.
    secret.push(access_token)
    print("Secret GitHub LINKEDIN_ACCESS_TOKEN mis a jour")

    repo._git("add", str(EXPIRY_FILE.name), timeout=repo.LOCAL_TIMEOUT)
    repo._git("commit", "-q", "-m", "Renouvelle le token LinkedIn",
              timeout=repo.LOCAL_TIMEOUT)
    repo._git("push", "-q", timeout=repo.NETWORK_TIMEOUT)
    print(f"{EXPIRY_FILE.name} commite et pousse")
    return 0


if __name__ == "__main__":
    if "--status" in sys.argv:
        sys.exit(show_status())
    sys.exit(authenticate())
