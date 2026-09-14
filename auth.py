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
import threading
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = "openid profile email w_member_social"

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

TOKEN_FILE = Path(__file__).parent / "token.json"

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


def wait_for_callback(timeout=300):
    """Ouvre un serveur local le temps de recevoir le callback."""
    server = HTTPServer(("localhost", 8000), CallbackHandler)
    server.timeout = timeout
    thread = threading.Thread(target=server.handle_request)
    thread.start()
    thread.join(timeout)
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
    TOKEN_FILE.write_text(json.dumps(payload, indent=2))
    os.chmod(TOKEN_FILE, 0o600)


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
    webbrowser.open(url)

    result = wait_for_callback()

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
            "person_urn": person_urn,
            "name": name,
        }
    )

    print(f"\nAuthentifie en tant que {name}")
    print(f"URN        : {person_urn}")
    print(f"Token valide jusqu'au {expires_at:%Y-%m-%d}")
    print(f"Enregistre dans {TOKEN_FILE}")
    return 0


if __name__ == "__main__":
    if "--status" in sys.argv:
        sys.exit(show_status())
    sys.exit(authenticate())
