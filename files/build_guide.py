"""
Construit GUIDE.pdf à partir de GUIDE.md.

GUIDE.md reste la source : on le corrige, puis on relance ce script. Le PDF
n'est qu'un rendu — ne l'édite jamais à la main.

Usage : python files/build_guide.py
Outils : pandoc et google-chrome (impression headless). Aucune dépendance Python.
"""

import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path

ICI = Path(__file__).parent
ASSETS = ICI / "assets"
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]


def svg(nom):
    """SVG en ligne, sans prologue : il hérite ainsi de la couleur du texte."""
    return (ASSETS / nom).read_text()


# Remplace le schéma ASCII du guide : même contenu, lisible imprimé.
SCHEMA = """
<svg class="schema" viewBox="0 0 720 150" xmlns="http://www.w3.org/2000/svg">
  <defs><marker id="f" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
    <path d="M0,0 L10,5 L0,10 z" fill="#000"/></marker></defs>
  <g font-family="Liberation Sans, Arial, sans-serif" font-size="12" text-anchor="middle">
    <g fill="none" stroke="#000" stroke-width="1.5">
      <rect x="4" y="30" width="112" height="48"/><rect x="152" y="30" width="112" height="48"/>
      <rect x="300" y="30" width="112" height="48"/><rect x="448" y="30" width="112" height="48"/>
      <rect x="596" y="30" width="112" height="48" stroke-width="3"/>
    </g>
    <g stroke="#000" stroke-width="1.5" marker-end="url(#f)">
      <line x1="116" y1="54" x2="150" y2="54"/><line x1="264" y1="54" x2="298" y2="54"/>
      <line x1="412" y1="54" x2="446" y2="54"/><line x1="560" y1="54" x2="594" y2="54"/>
    </g>
    <path d="M208,78 V118 H652 V80" fill="none" stroke="#000" stroke-width="1.5" stroke-dasharray="4 3" marker-end="url(#f)"/>
    <text x="60" y="51" font-weight="700">Toi + assistant</text><text x="60" y="67" fill="#555">rédaction</text>
    <text x="208" y="51" font-weight="700">Outils MCP</text><text x="208" y="67" fill="#555">mcp_server.py</text>
    <text x="356" y="51" font-weight="700">queue/</text><text x="356" y="67" fill="#555">fichiers JSON, git</text>
    <text x="504" y="51" font-weight="700">GitHub Actions</text><text x="504" y="67" fill="#555">toutes les 15 min</text>
    <text x="652" y="51" font-weight="700">LinkedIn</text><text x="652" y="67" fill="#555">/rest/posts</text>
    <text x="430" y="138" fill="#555">publish_now : publication directe</text>
    <text x="430" y="20" fill="#555" font-size="11">schedule_post : programmé</text>
  </g>
</svg>"""


def corps():
    html = subprocess.run(
        ["pandoc", "-f", "gfm", "-t", "html", str(ICI / "GUIDE.md")],
        check=True, capture_output=True, text=True,
    ).stdout
    html = re.sub(r"<h1[^>]*>GUIDE\.md</h1>\s*", "", html, count=1)
    html = re.sub(r"<pre><code>[^<]*─►.*?</code></pre>", SCHEMA, html, count=1, flags=re.S)
    html = html.replace("<hr />", "")
    # Chaque grande partie (## 1. …) commence une page.
    return re.sub(r"<h2([^>]*)>(\d+\.)", r'<h2\1 class="partie">\2', html)


def page():
    aujourd_hui = date.today()
    edition = f"{MOIS[aujourd_hui.month - 1]} {aujourd_hui.year}"
    gabarit = (ICI / "guide-template.html").read_text()
    return (gabarit
            .replace("{{logo_postagent}}", svg("postagent-logo.svg"))
            .replace("{{logo_sentinelle}}", svg("sentinelle-logo.svg"))
            .replace("{{edition}}", edition)
            .replace("{{corps}}", corps()))


def main():
    sortie = ICI / "GUIDE.pdf"
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "guide.html"
        source.write_text(page())
        subprocess.run(
            ["google-chrome", "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={sortie}", source.as_uri()],
            check=True, capture_output=True, timeout=120,
        )
    print(f"Écrit : {sortie}")


if __name__ == "__main__":
    main()
