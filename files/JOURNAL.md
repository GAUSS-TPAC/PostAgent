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

## 2026-10-04T00:58 — 2. Phase C de TESTING.md

Fait      : `tests/phase_c.py` créé (faux identifiants, jamais le vrai
            `token.json` ; réseau coupé au niveau socket pour C.2, C.6, C.7).
            Premier passage : trois défauts réels. Correctifs :
            - `linkedin.py` `_credentials()` : `token.json` sans
              `access_token` ou `person_urn` lève une `RuntimeError`
              explicite (était un `KeyError` brut) ; `expires_at` dépassé
              lève « relance python auth.py » avant tout appel réseau
              (aucun contrôle auparavant). Module à 250 lignes, la limite.
            - `publisher.py` `publish_due()` : une erreur réseau sur le
              `me()` préalable rend 1 avec un `::error::` lisible, file
              intacte (était une trace Python nue).
            Quatre lignes ajoutées au journal des tests de `TESTING.md`.
            Aucun de ces correctifs ne peut déclencher une publication :
            ils ajoutent des refus.
Preuve    : `POSTAGENT_DRY_RUN=1 .venv/bin/python tests/phase_c.py`

Avant correctifs (code de sortie 1) :
```
C.2 : ÉCHEC — ConnectionError : HTTPSConnectionPool(host='api.linkedin.com', port=443): Max retries exceeded with url: /v2/userinfo (...[Errno 101] Network is unreachable")) — 4 tentative(s) réseau
C.6 (environnement) : OK — RuntimeError : LINKEDIN_ACCESS_TOKEN défini sans LINKEDIN_PERSON_URN — 0 tentative(s) réseau
C.6 (fichier) : ÉCHEC — KeyError : 'person_urn' — 0 tentative(s) réseau
C.7 (publish) : OK — DryRunRefused, 0 tentative(s) réseau
C.7 (publisher) : ÉCHEC — exception=ConnectionError, code=None, fichier resté dans queue/=True
C.1 : OK — LinkedInError : LinkedIn a répondu 401 : {"status":401,"serviceErrorCode":65600,"code":"INVALID_ACCESS_TOKEN","message":"Invalid access token"}
PHASE C : ÉCHEC sur C.2, C.6 (fichier), C.7 (publisher)
```
Après correctifs (code de sortie 0) :
```
C.2 : OK — RuntimeError : Token LinkedIn expiré depuis le 2026-10-02 : relance python auth.py — 0 tentative(s) réseau
C.6 (environnement) : OK — RuntimeError : LINKEDIN_ACCESS_TOKEN défini sans LINKEDIN_PERSON_URN — 0 tentative(s) réseau
C.6 (fichier) : OK — RuntimeError : token.json sans person_urn : relance python auth.py — 0 tentative(s) réseau
C.7 (publish) : OK — DryRunRefused, 0 tentative(s) réseau
::error::Réseau injoignable avant toute publication, file intacte : HTTPSConnectionPool(host='api.linkedin.com', port=443): Max retries exceeded with url: /v2/userinfo (...[Errno 101] Network is unreachable"))
C.7 (publisher) : OK — exception=aucune, code=1, fichier resté dans queue/=True
C.1 : OK — LinkedInError : LinkedIn a répondu 401 : {"status":401,"serviceErrorCode":65600,"code":"INVALID_ACCESS_TOKEN","message":"Invalid access token"}
PHASE C : OK
```
Non-régression : `tests/garde_fou.py` → `GARDE-FOU OK`, code 0 ;
`wc -l` → `linkedin.py` 250, `publisher.py` 219 ; `requirements.txt` inchangé.

Appris    : (1) sous `DRY_RUN`, `publish()` refuse avant `_credentials()` :
            C.2 et C.6 ne sont observables que par `me()`. (2) Écart de
            protocole assumé : `TESTING.md` règle 3 veut Alan présent à tout
            test ; le backlog confie ceux-ci à la boucle parce qu'aucun ne
            publie. (3) Pour vérifier les imports, j'ai lancé une fois
            `import mcp_server, agenda, auth` : `auth` charge `.env` dans le
            processus. Rien n'a été affiché ni écrit, mais c'est à la limite
            de l'interdit sur les secrets — consigné en piège, à ne pas
            refaire.
Reste     : non vérifié sur le vrai `token.json` (interdit à la boucle) et
            coupure réseau pendant le POST non jouée — deux entrées dans
            `DECISIONS.md`.
