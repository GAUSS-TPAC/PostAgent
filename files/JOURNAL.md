# JOURNAL.md

Ajout seulement, jamais réécrit. Format : voir `LOOP.md`, section 3.

## 2026-10-04T00:35 — 1. Vérifier le garde-fou de publication

Fait      : `tests/garde_fou.py` créé (preuve statique par AST + preuve
            dynamique, réseau coupé). Aucun code de production modifié :
            rien à corriger. Branche `chantier/boucle-autonome` ouverte.

Chemins menant au POST `/rest/posts` — un seul appel réseau,
`linkedin.py:152`, dans `publish()`, sept lignes après le verrou
(`linkedin.py:144-145`). Trois appelants :

| Chemin | Déclencheur | Garde |
|---|---|---|
| `linkedin.publish()` direct | import Python | verrou `DRY_RUN` |
| `publisher.publish_now()` (`publisher.py:149`) ← CLI `--publish-now`, outil MCP `publish_now` | humain, interdit à la boucle | verrou `DRY_RUN` |
| `publisher.publish_due()` (`publisher.py:117`) ← `python publisher.py [--commit]` ← workflow `publish.yml` (cron, `repository_dispatch` du Worker, `workflow_dispatch`) | un fichier dû dans `queue/` | verrou `DRY_RUN` ; en CI le verrou n'est pas posé, c'est voulu : la garde est alors le contenu de `queue/`, que seul `schedule_post` (humain) remplit |

Aucun chemin n'échappe au verrou. `auth.py:102` est le seul autre appel
d'écriture HTTP : échange du code OAuth, pas une publication.
`queue/` et `publishing/` sont vides sur `origin/main` (`.gitkeep` seuls).

Preuve    : `POSTAGENT_DRY_RUN=1 .venv/bin/python tests/garde_fou.py`

```
Preuve statique
  appel sortant : auth.py:102 -> TOKEN_URL
  appel sortant : linkedin.py:152 -> POSTS_URL
  verrou ligne 145, POST ligne 152, tous deux dans publish()
Preuve dynamique (POSTAGENT_DRY_RUN=1, réseau coupé)
  linkedin.publish       : refusé (DryRunRefused)
  publisher.publish_now  : refusé (DryRunRefused)
::error::test.json laissé dans publishing/, arbitrage manuel : POSTAGENT_DRY_RUN=1 : publication refusée avant tout appel réseau. Texte de 42 unités, visibilité CONNECTIONS. Retire la variable d'environnement pour publier réellement.
  publisher.publish_due  : refusé, fichier resté dans publishing/, code 1
GARDE-FOU OK
code de sortie : 0
```

Le `::error::` vient de la file jetable du test (dossier temporaire), pas
des dossiers réels. Grep de `LOOP.md` §1 lancé aussi : mêmes chemins, plus
des mentions en commentaire (`repo.py:56`, `files/build_guide.py:48-49`).
Définition de fini : plus gros module 248 lignes (`auth.py`) ;
`requirements.txt` = `requests`, `python-dotenv`.

Appris    : (1) le verrou est **opt-in** : il ne protège que si la variable
            est posée. Toute commande Python de la boucle se préfixe par
            `POSTAGENT_DRY_RUN=1`. (2) `python publisher.py` **sans
            argument** publie les posts dus : ne jamais le lancer nu.
            (3) `repo.sync()` pousse la branche courante et `git add -A`
            sur `queue/` : n'appeler ni `agenda.*` ni `repo.sync` hors
            dossier jetable. Consignés dans `LOOP.md` §7 ; question posée
            dans `DECISIONS.md`.
Reste     : rien.
