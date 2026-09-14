# ROADMAP.md

Une étape n'est close que lorsque son critère de validation est vérifié en
conditions réelles. Ne commence pas la suivante avant.

## Étape 0 — Portail LinkedIn ✅

App `Post-Agent` créée, produits « Sign In with LinkedIn using OpenID Connect »
et « Share on LinkedIn » provisionnés, redirect URL
`http://localhost:8000/callback` enregistrée.

Scopes obtenus : `openid`, `profile`, `email`, `w_member_social`.

## Étape 1 — Authentification ⏳

`auth.py` est écrit, pas encore validé.

**Validation :** `python auth.py` affiche le nom du membre et un URN de la
forme `urn:li:person:...`, et `token.json` existe en permissions 600.

Pièges connus : `redirect_uri_mismatch` si l'URL diffère d'un caractère ;
`invalid_client` si le secret est mal copié.

## Étape 2 — Client de publication

`linkedin.py` : deux fonctions, `publish(text, visibility)` et `me()`.
Lecture du token par variable d'environnement puis fichier (voir
ARCHITECTURE.md).

**Avant d'écrire l'appel :** interroger le MCP Microsoft Learn pour confirmer
la version courante de l'en-tête `LinkedIn-Version` et la forme exacte du
payload `/rest/posts`.

**Validation :** un post « test » apparaît réellement sur le profil, et son
`post_id` est retourné.

## Étape 3 — Planification

`publisher.py` + `.github/workflows/publish.yml` (cron `*/15 * * * *`).
Secrets GitHub : `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_PERSON_URN`.

**Validation :** un post daté à +20 minutes part tout seul, poste éteint. Puis
relancer le workflow à la main sur la même queue ne republie rien (NF5).

À inclure dès cette étape : alerte si le token expire dans moins de 7 jours.

## Étape 4 — Serveur MCP

`mcp_server.py` exposant `publish_now`, `schedule_post`, `list_queue`,
`cancel_post`, `auth_status`.

`schedule_post` n'appelle pas LinkedIn : il écrit un fichier dans `queue/` et
le commite. La séparation est volontaire.

**Validation :** programmer un post depuis la conversation, sans toucher au
terminal.

## Étape 5 — Confort

Images (F9), modèles de posts récurrents, résumé hebdomadaire de la file.

## Reporté, volontairement

- **X / Twitter** : décision économique, pas technique. À reprendre quand le
  volume de publication justifiera d'arbitrer entre le coût par appel et la
  publication manuelle.
- **Analytics** : demande une autorisation LinkedIn séparée.
- **Multi-tenant** : réécriture du cœur pour DEAL, pas un portage. `linkedin.py`
  doit rester importable sans rien traîner derrière lui.
