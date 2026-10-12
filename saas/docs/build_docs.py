"""
Construit les PDF du cahier des charges et du guide d'utilisation du SaaS.

Les fichiers Markdown restent la source : on les corrige, puis on relance ce
script. Il régénère aussi les diagrammes (diagrammes.py). Les captures
d'écran de img/ecran-*.png ne sont pas régénérées ici : elles viennent de
l'application lancée en local avec des données de démonstration.

Usage : python3 saas/docs/build_docs.py
Outils : pandoc et google-chrome, comme files/build_guide.py, dont ce script
reprend le gabarit.
"""

import re
import subprocess
from datetime import date
from pathlib import Path

import diagrammes

ICI = Path(__file__).parent
FILES = ICI.parent.parent / "files"
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]

DOCUMENTS = [
    ("CAHIER_DES_CHARGES", "Cahier des charges",
     "Le SaaS multi-membres : besoin, exigences, conception, architecture et plan de validation."),
    ("GUIDE_UTILISATEUR", "Guide d'utilisation",
     "Se connecter, écrire ou faire rédiger un post, y joindre un carrousel, programmer et suivre ses publications."),
]

# Ajouts au gabarit : images, et tableaux longs qui doivent pouvoir changer de page.
STYLE = """
  img { max-width: 100%; display: block; margin: 4mm auto 2mm; }
  img[src$=".svg"] { width: 100%; }
  img[src*="cas-utilisation"] { width: 82%; }
  td.id { white-space: nowrap; }
  img[src*="ecran-"] { max-width: 78%; max-height: 205mm; border: .5pt solid var(--filet); }
  img[src*="carrousel-"] { border: .5pt solid var(--filet); }
  p.legende { text-align: center; font-size: 8.5pt; color: var(--gris); margin: 0 0 5mm; }
  table { break-inside: auto; }
  tr { break-inside: avoid; }
  h4 { font-size: 10pt; margin: 5mm 0 1mm; break-after: avoid; }
"""


def corps(nom):
    html = subprocess.run(["pandoc", "-f", "gfm", "-t", "html", str(ICI / f"{nom}.md")],
                          check=True, capture_output=True, text=True).stdout
    html = re.sub(r"<h1[^>]*>.*?</h1>\s*", "", html, count=1, flags=re.S)
    html = html.replace("<hr />", "")
    # Les identifiants (EF-01, ENF-03, R2, L4…) ne se coupent pas en deux lignes.
    html = re.sub(r"<td([^>]*)>((?:EF|ENF)-\d+|[RLO]\d+)</td>", r'<td\1 class="id">\2</td>', html)
    # Un paragraphe fait d'une seule phrase en italique est la légende d'une figure.
    html = re.sub(r"<p><em>([^<]*(?:<code>[^<]*</code>[^<]*)*)</em></p>", r'<p class="legende"><em>\1</em></p>', html)
    # Chaque grande partie (## 1. …) commence une page.
    return re.sub(r"<h2([^>]*)>(\d+\.)", r'<h2\1 class="partie">\2', html)


def page(nom, titre, accroche):
    aujourd_hui = date.today()
    gabarit = (FILES / "guide-template.html").read_text()
    remplacements = {
        "PostAgent — Guide d'utilisation": f"PostAgent — {titre}",
        "PostAgent · Guide d'utilisation": f"PostAgent · {titre}",
        '<div class="titre">Guide d\'utilisation</div>': f'<div class="titre">{titre}</div>',
        "Publier sur LinkedIn depuis une conversation, avec une planification\n        qui tourne sans serveur.": accroche,
        "</style>": STYLE + "</style>",
        "{{logo_postagent}}": (FILES / "assets" / "postagent-logo.svg").read_text(),
        "{{logo_sentinelle}}": (FILES / "assets" / "sentinelle-logo.svg").read_text(),
        "{{edition}}": f"{MOIS[aujourd_hui.month - 1]} {aujourd_hui.year}",
        "{{corps}}": corps(nom),
    }
    for ancien, nouveau in remplacements.items():
        assert ancien in gabarit, f"le gabarit a changé : « {ancien[:40]} » introuvable"
        gabarit = gabarit.replace(ancien, nouveau)
    return gabarit


def main():
    diagrammes.tous()
    for nom, titre, accroche in DOCUMENTS:
        # Écrit à côté des images, pour que les chemins relatifs img/… tiennent.
        source = ICI / f".{nom}.html"
        source.write_text(page(nom, titre, accroche))
        try:
            subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={ICI / (nom + '.pdf')}", source.as_uri()],
                           check=True, capture_output=True, timeout=180)
        finally:
            source.unlink()
        print(f"Écrit : {ICI / (nom + '.pdf')}")


if __name__ == "__main__":
    main()
