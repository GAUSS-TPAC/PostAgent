# PRODUIT.md

Décision du 02/10/2026 : **PostAgent devient un produit vendable de Sentinelle
Services.** Alan reste l'utilisateur principal, mais en tant que premier
client, pas comme un cas à part. Ce document fixe ce qui change, ce qui ne
change pas, et l'ordre des travaux.

## Ce qui change

| Avant | Désormais |
|---|---|
| Outil personnel, un seul compte LinkedIn | Plusieurs clients, chacun son compte |
| « Interface web : jamais » | Une interface web, pour ce que la conversation fait mal |
| Utilisateur technique (terminal, git, GPG) | Utilisateur non technique : aucun terminal, jamais |
| Coût nul (NF1) | Coût **marginal** quasi nul par client ; un socle payant modeste est accepté |

### Ce que l'interface fait, et ne fait pas

La conversation reste le cœur du produit et ce qui le distingue. L'interface
couvre seulement ce qu'une conversation fait mal :

- **se connecter** : « Se connecter avec LinkedIn », un clic ;
- **voir** : calendrier des posts programmés, publiés et en échec ;
- **trancher** : un post bloqué ou périmé apparaît avec une question claire
  et deux boutons, au lieu d'un fichier à déplacer dans git ;
- **renouveler** l'accès LinkedIn avant l'expiration ;
- **écrire sans assistant** : un éditeur simple, pour le client qui n'a pas
  d'assistant IA (voir les questions ouvertes).

## Ce qui ne change pas

Les règles de `CLAUDE.md` valent pour chaque client, et pèsent plus lourd :
un incident touche désormais le profil de quelqu'un d'autre.

- API officielle uniquement.
- **Visibilité toujours explicite**, y compris dans l'interface : pas de
  case présélectionnée.
- Un post ne part jamais deux fois ; chaque `post_id` est conservé.
- Échec visible, pour le client **et** pour Sentinelle.
- Le cœur LinkedIn reste isolé de l'orchestration (NF8).

## Faits LinkedIn qui conditionnent la vente

Vérifiés sur Microsoft Learn le 02/10/2026.

- **Share on LinkedIn est une permission ouverte** : n'importe quel membre
  peut autoriser l'app, sans approbation partenaire. Le modèle multi-clients
  est donc possible sur l'app actuelle.
- **Quotas** : 150 requêtes par membre et par jour, 100 000 par application.
  Le quota d'application ne sera pas un frein avant longtemps.
- **Pas de refresh token** : réservés aux partenaires approuvés du Marketing
  Developer Platform. Chaque client devra se reconnecter tous les 60 jours.
  Atténuation documentée : si le client relance l'autorisation **avant**
  l'expiration et qu'il est connecté à LinkedIn, l'écran d'autorisation est
  sauté — un clic suffit. D'où le bouton « Renouveler » envoyé à J−7, jamais
  après l'échéance.
- **Publier au nom d'une page entreprise** relève d'une autre API (Community
  Management), soumise à approbation. Hors périmètre tant que la cible n'est
  pas tranchée.
- L'usage commercial est régi par les **LinkedIn API Terms of Use**. À lire
  en entier avant la première vente : stockage des tokens, données
  conservées, présentation de la marque LinkedIn.

## P0 — lecture des API Terms of Use

Lues en entier le 04/10/2026 (version révisée le 13 décembre 2022,
`linkedin.com/legal/l/api-terms-of-use`). **P0 n'est pas validée : trois
clauses peuvent bloquer la vente sur l'app actuelle.** L'app `Post-Agent`
relève du « Self-Serve API Program » ; ce sont ses conditions qui coincent,
pas la technique — « possible sur l'app actuelle » plus haut ne vaut que
pour la technique.

| Clause | Texte | Portée |
|---|---|---|
| §3.1, dernier point | interdit de « use the Content or the APIs to automate posting on the LinkedIn Services » | touche le cœur du produit. Reste à savoir si publier à l'heure choisie un texte écrit et validé par le membre est « automatiser » : le texte ne le dit pas. Concerne aussi l'instance d'Alan. |
| §1.4, critère 5 | le Self-Serve exige que l'application « DOES NOT rely on access to the APIs as a fundamental aspect of your business » | un produit vendu dont la seule fonction est de publier sur LinkedIn en dépend, par construction |
| §8.2 | « You may not charge your Users incremental fees for access to our Content or APIs » | à lire avant de fixer un prix (P7) : facturer le service, pas l'accès |

§1.4 renvoie, quand ses critères ne sont pas remplis, vers un « Vetted API
Program » ou un « Partner Program ». Piste à vérifier : la Community
Management API, réservée aux organisations légalement enregistrées, pour un
usage commercial, avec page entreprise vérifiée — donc Sentinelle Services,
et d'autres conditions (Marketing API Terms), à lire à leur tour.

Obligations non bloquantes, mais qui s'imposent à la conception :

- **§4.2** : les tokens OAuth et l'identifiant du membre peuvent être
  stockés. **§4.3** : nom et photo, seulement avec consentement.
- **§4.4** : suppression immédiate de tout, token compris, à la demande du
  client ou à la fermeture de son compte.
- **§5.1** : conditions d'utilisation et politique de confidentialité
  propres, visibles là où le client accède au produit.
- **§5.2** : consentement explicite avant la connexion LinkedIn (quelles
  données, quand, comment retirer, comment supprimer), à **redemander à
  chaque expiration du token** — le bouton « Renouveler » doit le porter.
