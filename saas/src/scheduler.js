/**
 * Ordonnanceur : publie les posts dont l'heure est venue. Appelé chaque
 * minute par le Cron Trigger. Portage de publisher.py, la file dans D1.
 *
 * Mêmes règles que l'instance Python :
 *  - un post est réservé (statut « publishing ») AVANT l'appel à LinkedIn,
 *    jamais après : un rejeu ne peut pas le reprendre ;
 *  - aucun nouvel essai automatique : un échec passe en « failed » et attend
 *    une décision humaine, car une erreur ne prouve pas que rien n'est parti ;
 *  - au-delà de PEREMPTION, le post n'est plus publié : le créneau visé
 *    n'existe plus.
 * Le texte des posts n'apparaît jamais dans les journaux.
 */

import { rendreCarrousel } from "./carousel.js";
import { dechiffrer } from "./crypto.js";
import * as linkedin from "./linkedin.js";
import * as store from "./store.js";

export const PEREMPTION_MS = 3 * 3600_000;
export const estOuvert = (env) => env.POSTAGENT_LIVE === "1";

/** Prépare le média du post et retourne { id, title } prêt pour publier(), ou null. */
async function media(post, identifiants, live) {
  if (!post.media_kind) return null;
  if (post.media_kind === "carousel") {
    const pdf = rendreCarrousel(JSON.parse(post.carousel));
    const id = await linkedin.envoyerMedia(identifiants, "document", pdf, { live });
    return { id, title: post.media_title };
  }
  const id = await linkedin.envoyerMedia(identifiants, post.media_kind, new Uint8Array(post.media_data), { live });
  return post.media_kind === "document" ? { id, title: post.media_title } : { id };
}

async function publierUn(env, id, maintenant) {
  const post = await store.postAvecMembre(env.DB, id);
  if (post.token_expires_at <= store.iso(maintenant)) {
    throw new Error("Accès LinkedIn expiré : reconnecte-toi, puis reprogramme ce post");
  }
  const identifiants = { token: await dechiffrer(env.TOKEN_KEY, post.token_enc), urn: post.person_urn };
  const piece = await media(post, identifiants, true);
  return linkedin.publier(identifiants, { text: post.text, visibility: post.visibility, media: piece }, { live: true });
}

/**
 * Traite les posts dus. Retourne un compte rendu chiffré, sans aucun texte.
 * Ne lève pas : chaque post échoue seul, les autres continuent.
 */
export async function executer(env, maintenant = new Date()) {
  const bilan = { perimes: 0, publies: 0, echecs: 0, ignores: 0, ferme: false };
  bilan.perimes = await store.perimer(env.DB, store.iso(new Date(maintenant.getTime() - PEREMPTION_MS)));

  const dus = await store.postsDus(env.DB, store.iso(maintenant));
  // Verrou fermé : on le dit avant de réserver quoi que ce soit, sinon les
  // posts resteraient coincés en « publishing » pour une variable oubliée.
  if (!estOuvert(env)) {
    bilan.ferme = true;
    bilan.ignores = dus.length;
    return bilan;
  }

  for (const { id } of dus) {
    if (!(await store.reserver(env.DB, id))) {
      bilan.ignores += 1;
      continue;
    }
    try {
      const postId = await publierUn(env, id, maintenant);
      await store.marquerPublie(env.DB, id, postId, maintenant);
      bilan.publies += 1;
    } catch (erreur) {
      // Le post reste hors de la file : c'est le membre qui tranche, après
      // avoir regardé son profil.
      await store.marquerEchec(env.DB, id, erreur.message ?? erreur);
      bilan.echecs += 1;
    }
  }
  return bilan;
}
