"""
Diagrammes du cahier des charges, écrits en SVG.

Chaque diagramme est une fonction qui place des boîtes et des flèches à la
main : pas d'outil de dessin, pas de dépendance, et un rendu identique sur
GitHub et dans le PDF. Pour en modifier un, change ses coordonnées ici puis
relance `python3 saas/docs/build_docs.py`.
"""

from pathlib import Path

IMG = Path(__file__).parent / "img"
ENCRE, GRIS, FOND = "#0a0a0a", "#555", "#f4f4f4"
POLICE = "Liberation Sans, Arial, sans-serif"


def _x(texte):
    return str(texte).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class Dessin:
    def __init__(self, largeur, hauteur):
        self.l, self.h, self.e = largeur, hauteur, []

    def rect(self, x, y, l, h, fond="#fff", rayon=6, tirets=False, trait=ENCRE):
        t = ' stroke-dasharray="6 5"' if tirets else ""
        self.e.append(f'<rect x="{x}" y="{y}" width="{l}" height="{h}" rx="{rayon}" fill="{fond}" stroke="{trait}" stroke-width="1.4"{t}/>')

    def texte(self, x, y, t, taille=12, gras=False, ancre="middle", couleur=ENCRE, halo=False):
        h = ' paint-order="stroke" stroke="#fff" stroke-width="5" stroke-linejoin="round"' if halo else ""
        self.e.append(f'<text x="{x}" y="{y}" font-size="{taille}" font-weight="{700 if gras else 400}" text-anchor="{ancre}" fill="{couleur}"{h}>{_x(t)}</text>')

    def boite(self, x, y, l, h, titre, lignes=(), fond="#fff", tirets=False):
        self.rect(x, y, l, h, fond, tirets=tirets)
        haut = y + (h - 15 * len(lignes)) / 2 + (5 if lignes else 4)
        self.texte(x + l / 2, haut, titre, 12.5, gras=True)
        for i, ligne in enumerate(lignes):
            self.texte(x + l / 2, haut + 16 + 15 * i, ligne, 10.5, couleur=GRIS)

    def fleche(self, x1, y1, x2, y2, etiquette=None, tirets=False, pointe=True, dx=0, dy=-6, taille=10.5):
        t = ' stroke-dasharray="6 5"' if tirets else ""
        m = ' marker-end="url(#p)"' if pointe else ""
        self.e.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{ENCRE}" stroke-width="1.3"{t}{m}/>')
        if etiquette:
            self.texte((x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy, etiquette, taille, halo=True)

    def acteur(self, x, y, nom):
        self.e.append(f'<g stroke="{ENCRE}" stroke-width="1.4" fill="none"><circle cx="{x}" cy="{y}" r="9"/>'
                      f'<path d="M{x} {y + 9}v24M{x - 15} {y + 19}h30M{x} {y + 33}l-12 18M{x} {y + 33}l12 18"/></g>')
        self.texte(x, y + 68, nom, 11.5, gras=True)

    def ovale(self, cx, cy, rx, nom, ry=19):
        self.e.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="#fff" stroke="{ENCRE}" stroke-width="1.3"/>')
        self.texte(cx, cy + 4, nom, 11)

    def ecrire(self, nom):
        IMG.mkdir(exist_ok=True)
        tete = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.l} {self.h}" font-family="{POLICE}">'
                f'<defs><marker id="p" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
                f'<path d="M0 0L10 5L0 10z" fill="{ENCRE}"/></marker></defs><rect width="{self.l}" height="{self.h}" fill="#fff"/>')
        (IMG / nom).write_text(tete + "".join(self.e) + "</svg>\n")


def contexte():
    d = Dessin(780, 380)
    d.acteur(70, 70, "Membre")
    d.acteur(70, 240, "Exploitant")
    d.boite(290, 140, 190, 90, "PostAgent", ["SaaS multi-membres"], fond=FOND)
    d.boite(580, 30, 180, 70, "LinkedIn", ["OAuth 2.0", "Posts, Images, Documents"])
    d.boite(580, 155, 180, 60, "API Claude", ["rédaction des brouillons"])
    d.boite(580, 275, 180, 70, "Cloudflare", ["Workers, D1, Cron", "hébergement"], tirets=True)
    d.fleche(95, 100, 288, 165, "écrit, programme, tranche")
    d.fleche(95, 270, 288, 205, "déploie, invite, surveille", dy=16)
    d.fleche(482, 160, 578, 75, "publie au nom du membre", dx=-22)
    d.fleche(482, 185, 578, 185, "sujet", dy=-7)
    d.fleche(482, 212, 578, 300, "hébergé par", tirets=True, pointe=False, dx=-10, dy=18)
    d.ecrire("contexte.svg")


