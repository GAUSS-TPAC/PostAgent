# clock — horloge externe

Cloudflare Worker qui déclenche le workflow de publication toutes les
15 minutes via `repository_dispatch`.

## Pourquoi

Le cron GitHub Actions est traité « au mieux » et dérive massivement sur les
dépôts publics : 12 exécutions mesurées sur 40 heures au lieu des 160
attendues, avec des écarts de 2 h 12 à 5 h 33. NF2 est intenable avec lui
seul.

Ce Worker fournit une horloge fiable. GitHub garde son rôle d'exécuteur et de
stockage.

**Le cron GitHub est conservé en secours.** Si le Worker cesse de fonctionner,
le cron reprend avec sa dérive, les posts dépassent `STALE_AFTER` (3 h),
partent dans `stale/` et le workflow passe au rouge. La panne de l'horloge se
signale donc d'elle-même — c'est le mécanisme de péremption qui sert de
sonde de santé.

## Déploiement

Le déploiement se fait **par la CI**, pas depuis le poste de travail :
wrangler enchaîne plusieurs appels à l'API Cloudflare par déploiement, ce
qu'une connexion en partage mobile (~2,3 s par requête) ne supporte pas.

`.github/workflows/deploy-clock.yml` déploie à chaque push touchant `clock/`,
et à la demande depuis l'onglet Actions. Il dépose aussi les deux secrets du
Worker à chaque déploiement : ils n'ont pas à être posés à la main.

### Les quatre secrets du dépôt

À créer dans **Settings → Secrets and variables → Actions → New repository
secret** du dépôt `PostAgent`.

| Secret du dépôt | Où l'obtenir | Devient, côté Worker |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` | dash.cloudflare.com → My Profile → API Tokens → Create Token → gabarit **Edit Cloudflare Workers** | — (authentifie le déploiement) |
| `CLOUDFLARE_ACCOUNT_ID` | dash.cloudflare.com → Workers & Pages → colonne de droite, **Account ID** | — (cible du déploiement) |
| `DISPATCH_PAT` | GitHub → Settings → Developer settings → Personal access tokens → Fine-grained | secret `DISPATCH_TOKEN` |
| `CLOCK_TRIGGER_KEY` | une chaîne aléatoire de ton choix, par exemple `openssl rand -hex 32` | secret `TRIGGER_KEY` |

Le nom change en route pour `DISPATCH_PAT` : **GitHub refuse tout secret dont
le nom commence par `GITHUB_`**, d'où `DISPATCH_PAT` dans le dépôt et
`DISPATCH_TOKEN` dans le Worker.

### Le jeton GitHub (`DISPATCH_PAT`)

| Champ | Valeur |
|---|---|
| Repository access | Only select repositories → `PostAgent` |
| Permissions → Contents | **Read and write** |
| Expiration | 1 an, date à noter |

`repository_dispatch` exige un accès en écriture au dépôt. Ce jeton expire :
il rejoint le token LinkedIn dans la liste des échéances à surveiller.

### Coût

Plan gratuit : 100 000 requêtes par jour. Ce Worker en consomme 96.
Aucune carte bancaire requise.

## Vérification

Déclenchement manuel, sans attendre le cron :

```bash
curl -X POST https://post-agent-clock.<ton-sous-domaine>.workers.dev/trigger \
     -H "X-Trigger-Key: <CLOCK_TRIGGER_KEY>"
```

Réponse attendue : `dispatch émis`. Le workflow de publication doit apparaître
dans l'onglet Actions dans la minute, avec `repository_dispatch` comme
déclencheur.

## Développement local

**Wrangler 4.135 exige Node.js 22 ou plus.** Sur Node 20, toute commande
wrangler s'arrête net :

```
Wrangler requires at least Node.js v22.0.0. You are using v20.20.2.
```

Le déploiement n'en dépend pas : la CI installe Node 22 elle-même. Seul le
test local est concerné. Pour le faire tourner :

```bash
nvm install 22 && nvm use 22
npx wrangler dev --test-scheduled
curl "http://localhost:8787/__scheduled?cron=*/15+*+*+*+*"
```

La `compatibility_date` doit rester inférieure ou égale à la date maximale
acceptée par le runtime embarqué, sinon le serveur refuse de démarrer :

```
This Worker requires compatibility date "...", but the newest date
supported by this server binary is "...".
```

Au 21/09/2026, avec wrangler 4.135.0, ce maximum est le **2026-09-25** — la
date du projet, 2026-09-21, passe. Pour le vérifier sans Node 22, interroger
directement le runtime :

```bash
node_modules/@cloudflare/workerd-linux-64/bin/workerd serve <config.capnp>
```

## Journaux

```bash
npx wrangler tail
```

## Ce que ce Worker ne fait pas

Il ne lit pas la file, ne décide pas ce qui doit partir, ne connaît pas
LinkedIn et ne détient aucun jeton LinkedIn. Il tire, `publisher.py` décide.

Cette séparation est volontaire : elle garde le secret LinkedIn dans un seul
endroit (GitHub Secrets) et laisse l'horloge remplaçable sans toucher au reste.