- **§7.1** : chiffrement en transit et au repos, procédure écrite de
  réponse aux vulnérabilités, incident signalé à LinkedIn **sous 24 h**,
  aucune déclaration publique sans leur accord.
- **§6.1** : marque LinkedIn utilisable dans le produit seulement ; tout
  support externe (site, publicité) qui la montre passe par une
  approbation préalable.
- **§11.3** : LinkedIn peut couper l'accès à tout moment, sans motif.
- **§14.7** : pas de cession sans accord écrit. L'app est enregistrée au
  nom d'Alan : son rattachement à Sentinelle Services est à faire
  proprement, pas à supposer.

Ceci est une lecture, pas un avis juridique.

## Ce qui ne passe pas à l'échelle

| Aujourd'hui | Problème avec des clients |
|---|---|
| File dans git, un dépôt | un dépôt par client est ingérable ; le contenu des clients ne doit pas vivre dans un dépôt |
| Token dans un secret GitHub | un secret par client, posé à la main |
| `auth.py` avec retour sur `localhost` | impossible pour un client : il faut une URL de retour publique |
| Serveur MCP local (stdio) | le client n'a ni Python, ni dépôt |
| GitHub Actions comme exécuteur | les jobs par client et le contenu des clients n'ont rien à faire dans la CI |
| Commits signés GPG | sans objet hors du poste d'Alan |

## Architecture cible recommandée

Tout sur **Cloudflare**, déjà utilisé pour l'horloge :

```
  Client (navigateur)     Client (assistant IA)
         |                        |
   Interface web            Serveur MCP distant (OAuth)
         |                        |
         +-----------+------------+
                     |
               Worker (API)  ── OAuth LinkedIn, callback public
                     |
          +----------+-----------+
          |                      |
   D1 (base SQL)          Durable Object par client
   clients, posts,        alarme à l'heure exacte,
   journal des post_id    verrou de publication
                     |
               cœur LinkedIn  ──►  API /rest/posts
```

Pourquoi ce choix :

- **L'alarme d'un Durable Object remplace le cron, la fenêtre d'attente et
  la péremption « par sondage ».** Elle réveille le client à l'heure du post,
  et l'état de l'objet est transactionnel : c'est le verrou `publishing/`,
  mais fiable entre exécutions concurrentes. Le problème le plus dur du
  projet (NF5) devient plus simple, pas plus compliqué.
- **Le serveur MCP distant garde la conversation** : le client ajoute
  PostAgent comme connecteur dans son assistant, sans rien installer.
- Pas de serveur à administrer, facturation à l'usage, et un seul fournisseur
  de plus que LinkedIn.

### Le compromis à trancher : le langage du cœur

Les Workers exécutent du JavaScript/TypeScript. `linkedin.py` devrait donc
être **porté en TypeScript** (~250 lignes, mais chaque règle est documentée et
testée : échappement, comptage UTF-16, 404 sur suppression). L'alternative,
garder Python sur un autre hébergeur, réintroduit un serveur à maintenir.
Recommandation : porter, et garder la version Python pour l'instance d'Alan
jusqu'à sa migration.

### Données et sécurité

- Tokens LinkedIn **chiffrés** en base, clé hors base (secret du Worker).
- Aucun texte de post dans les journaux techniques.
- Suppression complète d'un client sur demande : tokens, posts, journal.
- Conformité à la loi de protection des données applicable aux clients visés
  — à vérifier avant la première vente.

## Étapes

Même règle qu'au `ROADMAP.md` : une étape n'est close que validée en
conditions réelles.

| Étape | Contenu | Validation |
|---|---|---|
| P0 | Lire les API Terms of Use ; rattacher l'app LinkedIn à la page Sentinelle Services | aucune clause bloquante identifiée, notée ici — **lu le 04/10/2026, trois clauses à lever, voir plus haut** |
| P1 | Cœur porté en TypeScript, testé avec un verrou `DRY_RUN` équivalent | phases B et C de `TESTING.md` rejouées, aucune publication |
| P2 | Connexion LinkedIn multi-clients, tokens chiffrés en base | deux comptes connectés, `me()` correct pour chacun |
| P3 | Programmation par Durable Object + journal en D1 | phase E rejouée, dont E.4/E.5 (idempotence) |
| P4 | Interface : calendrier, décisions, renouvellement | un non-technicien programme et annule un post sans aide |
| P5 | Serveur MCP distant | programmer depuis un assistant, sans rien installer |
| P6 | Migration d'Alan, arrêt de la file git | ses posts partent par la nouvelle chaîne une semaine sans incident |
| P7 | Facturation | premier client payant |

Le système actuel reste en service jusqu'à P6. Rien ne l'arrête avant que
la relève soit prouvée.

## Questions ouvertes, à trancher par Alan

1. **Cible** : particuliers et indépendants (profil personnel, possible
   aujourd'hui) ou entreprises (pages, approbation LinkedIn nécessaire) ?
2. **Rédaction** : le client apporte son propre assistant (connecteur MCP),
   ou PostAgent inclut la rédaction IA (coût par client à intégrer au prix) ?
3. **Prix et facturation** : abonnement, palier gratuit, moyen de paiement
   adapté au marché visé.
4. **Marque** : PostAgent seul, ou « PostAgent par Sentinelle Services »
   partout ?
