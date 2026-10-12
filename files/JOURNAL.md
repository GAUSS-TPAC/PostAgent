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

## 2026-10-04T01:06 — 3. Nettoyages en attente

Fait      : aucun fichier de code ni de doc modifié. Item passé `bloqué`,
            trois entrées dans `DECISIONS.md`.
            - `/trigger` : aucune instruction ne le décrit encore, ni dans
              `README.md`, ni dans `CLAUDE.md`. Il reste une seule mention,
              historique, dans `clock/README.md:122` (« Une première version
              exposait… Il a été retiré »). Non retirée : elle explique
              `workers_dev = false`, et toute modification sous `clock/**`
              redéploie le Worker à la fusion sur `main`
              (`deploy-clock.yml`), ce qui est interdit à la boucle.
            - `stale/2026-09-16T1523.json` : non supprimé, `LOOP.md` §1
              l'interdit sans exception.
            - secret Worker `TRIGGER_KEY` : consigné, non touché.
Preuve    : `git grep -n -i -E "/trigger|TRIGGER_KEY" -- . ':!clock/package-lock.json'`

```
clock/README.md:122:Une première version exposait un endpoint `/trigger` protégé par une clé
files/BACKLOG.md:43:- Secret `TRIGGER_KEY` encore présent côté Worker (sans effet depuis le
files/BACKLOG.md:47:  encore l'endpoint `/trigger`, supprimé le 22/09.
files/BACKLOG.md:49:**Fini quand** : le dépôt ne contient plus de référence à `/trigger`, le
```
`ls stale` → `2026-09-16T1523.json`, `.gitkeep` (fichier toujours là).
Présence du secret `TRIGGER_KEY` côté Cloudflare : non vérifiée, la boucle
ne lit pas les secrets.

