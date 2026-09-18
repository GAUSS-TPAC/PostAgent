# SPEC.md

Ce que le système doit faire, et sous quelles contraintes.

## Besoins fonctionnels

| ID | Besoin | Version |
|---|---|---|
| F1 | S'authentifier auprès de LinkedIn (OAuth 2.0) et réutiliser le jeton sans refaire le flow à chaque publication | v1 |
| F2 | Recevoir un texte de post déjà rédigé et validé | v1 |
| F3 | Publier immédiatement sur le profil personnel | v1 |
| F4 | Programmer un post à une date et une heure précises | v1 |
| F5 | Consulter la file des posts programmés | v1 |
| F6 | Annuler ou modifier un post programmé avant son départ | v1 |
| F7 | Exécuter automatiquement les posts dus, sans intervention ni machine allumée | v1 |
| F8 | Conserver l'historique des posts publiés avec leur identifiant LinkedIn | v1 |
| F9 | Joindre une image à un post | v2 |
| F10 | Diffuser vers X | reporté |

Précision sur F2 : la rédaction n'est pas une fonctionnalité du système. Elle a
lieu dans la conversation avec l'assistant. Le code ne reçoit que du texte
final. C'est ce qui maintient le projet petit.

## Besoins non fonctionnels

| ID | Contrainte | Vérification |
|---|---|---|
| NF1 | Coût nul en fonctionnement : pas de VPS, pas d'abonnement | facture à 0 |
| NF2 | La publication part même poste éteint. Dérive tolérée : ±30 min | test d'un post programmé la nuit |
| NF3 | API officielle uniquement, aucun scraping | revue de code |
| NF4 | Secrets hors du dépôt, en GitHub Secrets uniquement | `git log -p` ne contient aucun secret |
| NF5 | Idempotence : aucun post publié deux fois | rejouer le publisher sur une queue déjà traitée |
| NF6 | Échec visible : workflow en échec et trace exploitable | injecter un token invalide |
| NF7 | Sobriété : environ 300 lignes, dépendances minimales | `wc -l src/*.py` |
| NF8 | Cœur métier LinkedIn isolé de l'orchestration, réutilisable en multi-tenant | `linkedin.py` n'importe ni la queue, ni le MCP, ni les Actions |

## Le point dur

NF5 est la seule vraie difficulté de conception du projet. Le reste est de la
plomberie.

Le cron s'exécute 96 fois par jour et peut, en cas de lenteur ou de relance,
traiter deux fois la même file. La parade retenue : le fichier de queue est
déplacé de `queue/` vers `publishing/` **avant** l'appel HTTP. Si l'appel
réussit, il part dans `published/`. S'il échoue, il reste dans `publishing/` et
le workflow échoue — un humain tranche. Un fichier ne repart jamais tout seul.

Le pire cas résiduel : l'appel LinkedIn aboutit mais la réponse se perd. Le
post est publié, le fichier reste en `publishing/`. On préfère cette situation
— visible et corrigeable à la main — à un doublon publié.

## Contrainte héritée de l'exécuteur

Le cron GitHub dérive de 2 h à 5 h 30 (mesuré, voir ARCHITECTURE.md). NF2 est
donc intenable si l'heure de publication dépend du cron. Elle dépend désormais
d'une attente bornée à 20 minutes dans le publisher, qui ramène la dérive
sous les ±30 minutes retenus — à condition qu'un run démarre dans les
20 minutes précédant l'heure prévue. Quand ce n'est pas le cas, le post part
en retard, et au-delà de 3 heures il ne part plus du tout (péremption).

C'est cette réserve qui justifie l'horloge externe prévue ensuite.

## Contrainte héritée du fournisseur

Le token expire au bout de 2 mois et l'app ne dispose pas de refresh token.
Conséquence de conception : le système doit alerter **avant** l'expiration,
pas la découvrir au moment d'un échec de publication. C'est une application
directe de NF6.
