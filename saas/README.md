# PostAgent — le SaaS

Version multi-membres de PostAgent : chacun se connecte avec LinkedIn, écrit
ou fait rédiger un post, y joint une image, un PDF ou un carrousel, choisit
la visibilité et l'heure. Un Worker Cloudflare publie à l'heure dite.

L'instance d'Alan (`publisher.py`, GitHub Actions, la file dans git) n'est
pas touchée par ce dossier et reste en service.

## Ce qui est fait, ce qui ne l'est pas

| | État |
|---|---|
| Connexion LinkedIn, sur invitation, consentement à chaque passage | fait, testé avec un faux LinkedIn |
| Jetons chiffrés en base, clé hors base | fait, testé |
| Post texte, image, PDF, carrousel généré (2 à 10 pages) | fait, testé avec un faux LinkedIn |
| Ordonnanceur : une publication par post, jamais de rejeu, péremption à 3 h | fait, testé (dont deux exécutions concurrentes) |
| Cloisonnement entre membres | fait, testé |
| Interface : composer, programmer, annuler, trancher, renouveler, supprimer son compte | fait, vue à l'écran en local |
| Rédaction assistée (« un post sur le RAG », avec carrousel) | fait, testé avec un faux modèle ; **jamais appelé pour de vrai** |
| Statistiques d'un post | codé ; LinkedIn répondra 403 tant que l'app n'a pas `r_member_postAnalytics` |
| **Une vraie publication par ce chemin** | **jamais faite** : aucun test ne publie |
| Vidéo | non : demande un stockage d'objets (R2) et l'envoi en plusieurs parties |
| Images générées par IA | non |
| Serveur MCP distant (piloter depuis un assistant) | non |
| Limite d'usage de la rédaction assistée par membre | non : chaque brouillon coûte un appel au modèle |
| Facturation | non |

Limites connues : un fichier déposé ne dépasse pas 1,5 Mo (ligne D1) ; le
carrousel n'affiche pas les emoji (police Helvetica standard).

## Le verrou de publication

Rien ne part vers LinkedIn sans `POSTAGENT_LIVE = "1"`. Cette variable
n'existe que dans le bloc `[env.production]` de `wrangler.toml`. En local et
en test, l'ordonnanceur compte les posts dus et n'en réserve aucun.

## Travailler en local

Node 22 est nécessaire (`nvm use 22`).

```bash
npm install
npm test                                   # 25 tests, aucun appel réseau
cp .dev.vars.example .dev.vars
npx wrangler d1 execute postagent-dev --local --file=schema.sql
npx wrangler dev                           # http://localhost:8787, verrou fermé
```

## Mise en ligne

La base de production existe déjà (`postagent`, région WEUR, schéma appliqué
le 12/10/2026). Il reste quatre gestes, qui demandent ton compte et tes
secrets :

1. **Une adresse.** Dans le tableau de bord Cloudflare, Workers & Pages :
   enregistrer le sous-domaine `workers.dev` du compte (il n'en a pas), ou
   rattacher un domaine. L'adresse sera `https://postagent.<sous-domaine>.workers.dev`.
2. **LinkedIn.** Dans le portail développeur, onglet Auth de l'app : ajouter
   l'URL de retour `https://postagent.<sous-domaine>.workers.dev/auth/callback`,
   au caractère près.
3. **Déployer**, puis poser les secrets :

   ```bash
   npm run deploy
   npx wrangler secret put LINKEDIN_CLIENT_ID --env production
   npx wrangler secret put LINKEDIN_CLIENT_SECRET --env production
   openssl rand -base64 32 | npx wrangler secret put TOKEN_KEY --env production
   npx wrangler secret put INVITE_CODE --env production      # le code à donner à tes invités
   npx wrangler secret put ANTHROPIC_API_KEY --env production # facultatif : rédaction assistée
   ```

   `TOKEN_KEY` ne doit jamais changer ensuite : les jetons déjà enregistrés
   deviendraient illisibles et chacun devrait se reconnecter.
4. **Premier essai, avec toi devant ton profil** : te connecter, programmer
   un post en « Mes relations » à quelques minutes, le voir partir, le
   supprimer. C'est la première publication réelle de ce code.

Dès l'étape 3, la publication est réelle pour tout membre connecté.

## Avant d'ouvrir à d'autres que toi

Voir `files/PRODUIT.md`, section P0. Ce service, tel qu'il est construit,
publie pour le compte d'autres membres depuis une seule app LinkedIn : c'est
la forme que la lecture des API Terms of Use avait écartée (§1.4, §3.1,
§8.2). La voie prévue par LinkedIn pour cet usage est la Community
Management API, qui apporte aussi les statistiques. Entre amis et sans
facturer, l'exposition est faible ; vendu, elle ne l'est plus.

## Plan du code

| Fichier | Rôle |
|---|---|
| `src/linkedin.js` | client LinkedIn sans état : publier, envoyer un média, supprimer, statistiques |
| `src/carousel.js` | pages -> PDF, sans dépendance |
| `src/generate.js` | sujet -> brouillon (API Claude) |
| `src/scheduler.js` | publie les posts dus, chaque minute |
| `src/store.js` | tout le SQL, cloisonné par membre |
| `src/oauth.js` | connexion LinkedIn, sessions |
| `src/api.js`, `src/index.js` | API de l'interface, routage |
| `src/crypto.js` | chiffrement des jetons |
| `public/` | l'interface, servie en fichiers statiques |
| `schema.sql` | la base |
| `docs/` | cahier des charges et guide d'utilisation (Markdown, PDF, diagrammes, captures) |

Les PDF de `docs/` se régénèrent par `python3 saas/docs/build_docs.py`
(pandoc et google-chrome). Les diagrammes sont décrits dans
`docs/diagrammes.py` ; les captures d'écran viennent de l'application
lancée en local avec des données de démonstration.