Appris    : (1) le critère « plus aucune référence à `/trigger` » ne peut
            pas être atteint à la lettre tant que `BACKLOG.md` le cite.
            (2) Lecture retenue de `LOOP.md` §6 : un geste interdit bloque
            l'item, pas la boucle, tant que d'autres items n'en dépendent
            pas — conforme à la consigne de lancement (« ce qui me revient
            va dans DECISIONS.md, et tu passes à l'item suivant »).
Reste     : les trois décisions d'Alan.

## 2026-10-04T01:22 — 4. Réécrire PRODUIT.md — forme auto-hébergée

Fait      : `files/PRODUIT.md` réécrit en entier. Forme hébergée retirée
            (schéma Cloudflare multi-clients, base de jetons, ancienne
            découpe). Ajouts : tableau hébergé / auto-hébergé, ce qui est
            vendu, ce qui n'est jamais vendu (§8.2), ce que le client
            enregistre lui-même, règle « le client saisit lui-même chaque
            secret », section P0 relue sous la nouvelle forme, découpe
            P1–P7 proposée en fin de fichier.
Preuve    : `grep -n -i -E "chiffr|en base|stock|\bD1\b|Durable|token|jeton" files/PRODUIT.md`

```
18:| Jeton d'accès LinkedIn | — | reste chez le client, dans ses propres secrets |
21:| Ce que Sentinelle détient | — | **rien** : ni jeton, ni contenu, ni accès à l'instance |
48:| Identifiants de l'app et jeton d'accès | ses propres secrets (aujourd'hui : `.env` local et secrets de son dépôt GitHub) | Sentinelle ne doit
53:secret.** Un partage d'écran où le jeton apparaît, un secret dicté ou copié
99:- **Pas de refresh token** : réservés aux partenaires approuvés. Chaque
160:- Sentinelle ne détient aucun jeton d'accès, aucun identifiant d'app, aucun
161:  texte de post d'un client. Il n'y a donc ni base, ni chiffrement, ni
190:Durable Objects, migration d'Alan) est abandonnée avec la forme hébergée.
```
Huit lignes, lues une à une : toutes disent que le jeton reste chez le
client ou que Sentinelle n'en détient pas. Aucune ne décrit un stockage de
jeton client. `grep -n -E "^## |^### " files/PRODUIT.md | tail -2` :
```
184:## Étapes
192:### Découpe proposée le 04/10/2026 — non commencée, à valider par Alan
```
Rien de P1–P7 n'est commencé : aucun fichier de code touché par cet item.

Appris    : (1) la forme auto-hébergée lève §1.4 et §8.2, **pas §3.1**
            (« automate posting ») : elle vise chaque app, celle d'Alan
            comprise. Écrit tel quel dans `PRODUIT.md`. (2) Point nouveau,
            §2.2 : interdiction de faire porter ses clés par ses
            utilisateurs ; lecture favorable ici, à surveiller. (3) « un
            dépôt par client, un secret par client » était le défaut de la
            forme hébergée ; c'est la définition de la forme auto-hébergée.
            L'instance actuelle est donc la première installation.
Reste     : la mention « Postiz » est reprise du backlog sans vérification.
            `CLAUDE.md:152` et `ROADMAP.md:83` parlent encore de
            « multi-clients » et de « multi-tenant » : non modifiés, hors
            de l'item — à aligner par Alan ou par un item dédié.

## 2026-10-04T01:38 — 5. Marketing API Terms — pour archive

Fait      : texte téléchargé et lu en entier (132 lignes, 39 805
            caractères une fois le HTML retiré). Note datée ajoutée à la
            section P0 de `files/PRODUIT.md`, avec la version lue.
            Réponse : le programme lève §1.4, **pas §3.1** — aucun passage
            ne traite de publication automatique ou programmée.
Preuve    : sur le texte téléchargé (`mkt.txt`, hors dépôt) puis sur le dépôt :

```
$ grep -n -o -E "Last revised on [A-Za-z]+ [0-9]+, [0-9]{4}" mkt.txt
6:Last revised on July 25, 2025
$ grep -n -o -i -E ".{90}(automat|schedul).{90}" mkt.txt
72:ective talent for hire, for lead creation, to enhance customer data in a CRM or marketing automation platform, to build an audience list, or for ad targeting purposes); (6) use Member Dat
108:(“Termination for Convenience”). For clarity, any termination of these LMA Terms will not automatically terminate the API Terms of Use but any termination of the API Terms of Use will aut
$ grep -n -E "Note du 04/10/2026|Last revised on" files/PRODUIT.md
134:### Note du 04/10/2026 — Marketing API Terms, pour archive
137:(`linkedin.com/legal/l/marketing-api-terms`), version « Last revised on
```
Les deux seules occurrences d'« automat » sont « marketing automation
platform » et « automatically terminate » : rien sur la publication.

Appris    : le backlog parle du « programme Partner » ; le document public
            est celui du programme **Vetted** (Marketing API). Le Partner
            Program est un contrat signé à part, non publié : sa réponse à
            §3.1 ne peut pas être lue, seulement demandée à LinkedIn.
Reste     : rien. La levée de §1.4 est une déduction (ses critères sont
            ceux du Self-Serve), pas une phrase du texte.

## 2026-10-04T01:50 — 6. Question ouverte à instruire

Fait      : analyse et recommandation écrites dans `files/DECISIONS.md`
            (« Le portage TypeScript / Cloudflare (P1) garde-t-il un sens
            sans jetons hébergés ? »). Recommandation : ne pas porter le
            cœur ; décider à l'étape P3 s'il faut une adresse publique chez
            le client, et n'ajouter alors que cela. Rien de codé.
Preuve    : `grep -n -E "^## " files/DECISIONS.md | cut -c1-110`

```
5:## 2026-10-04 — Poser `POSTAGENT_DRY_RUN=1` d'office dans les sessions de boucle ?
28:## 2026-10-04 — Vérifier le nouveau contrôle d'expiration sur le vrai token
42:## 2026-10-04 — Réseau coupé pendant le POST : quel message ?
59:## 2026-10-04 — Supprimer `stale/2026-09-16T1523.json` ?
72:## 2026-10-04 — Secret Worker `TRIGGER_KEY` à supprimer
84:## 2026-10-04 — Garder la mention historique de `/trigger` dans `clock/README.md` ?
97:## 2026-10-04 — Le portage TypeScript / Cloudflare (P1) garde-t-il un sens sans jetons hébergés ?
```
Aucun code touché par cet item : `git diff --stat -- '*.py' clock` vide.
Non-régression : `tests/garde_fou.py` → `GARDE-FOU OK`.

Appris    : ce qui reste en faveur de Cloudflare ne concerne pas le cœur
            mais deux étapes précises (P3, renouvellement sans terminal ;
            P5, assistant sans installation), parce que la forme actuelle
            n'a aucune adresse publique.
Reste     : rien.

## 2026-10-04T01:52 — Arrêt de la boucle

Condition : `LOOP.md` §6, « le backlog n'a plus d'item non bloqué ».
État      : items 1, 2, 4, 5, 6 finis ; item 3 bloqué sur trois décisions.
            Sept entrées dans `DECISIONS.md`. Branche
            `chantier/boucle-autonome` poussée, `main` intacte. Aucune
            publication, aucun fichier poussé dans `queue/`, aucun secret
            modifié, Worker non déployé.
