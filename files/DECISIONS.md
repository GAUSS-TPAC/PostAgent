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

## 2026-10-04 — Vérifier le nouveau contrôle d'expiration sur le vrai token

Contexte  : `linkedin._credentials()` refuse désormais un `token.json` sans
            `access_token`/`person_urn` ou dont `expires_at` est dépassé.
            Testé sur des fichiers jetables seulement : la boucle n'a pas le
            droit de lire le vrai. Si son `expires_at` avait une forme
            inattendue (sans fuseau, par exemple), `publish_now` en local
            échouerait — bruyamment, sans publier.
Options   : lancer `.venv/bin/python linkedin.py --me` avant de fusionner
            la branche : il doit rendre ton nom et ton URN.
Recommandé: le faire avant la fusion ; trente secondes.
Bloque    : rien dans le backlog ; conditionne la fusion de
            `chantier/boucle-autonome`.

## 2026-10-04 — Réseau coupé pendant le POST : quel message ?

Contexte  : C.7 est joué pour tout ce qui précède le POST. La coupure
            pendant le POST lui-même n'est pas testable sous verrou. Dans
            `publisher.py --publish-now`, elle donne aujourd'hui une trace
            Python nue ; dans `publish_due`, un `::error::` et le fichier
            reste dans `publishing/`. Le fond du problème n'est pas la
            trace : un délai dépassé **après** l'envoi ne dit pas si le
            post est parti.
Options   : (a) laisser tel quel : la trace nue ne ment pas.
            (b) attraper l'erreur réseau dans `publish_now` et distinguer
            « connexion jamais établie, rien n'est parti » de « délai
            dépassé, vérifie ton profil avant de relancer ».
Recommandé: (b), avec toi : le texte du second message engage ce que tu
            feras devant un doute de doublon.
Bloque    : rien.

## 2026-10-04 — Supprimer `stale/2026-09-16T1523.json` ?

Contexte  : déchet du test de péremption du 18/09 (commit `89b952a`). Le
            backlog demande sa suppression ; `LOOP.md` §1 interdit à la
            boucle de supprimer quoi que ce soit dans `stale/`.
Options   : (a) `git rm stale/2026-09-16T1523.json` par toi ; `git show
            89b952a` en garde le contenu. (b) le laisser : `list_queue` le
            signalera à chaque appel comme un post périmé à arbitrer.
Recommandé: (a). Attention, `TESTING.md` ligne 243 le cite encore comme
            jeu de test d'E.13 (sous son ancien chemin `queue/`) : à
            corriger dans le même commit.
Bloque    : item 3.

## 2026-10-04 — Secret Worker `TRIGGER_KEY` à supprimer

Contexte  : sans effet depuis le retrait de `/trigger` le 22/09, mais
            toujours déposé côté Cloudflare d'après le backlog. La boucle
            ne lit ni ne modifie aucun secret : présence non vérifiée.
Options   : `cd clock && npx wrangler secret delete TRIGGER_KEY`, puis
            `npx wrangler secret list` pour constater qu'il ne reste que
            `DISPATCH_TOKEN`.
Recommandé: le supprimer : un secret sans usage reste un secret à faire
            fuiter.
Bloque    : item 3.

## 2026-10-04 — Garder la mention historique de `/trigger` dans `clock/README.md` ?

Contexte  : c'est la dernière référence du dépôt (ligne 122). Ce n'est pas
            une instruction : elle raconte pourquoi le Worker n'a plus
            d'URL. Le critère du backlog demande pourtant zéro référence.
Options   : (a) la garder : elle justifie `workers_dev = false`.
            (b) la reformuler sans nommer l'endpoint. Dans les deux cas,
            un commit sous `clock/**` fusionné sur `main` redéploie le
            Worker : à grouper avec un vrai changement de l'horloge.
Recommandé: (a), et assouplir le critère du backlog en « aucune
            instruction ne décrit `/trigger` ».
Bloque    : item 3.
