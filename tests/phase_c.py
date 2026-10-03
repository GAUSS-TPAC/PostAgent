"""
Phase C de TESTING.md : C.1, C.2, C.6, C.7. Aucun scénario ne publie.

Ne lit jamais le vrai token.json : les identifiants sont des faux, posés dans
l'environnement ou dans un fichier jetable. Seul C.1 touche le réseau, par
`me()` — une lecture, avec un jeton entièrement invalide.

Usage : .venv/bin/python tests/phase_c.py
"""

import contextlib
import json
import os
import socket
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Posé avant tout import du projet (CLAUDE.md, règle 4).
os.environ["POSTAGENT_DRY_RUN"] = "1"

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import linkedin  # noqa: E402
import publisher  # noqa: E402

FAUX_JETON = "jeton-de-test-entierement-invalide"
FAUX_URN = "urn:li:person:TEST"
ECHECS = []


def verdict(scenario, ok, observation):
    print(f"{scenario} : {'OK' if ok else 'ÉCHEC'} — {observation}")
    if not ok:
        ECHECS.append(scenario)


@contextlib.contextmanager
def reseau_coupe():
    """Coupe le réseau au niveau socket et compte les tentatives."""
    tentatives = []
    vrai = socket.socket.connect

    def refus(self, adresse):
        tentatives.append(adresse)
        raise OSError(101, "Network is unreachable")

    socket.socket.connect = refus
    try:
        yield tentatives
    finally:
        socket.socket.connect = vrai


@contextlib.contextmanager
def identifiants(env=None, fichier=None):
    """Faux identifiants : variables d'environnement, ou token.json jetable."""
    for cle in ("LINKEDIN_ACCESS_TOKEN", "LINKEDIN_PERSON_URN"):
        os.environ.pop(cle, None)
    os.environ.update(env or {})
    vrai = linkedin.TOKEN_FILE
    with tempfile.TemporaryDirectory() as tmp:
        linkedin.TOKEN_FILE = Path(tmp) / "token.json"
        if fichier is not None:
            linkedin.TOKEN_FILE.write_text(json.dumps(fichier))
        try:
            yield
        finally:
            linkedin.TOKEN_FILE = vrai
            for cle in env or {}:
                os.environ.pop(cle, None)


def erreur_de(appel):
    try:
        appel()
    except Exception as exc:  # le test juge le type et le message
        return exc
    return None


def c1_token_invalide():
    with identifiants(env={"LINKEDIN_ACCESS_TOKEN": FAUX_JETON, "LINKEDIN_PERSON_URN": FAUX_URN}):
        exc = erreur_de(linkedin.me)
    ok = isinstance(exc, linkedin.LinkedInError) and exc.status == 401
    verdict("C.1", ok, f"{type(exc).__name__} : {str(exc)[:150]}")


def c2_token_expire():
    hier = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    perime = {"access_token": FAUX_JETON, "person_urn": FAUX_URN, "expires_at": hier}
    with identifiants(fichier=perime), reseau_coupe() as tentatives:
        exc = erreur_de(linkedin.me)
    ok = isinstance(exc, RuntimeError) and "auth.py" in str(exc) and not tentatives
    verdict("C.2", ok, f"{type(exc).__name__} : {exc} — {len(tentatives)} tentative(s) réseau")


def c6_urn_absent():
    cas = {
        "environnement": dict(env={"LINKEDIN_ACCESS_TOKEN": FAUX_JETON}),
        "fichier": dict(fichier={"access_token": FAUX_JETON}),
    }
    for nom, source in cas.items():
        with identifiants(**source), reseau_coupe() as tentatives:
            exc = erreur_de(linkedin.me)
        ok = type(exc) is RuntimeError and "person_urn" in str(exc).lower() and not tentatives
        verdict(f"C.6 ({nom})", ok,
                f"{type(exc).__name__} : {exc} — {len(tentatives)} tentative(s) réseau")


def c7_reseau_coupe():
    texte = "PHASE C : ce texte ne doit jamais partir"
    env = {"LINKEDIN_ACCESS_TOKEN": FAUX_JETON, "LINKEDIN_PERSON_URN": FAUX_URN}

    # Publier, réseau coupé : le verrou refuse avant toute tentative.
    with identifiants(env=env), reseau_coupe() as tentatives:
        exc = erreur_de(lambda: linkedin.publish(texte, "CONNECTIONS"))
    verdict("C.7 (publish)", isinstance(exc, linkedin.DryRunRefused) and not tentatives,
            f"{type(exc).__name__}, {len(tentatives)} tentative(s) réseau")

    # Le publisher, réseau coupé, sur une file jetable : il doit rendre 1 avec
    # un message, laisser le fichier dans queue/, et ne pas lever d'exception.
    with tempfile.TemporaryDirectory() as tmp, identifiants(env=env), reseau_coupe():
        for nom in ("QUEUE", "PUBLISHING", "PUBLISHED", "STALE"):
            (Path(tmp) / nom.lower()).mkdir()
            setattr(publisher, nom, Path(tmp) / nom.lower())
        du = datetime.now(timezone.utc) - timedelta(minutes=1)
        (publisher.QUEUE / "test.json").write_text(json.dumps(
            {"text": texte, "scheduled_at": du.isoformat(), "visibility": "CONNECTIONS"}))
        rendu = []
        exc = erreur_de(lambda: rendu.append(publisher.publish_due(commit=False)))
        code = rendu[0] if rendu else None
        intact = (publisher.QUEUE / "test.json").exists()
    verdict("C.7 (publisher)", exc is None and code == 1 and intact,
            f"exception={type(exc).__name__ if exc else 'aucune'}, code={code}, "
            f"fichier resté dans queue/={intact}")


if __name__ == "__main__":
    c2_token_expire()
    c6_urn_absent()
    c7_reseau_coupe()
    c1_token_invalide()  # en dernier : le seul à toucher le réseau
    print(f"PHASE C : {'OK' if not ECHECS else 'ÉCHEC sur ' + ', '.join(ECHECS)}")
    sys.exit(1 if ECHECS else 0)
