# TESTING.md

Protocole de test du projet. À suivre dans l'ordre, sans sauter d'étape.

## Règle absolue

**LinkedIn n'a pas d'environnement de test.** Aucune sandbox, aucun mode
brouillon accessible par l'API. Tout appel réussi produit une publication
réelle sur le profil d'Alan, visible par son réseau et indexable.

Conséquences, non négociables :

1. Toute publication de test est en visibilité `CONNECTIONS`, jamais `PUBLIC`.
2. Toute publication de test est supprimée immédiatement après vérification.
3. Aucun test n'est lancé sans qu'Alan soit présent et prévenu.
4. Ne relance jamais un test « pour voir » après un échec sans avoir compris
   la cause : une erreur côté réponse HTTP ne garantit pas que rien n'a été
   publié. Vérifie visuellement le profil avant toute relance.

## Prérequis

- Étape 1 validée : `python auth.py --status` retourne un token valide et un
  URN de la forme `urn:li:person:...`
- `linkedin.py` écrit, avec `publish()`, `me()` et `delete(post_id)`
- MCP Microsoft Learn accessible dans la session
- Alan devant son profil LinkedIn, prêt à vérifier visuellement

La fonction `delete()` est un prérequis, pas une fonctionnalité optionnelle.
Ne lance aucun test de publication avant qu'elle existe et soit relue.

---

## Phase A — Validation de la chaîne technique

**But :** prouver que token, headers, payload et parsing de la réponse
fonctionnent. Le contenu n'a aucune importance.

| ID | Scénario | Procédure | Attendu | Si échec |
|---|---|---|---|---|
| A.1 | Identité | `me()` | nom + URN identiques à `token.json` | problème de token, stop |
| A.2 | Publication minimale | publier `test technique <horodatage>` en `CONNECTIONS` | un `post_id` (`urn:li:share:...` ou `urn:li:ugcPost:...`) | voir tableau des erreurs |
| A.3 | Confirmation visuelle | Alan regarde son profil | le post est là | **point d'arrêt** |
| A.4 | Suppression | `delete(post_id)` | 200 ou 204 | **stop tout le protocole** |
| A.5 | Confirmation de suppression | Alan rafraîchit son profil | le post a disparu | nettoyage manuel |

Sans suppression fiable (A.4), la phase B devient trop risquée : ne la lance
pas et signale-le à Alan.

---

## Phase B — Validation du rendu du texte

**But :** c'est la phase qui compte réellement. Le champ `commentary` de
`/rest/posts` impose l'échappement de caractères réservés. Un texte mal
échappé produit soit une erreur 400, soit un post affichant des backslashes
visibles — sur un contenu qu'on voulait garder.

### B.0 Avant de coder

Interroge le MCP Microsoft Learn pour obtenir la liste exacte des caractères
réservés du champ `commentary` et la règle d'échappement. Rapporte ce que dit
la documentation avant d'écrire la fonction d'échappement. Ne te fie pas à ta
mémoire sur ce point.

### B.1 Jeu de test

Publier ce texte exact, en visibilité `CONNECTIONS` :

```
test rendu 2026-09-18

Ligne avec accents : é è ê à ç ù ô
Ponctuation : (parenthèses) [crochets] {accolades}
Symboles : @ # * _ ~ | < > = + -
Tiret long — et apostrophe d'usage
Chiffres : 18 094 tickets, 12,5 %

Dernière ligne après double saut.
```

### B.2 Grille de vérification visuelle

| ID | Point contrôlé | Attendu | Symptôme d'échec |
|---|---|---|---|
| B.2.1 | Accents | `é è ê à ç ù ô` corrects | `Ã©` → problème d'encodage UTF-8 |
| B.2.2 | Caractères réservés | visibles tels quels | backslash parasite → sur-échappement |
| B.2.3 | Saut de ligne simple | respecté | lignes collées |
| B.2.4 | Double saut | vrai paragraphe | saut simple |
| B.2.5 | Espace des milliers | `18 094` conservé | `18094` ou espace perdu |
| B.2.6 | Tiret long / apostrophe | `—` et `'` intacts | caractères de remplacement |

Note tout écart dans le journal en bas de ce fichier, avec le caractère fautif.

### B.3 Suppression

`delete(post_id)`, confirmation visuelle par Alan.

**Point d'arrêt obligatoire.** Ne passe pas en phase C tant que les six points
de B.2 ne sont pas validés. Un défaut d'échappement sur le post de la phase C
serait public et durable.

---

## Phase C — Cas limites et erreurs

Ces scénarios ne publient rien de valable : ils vérifient que le code échoue
proprement. À exécuter avant la mise en service réelle, pas après.

| ID | Scénario | Provocation | Attendu |
|---|---|---|---|
| C.1 | Token invalide | altérer un caractère du token en mémoire | erreur explicite mentionnant 401, pas de trace ambiguë |
| C.2 | Token expiré | forcer `expires_at` dans le passé | message clair invitant à relancer `auth.py`, **avant** tout appel réseau |
| C.3 | Texte vide | `publish("")` | refus côté client, aucun appel HTTP émis |
| C.4 | Texte trop long | 3 500 caractères (limite LinkedIn : 3 000) | refus côté client avec le nombre de caractères, aucun appel HTTP |
| C.5 | Texte à la limite | exactement 3 000 caractères | publication acceptée |
| C.6 | URN absent | supprimer `person_urn` de l'environnement et du fichier | erreur explicite, pas de `KeyError` brut |
| C.7 | Réseau coupé | couper le wifi puis publier | erreur réseau lisible, pas de trace Python nue |
| C.8 | `post_id` inexistant | `delete("urn:li:share:000000")` | erreur 404 gérée, message clair |
| C.9 | Double suppression | `delete()` deux fois sur le même id | la seconde échoue proprement, sans exception non gérée |

