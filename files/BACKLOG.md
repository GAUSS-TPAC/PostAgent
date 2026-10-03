# BACKLOG.md

Par ordre de priorité. On ne travaille que sur le premier item non bloqué.
Voir `LOOP.md` pour le protocole.

États : `à faire` · `en cours` · `fini` · `bloqué`

---

## 1. Vérifier le garde-fou de publication — fini

Vérifié le 04/10/2026 par `tests/garde_fou.py` (voir `JOURNAL.md`).

Aucun chemin de code ne doit pouvoir publier sans un `DRY_RUN` explicite
ou une action humaine. C'est la condition d'existence de cette boucle.

**Fini quand** : la liste des chemins menant à un POST `/rest/posts` est
dans le journal, et chacun est soit derrière `DRY_RUN`, soit accessible
uniquement par `publish_now` (interdit à la boucle). Si un chemin
échappe aux deux, le corriger d'abord.

---

## 2. Phase C de TESTING.md — à faire

C.1 (token invalide), C.2 (token expiré), C.6 (URN absent), C.7 (réseau
coupé). Jamais joués. Exigés avant la phase D.

Aucun ne publie : ils vérifient que le code échoue proprement. C.3, C.4,
C.5 sont faits.

**Fini quand** : les quatre lignes sont au journal des tests de
`TESTING.md` avec leur sortie réelle. C.6 et C.7 doivent échouer **avant**
tout appel réseau.

---

## 3. Nettoyages en attente — à faire

- `stale/2026-09-16T1523.json` : déchet du test de péremption du 18/09.
- Secret `TRIGGER_KEY` encore présent côté Worker (sans effet depuis le
  plan B). Demande `wrangler secret delete` → **interdit à la boucle**,
  donc va dans `DECISIONS.md`.
- `README.md` et `CLAUDE.md` : vérifier qu'aucune instruction ne décrit
  encore l'endpoint `/trigger`, supprimé le 22/09.

**Fini quand** : le dépôt ne contient plus de référence à `/trigger`, le
fichier `stale/` est supprimé, et le secret Worker est consigné dans
`DECISIONS.md`.

---

## 4. Réécrire PRODUIT.md — forme auto-hébergée — à faire

Décision d'Alan du 04/10 : on ne vend pas un service qui publie, on vend
le logiciel et sa mise en place. Chaque client enregistre **sa propre**
app LinkedIn, à son nom, sous son propre palier self-serve. On ne détient
aucun token client.

Conséquences à écrire noir sur blanc :
- ce qui est vendu (logiciel, installation, accompagnement, gabarits) ;
- ce qui n'est jamais vendu (l'accès à l'API — §8.2) ;
- ce que le client enregistre lui-même (app LinkedIn, secrets, horloge) ;
- P2 ne stocke plus aucun token : la section est à réécrire, pas à
  ajuster.

Précédent documenté : Postiz, même catégorie, même modèle.

**Fini quand** : `PRODUIT.md` ne contient plus aucune mention de stockage
de token client, et la nouvelle découpe P1–P7 est proposée en fin de
fichier, non commencée.

---

## 5. Marketing API Terms — pour archive — à faire

Vingt minutes, rien n'en dépend. Lire et consigner dans la section P0 de
`PRODUIT.md` si les conditions du programme Partner lèvent §1.4 et §3.1.

**Fini quand** : une note datée est dans `PRODUIT.md`, avec la version du
document lue.

---

## 6. Question ouverte à instruire — à faire

Le passage en TypeScript / Cloudflare (P1) garde-t-il un sens si le
produit n'héberge plus de tokens ? Ne pas coder : écrire l'analyse dans
`DECISIONS.md` avec une recommandation.

**Fini quand** : l'entrée est dans `DECISIONS.md`.

---

## Hors boucle — pour Alan seul

- Phase D : la première vraie publication. Demande une action humaine et
  un texte validé.
- Le texte du post sur les connaissances métier : Alan doit fournir
  l'anecdote.
- Renouvellement du token LinkedIn : échéance 13 novembre.
- Expiration du `DISPATCH_PAT` : un an après sa création.
