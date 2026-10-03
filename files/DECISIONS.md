# DECISIONS.md

Ce qui attend Alan. Format : voir `LOOP.md`, section 3.

## 2026-10-04 — Poser `POSTAGENT_DRY_RUN=1` d'office dans les sessions de boucle ?

Contexte  : le garde-fou tient (journal du 04/10, item 1), mais il est
            opt-in : `linkedin.publish()` ne refuse que si la variable est
            posée. La boucle la pose à la main sur chaque commande. Un oubli
            ne publierait que si un fichier dû traînait dans `queue/` ou si
            un script appelait `publish()` — peu probable, pas impossible.
Options   : (a) ne rien changer : la discipline de `LOOP.md` §7 suffit.
            (b) poser la variable dans `.claude/settings.local.json`
            (`env`) : toutes les commandes de la boucle sont verrouillées,
            mais le serveur MCP `post-agent` lancé par Claude Code en
            hérite — `publish_now` depuis la conversation refuserait
            jusqu'à ce que tu la retires.
            (c) inverser le verrou dans `linkedin.py` : publier exige
            `POSTAGENT_LIVE=1`, posé seulement dans `publish.yml` et dans
            la config du serveur MCP. Le plus sûr, mais touche le chemin de
            production.
Recommandé: (c), à faire par toi ou sous ta relecture : c'est le seul qui
            rend l'oubli inoffensif. La boucle ne l'a pas fait d'elle-même :
            modifier le chemin de publication sans toi est exactement ce
            qu'elle ne doit pas faire.
Bloque    : rien.