def cas_utilisation():
    d = Dessin(820, 560)
    d.rect(190, 20, 450, 520, fond=FOND)
    d.texte(415, 44, "PostAgent", 13, gras=True)
    membre = ["Se connecter, renouveler l'accès", "Faire rédiger un brouillon", "Composer un post",
              "Joindre image, PDF ou carrousel", "Programmer ou annuler", "Trancher un post en panne",
              "Consulter ses posts", "Voir les statistiques", "Supprimer son compte"]
    d.acteur(80, 230, "Membre")
    for i, nom in enumerate(membre):
        y = 80 + 52 * i
        d.ovale(320, y, 112, nom)
        d.fleche(100, 262, 208, y, pointe=False)
    d.acteur(730, 40, "LinkedIn")
    d.acteur(730, 230, "Horloge")
    systeme = [("Authentifier le membre", 80), ("Publier les posts dus", 200), ("Périmer les posts en retard", 268)]
    for nom, y in systeme:
        d.ovale(545, y, 86, nom)
    d.fleche(434, 80, 457, 80, tirets=True)
    d.texte(446, 58, "« include »", 10, halo=True)
    d.fleche(712, 72, 633, 80, pointe=False)
    d.fleche(714, 84, 622, 190, pointe=False)
    d.fleche(712, 258, 633, 204, pointe=False)
    d.fleche(712, 266, 633, 268, pointe=False)
    d.ecrire("cas-utilisation.svg")


def architecture():
    d = Dessin(800, 480)
    d.boite(300, 12, 200, 52, "Navigateur du membre", ["interface statique, fetch"])
    d.rect(30, 105, 740, 232, fond=FOND, tirets=True)
    d.texte(46, 124, "Worker Cloudflare « postagent »", 11.5, gras=True, ancre="start")
    haut = [("Fichiers statiques", "public/"), ("index.js", "routage, en-têtes"), ("oauth.js", "connexion, sessions"), ("api.js", "routes du membre")]
    bas = [("scheduler.js", "publie les posts dus"), ("store.js", "tout le SQL"), ("linkedin.js", "client sans état"), ("generate.js", "brouillon")]
    xs = [50, 232, 414, 596]
    for (titre, ligne), x in zip(haut, xs):
        d.boite(x, 140, 156, 58, titre, [ligne])
    for (titre, ligne), x in zip(bas, xs):
        d.boite(x, 250, 156, 58, titre, [ligne])
    d.texte(400, 228, "crypto.js : chiffrement des jetons   ·   carousel.js : pages → PDF", 10.5, couleur=GRIS)
    d.fleche(400, 66, 400, 103, "HTTPS", dx=26, dy=4)
    for titre, lignes, x in [("Cron Trigger", ["chaque minute"], 50), ("D1 (SQLite)", ["users, sessions, posts"], 232),
                             ("API LinkedIn", ["api.linkedin.com"], 414), ("API Claude", ["api.anthropic.com"], 596)]:
        d.boite(x, 400, 156, 56, titre, lignes)
    d.fleche(128, 398, 128, 310)
    for x in (310, 492, 674):
        d.fleche(x, 310, x, 398)
    d.ecrire("architecture.svg")


