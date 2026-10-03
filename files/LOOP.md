# LOOP.md — protocole de travail autonome

Ce fichier définit comment travailler sur ce dépôt **sans Alan devant
l'écran**. Il se lit en entier à chaque réveil de boucle, avant toute
action.

Alan n'est pas là. Personne ne validera, ne corrigera, ni n'arrêtera une
erreur en cours. Tout ce qui suit découle de ce fait.

---

## 1. Interdits absolus

Ces règles ne souffrent aucune exception, aucune « bonne raison », aucun
« juste pour tester ».

| Interdit | Pourquoi |
|---|---|
| Appeler `publish_now`, `linkedin.publish()` ou tout POST vers `/rest/posts` | Un post parti est public et irréversible. C'est la seule action de ce dépôt qu'on ne peut pas annuler. |
| Pousser un fichier dans `queue/` | Un fichier en file **est** une publication armée. |
| Publier en visibilité `PUBLIC`, même en test | Règle du 14/09. |
| Créer, modifier, supprimer ou lire un secret (`gh secret`, `wrangler secret`, `.env`, `token.json`) | Ils n'appartiennent pas à la boucle. |
| `git push --force`, `rebase` sur `main`, réécriture d'historique | Perte irrécupérable. |
| Pousser sur `main` | `main` est la production : le publisher tourne depuis elle. |
| Déployer le Worker | `gh workflow run deploy-clock.yml` modifie l'horloge en service. |
| Supprimer un fichier de `published/`, `publishing/` ou `stale/` | Traces d'exécution réelle. |
| Lancer deux `pip install` concurrents dans le même environnement | Constaté le 23/09 : deux `dist-info` rivaux, `ImportError` incompréhensible, une heure perdue. |

**Avant la première itération**, vérifier que le garde-fou tient encore :

```bash
grep -rn "publish_now\|/rest/posts" --include="*.py" . | grep -v "^./tests"
```

Si un chemin de code permet de publier sans passer par un `DRY_RUN`
explicite, l'inscrire en tête de `files/BACKLOG.md` et le traiter en
priorité.

---

## 2. Où travailler

Toujours sur une branche, jamais sur `main` :

```bash
git checkout -b chantier/<nom-court>   # ou git checkout chantier/<nom-court>
```

Un seul chantier à la fois. Alan relit et fusionne.

---

## 3. Les trois fichiers d'état

La boucle n'a pas de mémoire entre deux réveils. Ces fichiers **sont** sa
mémoire. Ils vivent dans `files/`, à côté de `CLAUDE.md`, et sont commités
à chaque itération.

**`files/BACKLOG.md`** — ce qui reste à faire, par ordre de priorité. Un item =
un titre, un critère de fini vérifiable, et son état (`à faire`,
`en cours`, `fini`, `bloqué`). On ne travaille que sur le premier item non
bloqué.

**`files/JOURNAL.md`** — ce qui a été fait, en ajout seulement, jamais réécrit.
Une entrée par itération :

```
## 2026-10-04T01:12 — <item du backlog>

Fait      : <ce qui a changé, fichiers nommés>
Preuve    : <la commande lancée ET sa sortie, copiée>
Appris    : <ce que la prochaine itération doit savoir, ou "rien">
Reste     : <ce qui n'est pas fini, ou "rien">
```

La ligne **Preuve** n'est pas facultative. Une entrée sans commande et
sans sortie réelle ne vaut rien : une boucle qui s'auto-évalue se
félicite. Si la vérification n'a pas pu tourner, écrire « non vérifié »
et pourquoi — c'est une information utile, contrairement à une
affirmation.

**`files/DECISIONS.md`** — ce qui attend Alan. Au lieu de bloquer, d'attendre ou
de deviner, on écrit ici et on passe à l'item suivant. Une entrée :

```
## <date> — <question en une ligne>

Contexte  : <pourquoi ça se pose>
Options   : <les choix réels, avec leur conséquence>
Recommandé: <celui que je prendrais, et pourquoi>
Bloque    : <les items du backlog en attente>
```

Y vont : toute décision irréversible, tout choix de produit ou de prix,
tout ce qui demande un clic dans une interface, tout secret, et toute
dépense.

