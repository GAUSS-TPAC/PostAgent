# PRODUIT.md

Décision du 02/10/2026 : **PostAgent devient un produit vendable de Sentinelle
Services.** Révisée le 04/10/2026, après lecture des API Terms of Use (P0) :
**on ne vend pas un service qui publie, on vend le logiciel et sa mise en
place.** Chaque client fait tourner sa propre instance, avec sa propre app
LinkedIn, enregistrée à son nom. Alan en est le premier client : son
instance est celle de ce dépôt.

Ce document fixe ce qui est vendu, ce qui ne l'est jamais, ce qui change et
l'ordre des travaux.

## La forme : auto-hébergée

| | Service hébergé (abandonné le 04/10) | Logiciel auto-hébergé (retenu) |
|---|---|---|
| App LinkedIn | une seule, celle de Sentinelle | une par client, à son nom |
| Jeton d'accès LinkedIn | — | reste chez le client, dans ses propres secrets |
| Qui publie | Sentinelle, au nom du client | le client, par son instance |
| Contenu des posts | — | dans le dépôt du client |
| Ce que Sentinelle détient | — | **rien** : ni jeton, ni contenu, ni accès à l'instance |

Précédent retenu par Alan : Postiz, même catégorie, même modèle (non
revérifié par la boucle du 04/10).

### Ce qui est vendu

- **le logiciel** : ce dépôt, rendu installable ;
- **l'installation** : accompagner le client jusqu'à son premier post
  programmé ;
- **l'accompagnement** : renouvellement, mises à jour, dépannage ;
- **les gabarits** : modèles de posts, guide d'usage (`GUIDE.md`).

### Ce qui n'est jamais vendu

- **L'accès à l'API LinkedIn** (§8.2 : « You may not charge your Users
  incremental fees for access to our Content or APIs »). Aucun prix au post,
  à l'appel ou au volume publié. Le prix porte sur le logiciel et le temps
  passé.
- Une garantie de publication : LinkedIn peut couper l'accès d'une app à
  tout moment, sans motif (§11.3). Le client doit le lire avant d'acheter.

### Ce que le client enregistre lui-même