def deploiement():
    d = Dessin(800, 400)
    d.boite(20, 30, 170, 60, "Poste du membre", ["navigateur"])
    d.boite(20, 290, 170, 70, "Poste de l'exploitant", ["wrangler deploy", "wrangler secret put"])
    d.rect(250, 20, 300, 350, fond=FOND, tirets=True)
    d.texte(400, 42, "Réseau Cloudflare", 12, gras=True)
    d.boite(275, 60, 250, 58, "Worker postagent", ["environnement production"])
    d.boite(275, 132, 250, 50, "Fichiers statiques", ["public/, en-têtes de sécurité"])
    d.boite(275, 196, 250, 50, "D1 postagent", ["région WEUR"])
    d.boite(275, 260, 250, 62, "Secrets et variables", ["TOKEN_KEY, LINKEDIN_*, INVITE_CODE", "ANTHROPIC_API_KEY, POSTAGENT_LIVE"])
    d.texte(400, 350, "Cron « * * * * * »", 11, couleur=GRIS)
    d.boite(610, 60, 170, 70, "LinkedIn", ["www.linkedin.com (OAuth)", "api.linkedin.com"])
    d.boite(610, 200, 170, 56, "Anthropic", ["api.anthropic.com"])
    d.fleche(192, 62, 273, 85, "HTTPS", dy=-8)
    d.fleche(192, 320, 273, 290, "API Cloudflare", dy=18)
    d.fleche(527, 85, 608, 92, "HTTPS", dy=-8)
    d.fleche(527, 105, 608, 222, "HTTPS", dx=18)
    d.ecrire("deploiement.svg")


def donnees():
    d = Dessin(800, 430)

    def table(x, y, nom, colonnes, l=220):
        h = 30 + 17 * len(colonnes)
        d.rect(x, y, l, h)
        d.rect(x, y, l, 26, fond=ENCRE)
        d.texte(x + l / 2, y + 18, nom, 12, gras=True, couleur="#fff")
        for i, (col, genre) in enumerate(colonnes):
            d.texte(x + 10, y + 44 + 17 * i, col, 10.5, ancre="start", gras=col.endswith("(PK)"))
            d.texte(x + l - 10, y + 44 + 17 * i, genre, 10, ancre="end", couleur=GRIS)
        return h

    table(20, 30, "users", [("id (PK)", "TEXT"), ("person_urn", "TEXT, unique"), ("name", "TEXT"),
                            ("token_enc", "TEXT, chiffré"), ("token_expires_at", "date ISO"),
                            ("consent_at", "date ISO"), ("created_at", "date ISO")])
    table(20, 230, "sessions", [("id (PK)", "empreinte SHA-256"), ("user_id", "→ users.id"), ("expires_at", "date ISO")])
    table(20, 330, "oauth_states", [("state (PK)", "TEXT"), ("invite_ok", "0 / 1"), ("expires_at", "date ISO")])
    table(330, 30, "posts", [("id (PK)", "TEXT"), ("user_id", "→ users.id"), ("text", "TEXT"),
                             ("visibility", "PUBLIC | CONNECTIONS"), ("media_kind", "image | document | carousel"),
                             ("media_title", "TEXT"), ("media_data", "BLOB, vidé après envoi"),
                             ("carousel", "JSON des pages"), ("scheduled_at", "date ISO"),
                             ("status", "6 états, voir diagramme"), ("post_id", "URN LinkedIn"),
                             ("error", "TEXT"), ("created_at", "date ISO"), ("published_at", "date ISO")], l=320)
    d.fleche(242, 90, 328, 75, "1 — N")
    d.fleche(130, 228, 130, 181, "N — 1", dx=30, dy=4)
    d.texte(490, 330, "Aucune valeur par défaut sur visibility :", 10.5, couleur=GRIS)
    d.texte(490, 346, "son absence est une erreur, pas un choix.", 10.5, couleur=GRIS)
    d.texte(490, 370, "Index : (status, scheduled_at) et (user_id, scheduled_at).", 10.5, couleur=GRIS)
    d.ecrire("donnees.svg")