---

## 4. La boucle

À chaque réveil, dans cet ordre :

1. **Lire** `files/CLAUDE.md`, `files/LOOP.md`, `files/BACKLOG.md`, puis
   les trois dernières entrées de `files/JOURNAL.md`. Rien d'autre pour
   l'instant.
2. **Se situer** : `git status`, `git log --oneline -5`, branche courante.
   Si l'arbre est sale sans entrée de journal correspondante, une
   itération a été coupée : repartir de l'état réel, pas de l'état
   supposé.
3. **Choisir** le premier item non bloqué du backlog. Un seul.
4. **Travailler** dessus, et sur rien d'autre. Un item trop gros pour une
   itération se découpe dans le backlog avant d'être commencé.
5. **Vérifier** par une commande qui peut échouer. Pas de relecture de
   code en guise de test.
6. **Écrire** l'entrée de journal, mettre à jour le backlog, commiter,
   pousser sur la branche de chantier.
7. **Décider** : item suivant, ou arrêt (voir ci-dessous).

---

## 5. Définition de fini

Un item n'est fini que si :

- son critère de fini a été vérifié par une commande dont la sortie est
  dans le journal ;
- les tests existants passent toujours (`TESTING.md`, non-régression CI) ;
- aucun module ne dépasse 250 lignes (NF7) ;
- `requirements.txt` contient toujours exactement `requests` et
  `python-dotenv` ;
- le travail est commité et poussé sur la branche.

Sinon l'item reste `en cours` ou passe `bloqué`, avec la raison.

---

## 6. Quand s'arrêter

S'arrêter et écrire un résumé final dès que l'une de ces conditions est
vraie :

- le backlog n'a plus d'item non bloqué ;
- trois itérations de suite ont échoué sur le même point ;
- une action nécessaire figure dans les interdits ;
- un test qui passait échoue et la cause n'est pas comprise en une
  itération ;
- le réseau est indisponible et l'item en cours en dépend.

L'arrêt propre vaut mieux que l'acharnement : un arbre de travail commité,
un journal à jour et une question claire dans `files/DECISIONS.md` valent
plus qu'un chantier à moitié fait dont personne ne comprend l'état.

**Ne jamais** contourner un interdit parce que l'item semble le demander.
C'est le cas précis où il faut s'arrêter et écrire dans
`files/DECISIONS.md`.

---

## 7. Pièges connus de ce dépôt

Mis à jour par la boucle elle-même. Date obligatoire.

- **04/10** — Le verrou `POSTAGENT_DRY_RUN` est opt-in. Préfixer **toute**
  commande Python par `POSTAGENT_DRY_RUN=1`. `python publisher.py` sans
  argument publie les posts dus : ne jamais le lancer nu. `repo.sync()`
  pousse la branche courante avec `queue/` : ne l'appeler, ni `agenda.*`,
  que sur un dossier jetable. Contrôle : `tests/garde_fou.py`.
- **23/09** — `pip install` concurrents : paquet corrompu, `ImportError`
  sur un paquet pourtant listé.
- **23/09** — SDK `mcp` 2.x : `FastMCP` → `MCPServer`, `inputSchema` →
  `input_schema`. Les exemples en ligne décrivent la 1.x. Inspecter le
  paquet installé, jamais écrire de mémoire.
- **23/09** — Le SDK MCP remplace toute exception ordinaire par
  « Error executing tool » et perd le message. Seul `ToolError` traverse.
- **22/09** — Node coupe chaque tentative de connexion à 250 ms. Sur la
  connexion d'Alan (~600 ms), tout échoue. `NODE_OPTIONS` est réglé dans
  son `.bashrc`.
- **22/09** — `wrangler deploy` accepte n'importe quelle
  `compatibility_date` sans broncher. Seul `wrangler dev` révèle une date
  non supportée.
- **21/09** — LinkedIn annonce `DELETE` comme idempotent ; l'API renvoie
  404 sur un post déjà supprimé.
- **Toujours** — vérifier l'API LinkedIn via le serveur MCP
  `microsoft-learn`, pas de mémoire. L'API est versionnée par mois.