| Élément | Où | Pourquoi lui |
|---|---|---|
| App LinkedIn (« Share on LinkedIn », « Sign In with LinkedIn ») | portail développeur LinkedIn, sous son compte | c'est lui qui accepte les API Terms of Use, pour son propre usage |
| Identifiants de l'app et jeton d'accès | ses propres secrets (aujourd'hui : `.env` local et secrets de son dépôt GitHub) | Sentinelle ne doit jamais les voir |
| Dépôt de la file | son compte GitHub | son contenu lui appartient |
| Horloge | son compte Cloudflare | un Worker par instance, aucun en commun |

Règle d'installation qui en découle : **le client saisit lui-même chaque
secret.** Un partage d'écran où le jeton apparaît, un secret dicté ou copié
par Sentinelle, et le modèle ne tient plus.

## Ce qui change

| Avant | Désormais |
|---|---|
| Outil personnel d'Alan | Le même outil, installé chez chaque client |
| « Interface web : jamais » | Une interface par instance, pour ce que la conversation fait mal |
| Utilisateur technique (terminal, git, GPG) | Utilisateur non technique **après** l'installation ; l'installation est accompagnée |
| Coût nul (NF1) | Coût d'exploitation nul pour Sentinelle ; chaque client porte le sien, quasi nul |

### Ce que l'interface fait, et ne fait pas

La conversation reste le cœur du produit et ce qui le distingue. L'interface
couvre seulement ce qu'une conversation fait mal :

- **voir** : calendrier des posts programmés, publiés et en échec ;
- **trancher** : un post bloqué ou périmé apparaît avec une question claire
  et deux boutons, au lieu d'un fichier à déplacer dans git ;
- **renouveler** l'accès LinkedIn avant l'expiration ;
- **écrire sans assistant** : un éditeur simple, pour le client qui n'a pas
  d'assistant IA (voir les questions ouvertes).

## Ce qui ne change pas

Les règles de `CLAUDE.md` valent pour chaque instance, et pèsent plus lourd :
un incident touche désormais le profil de quelqu'un d'autre.

- API officielle uniquement.
- **Visibilité toujours explicite**, y compris dans l'interface : pas de
  case présélectionnée.
- Un post ne part jamais deux fois ; chaque `post_id` est conservé.
- Échec visible, pour le client — et pour Sentinelle seulement s'il a
  choisi de l'en avertir.
- Le cœur LinkedIn reste isolé de l'orchestration (NF8).

## Faits LinkedIn qui conditionnent la vente

Vérifiés sur Microsoft Learn le 02/10/2026.

- **Share on LinkedIn est une permission ouverte** : n'importe quel membre
  peut créer une app et l'obtenir, sans approbation partenaire. C'est ce qui
  rend possible une app par client.
- **Quotas** : 150 requêtes par membre et par jour, 100 000 par application.
  Chaque client a les siens.
- **Pas de refresh token** : réservés aux partenaires approuvés. Chaque
  client refait l'autorisation tous les 60 jours. S'il la relance **avant**
  l'expiration en étant connecté à LinkedIn, l'écran d'autorisation est
  sauté. D'où l'alerte à J−7, jamais après l'échéance.
- **Publier au nom d'une page entreprise** relève d'une autre API (Community
  Management), soumise à approbation. Hors périmètre.

## P0 — lecture des API Terms of Use

Lues en entier le 04/10/2026 (version révisée le 13 décembre 2022,
`linkedin.com/legal/l/api-terms-of-use`). Trois clauses bloquaient la forme
hébergée. La forme auto-hébergée en lève deux ; **la troisième reste
ouverte, et un point nouveau apparaît.**

| Clause | Texte | Forme auto-hébergée |
|---|---|---|
| §1.4, critère 5 | le Self-Serve exige que l'application « DOES NOT rely on access to the APIs as a fundamental aspect of your business » | **levée** : Sentinelle n'exploite aucune app pour ses clients ; l'app de chaque client sert son propre profil, pas son activité |
| §8.2 | « You may not charge your Users incremental fees for access to our Content or APIs » | **levée** si le prix ne dépend jamais du volume publié — voir « Ce qui n'est jamais vendu » |
| §3.1, dernier point | interdit de « use the Content or the APIs to automate posting on the LinkedIn Services » | **non levée** : elle vise chaque app, celle du client comme celle d'Alan. Le texte ne dit pas si publier à l'heure choisie un texte écrit et validé par le membre est « automatiser ». Le risque est porté par celui qui enregistre l'app : il doit lui être dit par écrit avant la vente |
| §2.2 (nouveau) | « do not require your Users to obtain their own Access Credentials to use your Application (for example, in an attempt to circumvent call limits) » | **à surveiller** : la clause vise un développeur qui fait porter ses clés par ses utilisateurs. Ici le client est le développeur de sa propre app et son seul utilisateur, et aucune limite n'est contournée. Lecture favorable, pas certitude |

Obligations qui pèsent sur celui qui enregistre l'app, donc sur chaque
client, pour ses propres données : conditions d'utilisation et politique de
confidentialité (§5.1), sécurité et signalement d'incident sous 24 h
(§7.1), marque LinkedIn limitée à l'intérieur de l'application (§6.1). Pour
une app à utilisateur unique, elles sont légères ; le guide d'installation
doit les nommer.

Pour Sentinelle : aucun support de vente ne montre la marque LinkedIn sans
approbation préalable (§6.1), et rien ne laisse entendre un partenariat.

L'app `Post-Agent` reste celle d'Alan, pour son instance. Aucun client ne
s'y connecte : la question de son rattachement à la page Sentinelle
Services ne se pose plus pour la vente.

### Note du 04/10/2026 — Marketing API Terms, pour archive

Lu en entier : « Additional Terms for the LinkedIn Marketing API Program »
(`linkedin.com/legal/l/marketing-api-terms`), version « Last revised on
July 25, 2025 ». Rien n'en dépend depuis le passage à la forme
auto-hébergée ; consigné pour ne pas avoir à le relire.

C'est un « Vetted API Program », pas le « Partner Program » : ce dernier
est un contrat signé séparé (API Terms §1.2), dont le texte n'est pas
public. La question du backlog ne peut donc recevoir de réponse que pour
le programme Vetted.

- **§1.4 des API Terms : levée.** Ses critères sont ceux du Self-Serve. Le
  programme Marketing est fait pour des applications qui fournissent des
  services à des clients sous contrat (LMA §1.2), dont la gestion de
  profils de membres pour leur compte (LMA §1.6, « Member Profile
  Management »). Dépendre de l'API y est le cas prévu.
- **§3.1 « automate posting » : pas levée par le texte.** Les LMA Terms ne
  l'emportent sur les API Terms qu'en cas de conflit (LMA §1.3), et aucune
  de leurs clauses ne parle de publication automatique ou programmée.
  « Manage Member Profiles » ne dit pas si programmer un post en fait
  partie. Seule la revue de LinkedIn trancherait : le cas d'usage est
  déclaré à la demande d'accès et aucun autre n'est permis (LMA §2.1).
- **Facturer** : prévu. LMA §5.1 admet des « markup fees » sur les
  services, à condition qu'ils restent distincts des coûts LinkedIn.

Ce que ce programme coûterait, s'il fallait un jour y revenir : revue de
l'application et des pratiques de sécurité, sans délai garanti (§2.1) ;
audit possible à tout moment (§2.3) ; interdiction de mettre l'application
à disposition d'un autre développeur qui la proposerait à ses propres
clients (§3.2.b) ; interdiction de servir des clients depuis ses propres
comptes (§3.2.k) ; données de membres ni exportées ni conservées au-delà
des durées de la documentation (§3.1.e, §4.1) ; résiliation par l'une ou
l'autre partie sous 30 jours, sans motif (§6.2).

Ceci est une lecture, pas un avis juridique.

## Ce que l'instance actuelle ne permet pas encore de vendre

| Aujourd'hui | Problème chez un client |
|---|---|
| Installation à la main, étalée sur trois semaines de notes | il faut une procédure rejouable, de zéro à un premier post programmé |
| `auth.py` dans un terminal, tous les 60 jours | un non-technicien ne relancera pas un script ; le renouvellement est le point de rupture du modèle |
| Décisions par déplacement de fichiers dans git | illisible hors du poste d'Alan : c'est le rôle de l'interface |
| Serveur MCP local, lancé par Claude Code | le client n'a pas forcément Python, ni le même assistant |
| Aucun canal de mise à jour | un correctif doit atteindre les instances installées sans que Sentinelle y ait accès |
| Création de l'app LinkedIn non documentée | le portail demande de la rattacher à une page LinkedIn : à vérifier sur une vraie première installation |

Ce qui, à l'inverse, convient déjà : un dépôt par client, un secret par
client, une horloge par client. Ce qui était un défaut de la forme hébergée
est exactement la forme auto-hébergée.

## Socle technique

Non tranché. Le plan du 02/10 portait le cœur en TypeScript sur Cloudflare
pour servir plusieurs clients depuis une seule plateforme. Cette raison a
disparu avec la forme hébergée ; reste à savoir si d'autres la remplacent.
Instruit dans `DECISIONS.md`, à trancher en P1.

## Données et sécurité

- Sentinelle ne détient aucun jeton d'accès, aucun identifiant d'app, aucun
  texte de post d'un client. Il n'y a donc ni base, ni chiffrement, ni
  suppression sur demande à organiser de son côté.
- Le client garde tout dans ses propres comptes ; arrêter le produit, c'est
  supprimer son dépôt et révoquer son app.
- Aucun texte de post dans les journaux techniques de l'instance.
- Si le client demande une aide à distance, elle passe par ce qu'il montre,
  jamais par un accès donné à Sentinelle.

## Questions ouvertes, à trancher par Alan

1. **§3.1** : le risque « automate posting » est-il acceptable, et sous
   quelle formulation est-il annoncé au client ?
2. **Cible** : particuliers et indépendants (profil personnel, possible
   aujourd'hui). Les pages entreprise restent hors périmètre.
3. **Rédaction** : le client apporte son propre assistant (connecteur MCP),
   ou l'installation inclut une rédaction IA à ses frais ?
4. **Prix** : forfait d'installation, abonnement d'accompagnement, ou les
   deux — jamais indexé sur le volume publié.
5. **Marque** : PostAgent seul, ou « PostAgent par Sentinelle Services »
   partout ?
6. **Licence du logiciel** : ce que le client a le droit de faire du code
   une fois installé chez lui.

## Étapes

Même règle qu'au `ROADMAP.md` : une étape n'est close que validée en
conditions réelles.

L'ancienne découpe (cœur porté en TypeScript, connexion multi-clients,
Durable Objects, migration d'Alan) est abandonnée avec la forme hébergée.

### Découpe proposée le 04/10/2026 — non commencée, à valider par Alan

| Étape | Contenu | Validation |
|---|---|---|
| P0 | Lecture des API Terms of Use | faite ; reste à décider si §3.1 est un risque acceptable, pour Alan et pour un client |
| P1 | Trancher le socle : garder Python + GitHub Actions + Worker d'horloge, ou porter | décision écrite ici, avec sa raison |
| P2 | Installation rejouable, sans secret chez Sentinelle : de comptes vides à un post programmé, app LinkedIn créée par le client | une seconde instance installée sur des comptes qui ne sont pas ceux d'Alan, sans que Sentinelle ait vu un seul secret |
| P3 | Renouvellement sans terminal : le client refait l'autorisation LinkedIn seul, depuis l'alerte à J−7 | un non-technicien renouvelle son accès sans aide |
| P4 | Interface de l'instance : calendrier, décisions, renouvellement | un non-technicien programme et annule un post sans aide |
| P5 | Assistant : serveur MCP utilisable depuis l'assistant du client | programmer un post depuis un assistant sur un poste qui n'est pas celui d'Alan |
| P6 | Mises à jour et support : un correctif atteint les instances installées ; un échec est visible du client | un correctif propagé à deux instances sans accès de Sentinelle |
| P7 | Offre et première vente : prix, contrat, avertissement écrit sur §3.1 et §11.3 | premier client payant |

L'instance d'Alan reste en service telle quelle pendant tout le chantier :
elle est la première installation, pas un système à remplacer.