C.3, C.4 et C.6 doivent être rejetés **avant** tout appel réseau. Une
validation qui laisse partir la requête gaspille du quota et brouille le
diagnostic.

C.7 est le scénario le plus réaliste dans les conditions de connexion d'Alan.
Le traiter correctement n'est pas du luxe.

---

## Phase D — Première publication réelle

Ce n'est plus un test. C'est la mise en service.

### Préconditions

- Phases A, B et C intégralement validées
- Le texte du post a été rédigé et **relu par Alan**
- Alan a vérifié qu'il ne divulgue aucun chiffre interne ni projet en cours
  d'Afriland sans accord
- Visibilité : `PUBLIC`
- Le post n'est **pas** supprimé après coup

### Procédure

1. Affiche le texte intégral à publier et demande une confirmation explicite.
   Pas de publication sur un « ok » ambigu.
2. Publie.
3. Retourne le `post_id` et enregistre l'entrée dans `published/`.

L'API ne permet pas d'éditer le texte d'un post publié. La seule voie de
correction est supprimer puis republier, ce qui perd les réactions. Signale-le
à Alan **avant** qu'il confirme, pas après.

---

## Phase E — Scheduler (étape 3)

À exécuter quand `publisher.py` et le workflow existent. Tous les posts de
cette phase sont en `CONNECTIONS` et supprimés après vérification.

| ID | Scénario | Procédure | Attendu | Couvre |
|---|---|---|---|---|
| E.1 | Queue vide | lancer le publisher sans fichier | sortie propre, code 0, aucun appel | — |
| E.2 | Post futur | fichier daté à +2 h | ignoré, reste en `queue/` | — |
| E.3 | Publication différée | fichier daté à +20 min, poste éteint | part seul, dérive ≤ 30 min | NF2 |
| E.4 | Idempotence | relancer le workflow sur une queue déjà traitée | aucune republication | **NF5** |
| E.5 | Rejeu concurrent | deux exécutions simultanées sur la même queue | un seul post publié | **NF5** |
| E.6 | Échec bruyant | token invalide dans les secrets | workflow en échec, trace lisible | NF6 |
| E.7 | Fichier bloqué | laisser un fichier dans `publishing/` | signalé, jamais republié automatiquement | NF5 |
| E.8 | JSON malformé | virgule en trop dans un fichier de queue | échec explicite nommant le fichier | NF6 |
| E.9 | Alerte d'expiration | token à moins de 7 jours | avertissement émis avant l'échéance | NF6 |
| E.10 | Plusieurs posts dus | trois fichiers échus simultanément | tous publiés, aucun doublon | NF5 |
| E.11 | Attente bornée | fichier daté à +10 min, run lancé à la main | le run attend, publie à l'heure exacte, dérive ≤ 1 min | NF2 |
| E.12 | Hors fenêtre d'attente | fichier daté à +45 min (> `WAIT_WINDOW`) | ignoré ce run, reste en `queue/`, aucune attente | NF2 |
| E.13 | **Péremption** | fichier daté à −4 h (> `STALE_AFTER`) | **aucun appel API**, fichier déplacé dans `stale/`, workflow en échec nommant le retard | NF6 |
| E.14 | Péremption non rejouée | relancer après E.13 | `stale/` intact, rien republié, run suivant vert | NF5 |

E.4 et E.5 sont les deux tests qui protègent contre le seul dégât public
possible : un doublon sur le profil. Ne les traite pas comme optionnels.

E.13 se teste sans risque : le post ne doit jamais atteindre LinkedIn. Si un
`post_id` apparaît, le seuil de péremption ne fonctionne pas — arrête tout.
Le fichier `queue/2026-09-16T1523.json`, périmé de plusieurs jours, sert
précisément à ce test.

E.14 vérifie l'autre moitié : une fois dans `stale/`, un post ne doit plus
faire échouer les runs suivants, sinon l'alerte se noie dans son bruit.

E.9 se teste sans attendre deux mois : modifier `expires_at` dans `token.json`
suffit.

---

## Tableau des erreurs connues

| Erreur | Cause probable | Correction |
|---|---|---|
| `invalid_client` | secret mal copié, espace ou `\r` parasite | `cat -A .env`, chaque ligne finit par `$` |
| `redirect_uri_mismatch` | URL différente d'un caractère du portail | vérifier l'onglet Auth, pas de slash final |
| 401 sur `/rest/posts` | token expiré ou scope manquant | `auth.py --status`, puis réauthentifier |
| 403 | `w_member_social` absent | vérifier les produits dans le portail |
| 400 `commentary` | échappement incorrect | revoir B.0 via le MCP Learn |
| 426 | `LinkedIn-Version` absent ou périmé | confirmer la version courante via le MCP Learn |
| 429 | quota journalier atteint | attendre, ne pas réessayer en boucle |

---

## Journal des tests

Une ligne par exécution. C'est la seule trace que ce protocole doit laisser.

| Date | Scénario | Résultat | Observation |
|---|---|---|---|
| | | | |
