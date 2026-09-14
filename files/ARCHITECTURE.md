# ARCHITECTURE.md

## Vue d'ensemble

Le système a deux points d'entrée indépendants qui partagent le même cœur.

```
  Conversation (Claude Desktop)          GitHub Actions (cron 15 min)
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
avec gestion des secrets intégrée. Le compromis assumé : le cron GitHub peut
dériver de 5 à 15 minutes aux heures de pointe. Sans importance pour du post
LinkedIn.

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

Le nom de fichier porte l'horodatage prévu. Le publisher traite tout fichier
dont l'horodatage est passé.

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
