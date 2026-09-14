# linkedin-agent

Publier sur LinkedIn depuis une conversation, avec une planification qui tourne
sans serveur.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Remplis `.env` avec le Client ID et le Client Secret de ton app, disponibles
dans l'onglet Auth sur `linkedin.com/developers`.

## Authentification

```bash
python auth.py
```

Le navigateur s'ouvre, tu autorises l'application, le script récupère le token
et ton identifiant de membre dans `token.json`.

Le token vaut 2 mois et n'est pas renouvelable automatiquement. Pour connaître
le temps restant :

```bash
python auth.py --status
```

## Documentation

| Fichier | Contenu |
|---|---|
| `CLAUDE.md` | Contexte et règles pour l'assistant de code |
| `SPEC.md` | Besoins fonctionnels et non fonctionnels |
| `ARCHITECTURE.md` | Conception, cycle de vie d'un post, décisions écartées |
| `ROADMAP.md` | Étapes et critères de validation |

## Sécurité

`.env` et `token.json` sont exclus du dépôt et ne doivent jamais y entrer. Le
token permet de publier en ton nom pendant deux mois.

Ce projet n'utilise que l'API officielle LinkedIn. Aucun scraping, aucune
automatisation de navigateur.
