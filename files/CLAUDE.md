# CLAUDE.md

Contexte de travail pour Claude Code sur ce dépôt. Lis ce fichier en entier
avant toute modification.

## Le projet en une phrase

Un agent personnel de publication LinkedIn, piloté par conversation plutôt que
par tableau de bord, dont l'exécution planifiée repose sur GitHub Actions pour
rester gratuite et permanente.

## Règles non négociables

1. **API officielle uniquement.** Aucun scraping, aucun appel à l'API Voyager,
   aucune automatisation de navigateur sur LinkedIn. Un bannissement est
   irréversible. Si une fonctionnalité demandée n'est atteignable que par
   scraping, refuse-la et explique pourquoi.
2. **Aucun secret dans le dépôt.** `.env` et `token.json` sont dans
   `.gitignore`. Ne les lis pas, ne les affiche pas, ne les commite jamais.
   En CI, les secrets viennent de GitHub Secrets.
3. **Idempotence.** Le publisher tourne à chaque run et peut rejouer.
   Un post ne doit jamais partir deux fois. Le fichier de queue est déplacé
   *avant* l'appel API, jamais après — et en CI le déplacement est **poussé**
   avant l'appel, sinon il n'existe pas pour le run suivant.
4. **Jamais de publication implicite.** `publish()` exige une visibilité, il
   n'y a pas de valeur par défaut. Un fichier de queue sans `visibility` est
   refusé. Publier depuis le terminal passe par
   `publisher.py --publish-now "<texte>" --visibility PUBLIC|CONNECTIONS`, qui
   journalise le `post_id` dans `published/`. Ne rétablis aucun défaut, même
   « raisonnable » : c'est exactement ce qui a produit l'incident du
   14/09/2026 (voir TESTING.md). Un post publié sans trace est un post qu'on
   ne sait plus supprimer — l'API ne permet pas de relire ses propres posts
   sans le scope `r_member_social`, qui n'est pas accordé.
5. **Échec bruyant.** Une publication ratée doit faire échouer le workflow et
   laisser une trace. Jamais de `except: pass`.
6. **Vérifie la doc avant de coder un appel API.** L'API LinkedIn est
   versionnée par mois. Utilise le serveur MCP Microsoft Learn
   (`https://learn.microsoft.com/api/mcp`) pour confirmer les endpoints, les
   headers et la version courante plutôt que de te fier à ta mémoire.

## Stack et contraintes

- Python 3.10+, venv local au projet (`.venv`)
- Dépendances minimales : `requests`, `python-dotenv`. N'en ajoute pas sans
  raison explicite.
- Pas de base de données, pas de serveur, pas de framework web. La file de
  publication vit dans git sous forme de fichiers JSON.
- Pas d'interface graphique. L'interface, c'est la conversation.

## État actuel

| Étape | Statut |
|---|---|
| Portail LinkedIn (app, produits, scopes) | fait |
| `auth.py` — OAuth + récupération de l'URN | fait (validé le 14/09/2026, token jusqu'au 13/11/2026) |
| `linkedin.py` — client de publication | fait — `publish`, `me`, `delete` ; phases A, B, C.8-C.9 de TESTING.md passées le 20/09/2026 |
| `publisher.py` + workflow GitHub Actions | écrit, à valider en conditions réelles |
| `mcp_server.py` — serveur MCP | à faire |

Voir `ROADMAP.md` pour le détail et les critères de validation.

## Faits établis sur l'API LinkedIn

Vérifiés au 11 septembre 2026, sur l'app `Post-Agent`.

- Scopes accordés : `openid`, `profile`, `email`, `w_member_social`
- Publier sur un profil personnel ne demande **aucune** approbation partenaire.
  Le produit self-serve « Share on LinkedIn » suffit.
- Access token : 2 mois (5 184 000 s). **Pas de refresh token** sur ce type
  d'app — la ré-authentification est manuelle et doit être anticipée, pas
  subie.
- L'URN du membre s'obtient via `GET /v2/userinfo` (champ `sub`), format
  `urn:li:person:{sub}`.