def etats():
    d = Dessin(800, 360)

    def etat(x, y, nom, sous):
        d.rect(x, y, 150, 50, fond=FOND, rayon=24)
        d.texte(x + 75, y + 22, nom, 12.5, gras=True)
        d.texte(x + 75, y + 38, sous, 10, couleur=GRIS)

    d.e.append(f'<circle cx="40" cy="155" r="8" fill="{ENCRE}"/>')
    etat(110, 130, "scheduled", "programmé")
    etat(330, 130, "publishing", "réservé, en cours")
    etat(560, 130, "published", "post_id conservé")
    etat(330, 270, "failed", "attend une décision")
    etat(110, 270, "stale", "heure dépassée")
    etat(560, 20, "cancelled", "abandonné")
    d.fleche(48, 155, 108, 155, "création", dy=-8)
    d.fleche(262, 155, 328, 155)
    d.texte(295, 108, "heure venue, verrou ouvert,", 10)
    d.texte(295, 121, "réservation atomique", 10)
    d.fleche(482, 155, 558, 155, "201 + identifiant", dy=-8)
    d.fleche(405, 182, 405, 268, "erreur LinkedIn, accès expiré", dx=92, dy=4)
    d.fleche(160, 182, 160, 268, "retard > 3 h", dx=-44, dy=4)
    d.fleche(210, 268, 210, 182, "reprogrammé", dx=46, dy=4)
    d.fleche(332, 276, 250, 182, "reprogrammé", dx=20, dy=30)
    d.fleche(250, 132, 558, 52, "annulé par le membre", dy=-10)
    d.texte(660, 290, "Depuis failed, stale ou publishing,", 10.5, couleur=GRIS)
    d.texte(660, 306, "seul le membre décide :", 10.5, couleur=GRIS)
    d.texte(660, 322, "reprogrammer ou abandonner.", 10.5, couleur=GRIS)
    d.ecrire("etats-post.svg")


def sequence(nom, participants, messages):
    pas, marge = 46, 95
    ecart = (800 - 2 * marge) / (len(participants) - 1)
    hauteur = 90 + pas * len(messages)
    d = Dessin(800, hauteur)
    xs = [marge + ecart * i for i in range(len(participants))]
    for x, p in zip(xs, participants):
        d.boite(x - 72, 12, 144, 34, p, fond=FOND)
        d.fleche(x, 46, x, hauteur - 14, tirets=True, pointe=False)
    for i, (de, vers, etiquette, *reste) in enumerate(messages):
        y = 86 + pas * i
        if de == vers:
            d.rect(xs[de] - 150 if xs[de] > 650 else xs[de] + 8, y - 22, 330, 26, fond="#fff", rayon=3)
            d.texte((xs[de] - 150 if xs[de] > 650 else xs[de] + 8) + 165, y - 5, etiquette, 10.5)
            continue
        d.fleche(xs[de], y, xs[vers], y, f"{i + 1}. {etiquette}", tirets=bool(reste), dy=-7)
    d.ecrire(nom)


def tous():
    contexte()
    cas_utilisation()
    architecture()
    deploiement()
    donnees()
    etats()
    R = True  # message de retour : trait en tirets
    sequence("sequence-connexion.svg", ["Navigateur", "Worker", "D1", "LinkedIn"], [
        (0, 1, "POST /auth/login (consentement)"),
        (1, 2, "état OAuth à usage unique, 10 min"),
        (1, 0, "303 vers l'écran d'autorisation", R),
        (0, 3, "le membre autorise l'application"),
        (3, 0, "303 /auth/callback?code&state", R),
        (0, 1, "GET /auth/callback"),
        (1, 2, "consomme l'état, usage unique"),
        (1, 3, "échange le code, puis GET /v2/userinfo"),
        (1, 2, "membre, jeton chiffré, session"),
        (1, 0, "303 / + cookie sid (HttpOnly, Secure)", R),
    ])
    sequence("sequence-publication.svg", ["Cron", "scheduler.js", "D1", "LinkedIn"], [
        (0, 1, "chaque minute"),
        (1, 2, "périme les posts en retard de plus de 3 h"),
        (1, 2, "liste les posts dus"),
        (1, 1, "verrou POSTAGENT_LIVE fermé : arrêt, rien n'est réservé"),
        (1, 2, "réserve : UPDATE … WHERE status = 'scheduled'"),
        (1, 2, "lit le post, déchiffre le jeton"),
        (1, 3, "envoie le média (initializeUpload, PUT)"),
        (1, 3, "POST /rest/posts"),
        (3, 1, "201 + x-restli-id", R),
        (1, 2, "published + post_id, ou failed + erreur"),
    ])
    sequence("sequence-redaction.svg", ["Navigateur", "Worker", "API Claude"], [
        (0, 1, "POST /api/generate { sujet, carrousel }"),
        (1, 2, "messages.create, sortie JSON imposée"),
        (2, 1, "texte du post + pages du carrousel", R),
        (1, 0, "brouillon — rien n'est enregistré", R),
        (0, 1, "POST /api/carousel : aperçu PDF"),
        (0, 1, "POST /api/posts : visibilité et date choisies"),
    ])


if __name__ == "__main__":
    tous()
    print("Diagrammes écrits dans", IMG)
