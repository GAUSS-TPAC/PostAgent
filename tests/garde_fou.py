"""
Vérifie le garde-fou de publication. Ne publie rien, ne lit aucun secret.

Deux preuves, toutes deux capables d'échouer :
  1. statique — le dépôt ne contient qu'UN appel capable d'atteindre
     /rest/posts, et il est placé après le verrou POSTAGENT_DRY_RUN ;
  2. dynamique — verrou posé, les trois appelants (linkedin.publish,
     publisher.publish_now, publisher.publish_due) s'arrêtent avant le réseau.

Le réseau est coupé deux fois (requests.post et socket.connect) : si le verrou
cédait, le test échouerait au lieu de publier.

Usage : .venv/bin/python tests/garde_fou.py
"""

import ast
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

import requests  # noqa: E402

import linkedin  # noqa: E402
import publisher  # noqa: E402


def _reseau_interdit(*args, **kwargs):
    raise AssertionError("LE VERROU A CÉDÉ : un appel réseau a été tenté")


requests.post = _reseau_interdit
socket.socket.connect = _reseau_interdit

ENVOIS = {"post", "put", "patch", "request", "urlopen"}


def appels_sortants():
    """Tous les appels d'écriture HTTP des modules Python du dépôt."""
    trouves = []
    for path in sorted(ROOT.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) in ENVOIS:
                cible = ast.unparse(node.args[0]) if node.args else "?"
                trouves.append((path.name, node.lineno, cible))
    return trouves


def preuve_statique():
    appels = appels_sortants()
    for nom, ligne, cible in appels:
        print(f"  appel sortant : {nom}:{ligne} -> {cible}")
    vers_posts = [a for a in appels if a[2] == "POSTS_URL"]
    assert [(a[0], a[2]) for a in appels] == [("auth.py", "TOKEN_URL"), ("linkedin.py", "POSTS_URL")], appels
    assert len(vers_posts) == 1, vers_posts

    # Le POST doit être dans publish(), après le `raise DryRunRefused`.
    arbre = ast.parse((ROOT / "linkedin.py").read_text())
    publish = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "publish")
    verrou = next(n.lineno for n in ast.walk(publish)
                  if isinstance(n, ast.Raise) and "DryRunRefused" in ast.unparse(n))
    assert publish.lineno < verrou < vers_posts[0][1] <= publish.end_lineno, (verrou, vers_posts)
    print(f"  verrou ligne {verrou}, POST ligne {vers_posts[0][1]}, tous deux dans publish()")


def preuve_dynamique():
    texte = "GARDE-FOU : ce texte ne doit jamais partir"

    try:
        linkedin.publish(texte, "CONNECTIONS")
        raise AssertionError("linkedin.publish n'a pas refusé")
    except linkedin.DryRunRefused:
        print("  linkedin.publish       : refusé (DryRunRefused)")

    try:
        publisher.publish_now(texte, "CONNECTIONS")
        raise AssertionError("publisher.publish_now n'a pas refusé")
    except linkedin.DryRunRefused:
        print("  publisher.publish_now  : refusé (DryRunRefused)")

    # publish_due sur une file jetable : jamais les dossiers réels, jamais git.
    with tempfile.TemporaryDirectory() as tmp:
        for nom in ("QUEUE", "PUBLISHING", "PUBLISHED", "STALE"):
            dossier = Path(tmp) / nom.lower()
            dossier.mkdir()
            setattr(publisher, nom, dossier)
        du = datetime.now(timezone.utc) - timedelta(minutes=1)
        (publisher.QUEUE / "test.json").write_text(json.dumps(
            {"text": texte, "scheduled_at": du.isoformat(), "visibility": "CONNECTIONS"}))
        linkedin.me = lambda: {"name": "test"}  # sinon : appel réseau avec le token

        code = publisher.publish_due(commit=False)
        assert code == 1, code
        assert (publisher.PUBLISHING / "test.json").exists()
        assert not list(publisher.PUBLISHED.iterdir())
        print("  publisher.publish_due  : refusé, fichier resté dans publishing/, code 1")


if __name__ == "__main__":
    print("Preuve statique")
    preuve_statique()
    print("Preuve dynamique (POSTAGENT_DRY_RUN=1, réseau coupé)")
    preuve_dynamique()
    print("GARDE-FOU OK")