- Publication : `POST /rest/posts`. L'ancien `/v2/ugcPosts` fonctionne encore
  mais est l'ancienne surface — ne l'utilise pas pour du code neuf.
- Header `LinkedIn-Version` obligatoire, format `AAAAMM`. **Vérifie la valeur
  courante via le MCP Learn**, ne la devine pas. Au 14/09/2026 : `202608`
  (chaque version est supportée au moins un an).
- Réponse de `POST /rest/posts` : 201, identifiant du post dans l'en-tête
  `x-restli-id` (corps vide).
- Le champ `commentary` est au format *little* : les caractères
  `| { } @ [ ] ( ) < > # \ * _ ~` doivent être échappés par `\`, sinon le
  texte est tronqué silencieusement. `linkedin.py` échappe tout sauf `#`
  pour garder les hashtags actifs. **Vérifié visuellement le 20/09/2026** :
  LinkedIn restitue bien `(parenthèses)` et non `\(parenthèses\)`, et un `#`
  isolé s'affiche tel quel.
- Suppression : `DELETE /rest/posts/{urn encodé}` avec l'en-tête
  `X-RestLi-Method: DELETE`. **La doc annonce l'opération idempotente (« Post
  deletions are idempotent... will return a 204 »), l'API renvoie en réalité
  404 sur un post déjà supprimé.** Constaté le 21/09/2026 sur deux appels
  successifs au même URN. `delete()` retourne donc `False` sur 404 plutôt que
  de lever une exception : l'état visé est atteint, le post n'est plus là.
- Longueur du `commentary` : **3 000**. La page Posts API ne chiffre rien et se
  borne au code `FIELD_LENGTH_TOO_LONG` ; le nombre vient de l'ancienne surface
  (UGC Post API) et du changelog de juillet 2021 qui l'a porté de 1 300 à
  3 000. Vérifié via le MCP Learn le 21/09/2026.
- **L'unité de comptage n'est documentée nulle part.** `linkedin.py` compte en
  unités UTF-16 (`utf16_length`), pas en points de code : la plateforme est en
  Java, et c'est la mesure la plus stricte des deux. Un emoji hors BMP vaut 1
  pour `len()` et 2 en UTF-16 — 1 501 emoji passeraient un contrôle en `len()`
  tout en dépassant la limite. Mesuré sur le texte **échappé**, seul à partir
  sur le réseau. Établi empiriquement le 21/09/2026 : 3 000 unités UTF-16 avec
  emoji sont acceptées. Reste indéterminé si LinkedIn compte en points de code
  (notre contrôle serait alors un peu trop strict) — un post de 3 000 points de
  code et 3 003 unités UTF-16 trancherait.
- Header `X-Restli-Protocol-Version: 2.0.0` requis.
- Limite : environ 150 posts par membre et par jour. Sans objet ici.
- **Relire ses propres posts est impossible** avec les scopes accordés :
  `GET /rest/posts?q=author` renvoie 403 `ACCESS_DENIED`, il exige
  `r_member_social`, qui est restreint. Conséquence directe : un `post_id`
  perdu est définitivement perdu, et le post ne peut plus être supprimé que
  depuis l'interface web. D'où la journalisation obligatoire.

## Hors périmètre, décidé

- **Gestion du profil** (bio, titre, expériences) : aucune API ne le permet.
  Ne propose jamais de solution à ça.
- **Analytics** : demande une autorisation séparée. Reporté.
- **X / Twitter** : depuis février 2026, plus de palier gratuit. Facturation à
  l'appel, avec une forte surtaxe sur les posts contenant un lien. Décision
  reportée et volontairement découplée de l'architecture.
- **Interface web** : jamais.

## Style de travail attendu

- Explique les décisions de conception, pas seulement le code.
- Signale les compromis plutôt que de les masquer.
- Préfère 50 lignes lisibles à 200 lignes génériques. Ce projet doit rester
  compréhensible dans six mois.
- Ne code pas l'étape suivante tant que la précédente n'est pas validée en
  conditions réelles.
