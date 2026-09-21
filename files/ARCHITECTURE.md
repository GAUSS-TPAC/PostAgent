# ARCHITECTURE.md

## Vue d'ensemble

Le système a deux points d'entrée indépendants qui partagent le même cœur.

```
  Conversation (Claude Desktop)          GitHub Actions (cron + dispatch)
             |                                      |
      mcp_server.py                           publisher.py
             |                                      |
             +----------------+---------------------+
                              |
                        linkedin.py          <- cœur métier, sans état
                              |
                     API LinkedIn /rest/posts
```

`linkedin.py` ne connaît ni la queue, ni MCP, ni GitHub Actions. Il expose deux
fonctions : publier un texte, et lire l'identité du membre. C'est ce qui rend
NF8 tenable — la version multi-tenant de DEAL réutilisera ce fichier tel quel.

## Pourquoi GitHub Actions comme moteur de planification

Postiz et les outils équivalents s'appuient sur un moteur de workflow durable
(Temporal) qui doit tourner en permanence. Le poste de travail visé dort la
nuit et dépend d'une connexion partagée : il ne peut structurellement pas
garantir qu'un post parte à 9h.

GitHub Actions fournit un exécuteur permanent, gratuit dans les quotas visés,
avec gestion des secrets intégrée.

**Le cron GitHub n'est pas une horloge.** Mesuré sur ce dépôt du 16 au
18 septembre 2026, avec `*/15 * * * *` : 12 exécutions en 40 heures au lieu
de 160, et des écarts de **2 h 12 à 5 h 33** entre deux runs. GitHub traite
les événements planifiés au mieux et supprime les exécutions en période de
charge, d'autant plus sur un dépôt public. L'estimation initiale de « 5 à
15 minutes de dérive » était fausse d'un ordre de grandeur.

Conséquence de conception : **l'horloge est déplacée dans le publisher.**
Un run qui démarre en avance attend l'heure exacte du post, dans la limite de
20 minutes (`WAIT_WINDOW`). Le cron ne décide plus de l'heure de publication,
il ne fait qu'offrir des occasions d'agir.

Pourquoi 20 minutes et pas davantage : l'attente doit rester inférieure à
l'intervalle réel entre deux runs (2 h au minimum observé). Une fenêtre de
plusieurs heures ferait convoiter le même post par deux runs successifs, et
transformerait la concurrence en problème quotidien plutôt qu'en cas
théorique.

Le workflow accepte aussi `repository_dispatch`, pour qu'une horloge externe
précise (un Cloudflare Worker) puisse le déclencher à l'heure voulue. Le cron
reste en place comme filet de sécurité.

## Pourquoi la queue vit dans git

Une base de données imposerait un serveur, donc un coût, donc la mort de NF1.
Des fichiers JSON versionnés donnent gratuitement l'historique, l'audit, la
récupération après erreur, et une édition triviale à la main. Le volume visé
(quelques posts par jour) rend toute autre solution disproportionnée.

## Cycle de vie d'un post

```
queue/2026-09-15T0900.json     programmé, en attente
        |
        |  publisher.py : le fichier est déplacé AVANT l'appel API
        v
publishing/2026-09-15T0900.json  en cours, verrou implicite
        |
        +-- succès --> published/2026-09-15T0900.json  (+ post_id LinkedIn)
        |
        +-- échec  --> reste ici, workflow en erreur, arbitrage humain
```

### Ce que le verrou par fichier ne protège pas

Le déplacement `queue/` → `publishing/` sérialise les traitements **au sein
d'un même clone**. Entre deux runners concurrents, il ne protège rien : chacun
a son propre clone du dépôt, chacun voit le fichier dans `queue/`, chacun le
déplace chez lui, et les deux publient. Le conflit n'apparaît qu'au `push`,
après les appels API — donc trop tard : le doublon est déjà sur le profil.

D'où le garde-fou au niveau de l'exécuteur, dans le workflow :

```yaml
concurrency:
  group: publisher
  cancel-in-progress: false
```

`cancel-in-progress: false` est le point important. Annuler un run en cours
pourrait l'interrompre entre le push du verrou et l'appel API, laissant un
fichier bloqué dans `publishing/` pour rien. On préfère faire attendre le
second run.

Le chevauchement est aujourd'hui impossible : l'écart minimum mesuré entre
deux runs (2 h 12) dépasse largement la fenêtre d'attente (20 min). Mais avec
le `repository_dispatch` de l'horloge externe, les déclenchements deviendront
fréquents et rapprochés, et le chevauchement deviendra la norme. Le garde-fou
est en place avant d'en avoir besoin, pas après le premier doublon.

### Péremption

Un post dû depuis plus de 3 heures (`STALE_AFTER`) n'est pas publié : il part
dans `stale/` et le workflow échoue. Publier un post des heures après l'heure
voulue est un dégât public, pas un rattrapage — le créneau d'audience visé
n'existe plus, et l'auteur découvre la publication après coup. La décision de
republier revient à l'humain, qui n'a qu'à redater le fichier et le remettre
dans `queue/`.

Le nom de fichier porte l'horodatage prévu, mais le publisher se fie au champ
`scheduled_at`, qui porte le fuseau horaire. Un fichier sans fuseau, ou
illisible, est mis de côté dans `publishing/` : le laisser dans `queue/`
ferait échouer le workflow toutes les 15 minutes, et l'alerte se noierait dans
son propre bruit.

En CI, le verrou réel n'est pas le déplacement mais le **push** qui le suit :
chaque run repart du dépôt distant, donc un déplacement non poussé n'existe
pas. Si ce push échoue, rien n'est publié.

Format d'un fichier de queue :

```json
{
  "text": "Le contenu du post.",
  "scheduled_at": "2026-09-15T09:00:00+01:00",
  "visibility": "PUBLIC",
  "created_at": "2026-09-11T22:14:00+01:00"
}
```

Après publication, le fichier est enrichi de `post_id` et `published_at`.

## Arborescence

```
linkedin-agent/
├── CLAUDE.md  SPEC.md  ARCHITECTURE.md  ROADMAP.md  README.md
├── auth.py                  # OAuth, écrit token.json
├── linkedin.py              # cœur métier, sans état
├── publisher.py             # exécuté par GitHub Actions
├── mcp_server.py            # outils exposés à l'assistant
├── queue/  publishing/  published/
└── .github/workflows/publish.yml
```

## Authentification en deux contextes

En local, `auth.py` écrit `token.json`, lu par `linkedin.py`.

En CI, il n'y a pas de `token.json`. Le token vient de la variable
d'environnement `LINKEDIN_ACCESS_TOKEN` (GitHub Secret), l'URN de
`LINKEDIN_PERSON_URN`. `linkedin.py` doit donc lire le token dans cet ordre :
variable d'environnement d'abord, fichier ensuite. Cette hiérarchie est ce qui
permet au même code de tourner dans les deux mondes.

## Décisions écartées, et pourquoi

| Option | Rejetée parce que |
|---|---|
| Postiz self-hosted | Stack lourde, exige un serveur permanent, et ne supprime pas le coût X |
| Fork de Postiz | AGPL-3.0, monorepo pnpm : le temps passerait dans leurs abstractions |
| Spring Boot | Démarrage JVM 96 fois par jour, quota Actions consommé pour rien |
| Base de données | Impose un serveur, contredit NF1 |
| Refresh token automatique | Non disponible sur ce type d'app LinkedIn |
