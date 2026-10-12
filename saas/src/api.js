/**
 * API de l'interface. Chaque route agit pour le membre connecté et lui seul :
 * `membre.id` est passé à toutes les fonctions du store.
 *
 * Aucune route ne publie directement. « Publier maintenant » programme le
 * post à l'instant présent ; l'ordonnanceur le prend dans la minute. Il n'y a
 * donc qu'un seul chemin vers LinkedIn, et il passe par le verrou.
 */

import { rendreCarrousel, validerCarrousel } from "./carousel.js";
import { dechiffrer } from "./crypto.js";
import { rediger } from "./generate.js";
import { LinkedInError, statistiques, valider } from "./linkedin.js";
import { estOuvert } from "./scheduler.js";
import * as store from "./store.js";

// D1 refuse les lignes de plus de 2 Mo : on garde de la marge. Au-delà il
// faudra un stockage d'objets (R2) — c'est aussi ce qui bloque la vidéo.
export const MEDIA_MAX = 1_500_000;

const json = (corps, status = 200) => Response.json(corps, { status });
const refus = (message, status = 400) => json({ erreur: message }, status);

function dateProgrammee(valeur, now) {
  if (valeur === "now") return store.iso(now);
  // Le fuseau est obligatoire : sans lui l'heure de publication est ambiguë.
  if (typeof valeur !== "string" || !/(Z|[+-]\d\d:\d\d)$/.test(valeur) || Number.isNaN(Date.parse(valeur))) {
    throw new RangeError("Date illisible ou sans fuseau horaire. Exemple : 2026-10-24T09:00:00+01:00");
  }
  const date = new Date(valeur);
  if (date <= now) throw new RangeError("La date de publication est dans le passé");
  return store.iso(date);
}

function octetsDepuisBase64(b64) {
  try {
    return Uint8Array.from(atob(b64 ?? ""), (c) => c.charCodeAt(0));
  } catch {
    throw new RangeError("Fichier illisible");
  }
}

const commencePar = (octets, signature) => signature.every((o, i) => octets[i] === o);

/** Contrôle le média demandé et le met sous la forme attendue par le store. */
function preparerMedia(media) {
  if (!media) return {};
  if (media.kind === "carousel") {
    const spec = validerCarrousel(media.spec);
    return { mediaKind: "carousel", mediaTitle: (media.title || spec.pages[0].titre).slice(0, 200), carousel: JSON.stringify(spec) };
  }
  const octets = octetsDepuisBase64(media.data);
  if (octets.byteLength > MEDIA_MAX) throw new RangeError(`Fichier trop lourd : ${octets.byteLength} octets, maximum ${MEDIA_MAX}`);
  if (media.kind === "image") {
    const ok = commencePar(octets, [0xff, 0xd8]) || commencePar(octets, [0x89, 0x50, 0x4e, 0x47]) || commencePar(octets, [0x47, 0x49, 0x46]);
    if (!ok) throw new RangeError("Image refusée : JPG, PNG ou GIF attendu");
    return { mediaKind: "image", mediaData: octets.buffer };
  }
  if (media.kind === "document") {
    if (!commencePar(octets, [0x25, 0x50, 0x44, 0x46])) throw new RangeError("Document refusé : PDF attendu");
    if (!media.title?.trim()) throw new RangeError("Un document a besoin d'un titre");
    return { mediaKind: "document", mediaTitle: media.title.trim().slice(0, 200), mediaData: octets.buffer };
  }
  throw new RangeError(`Type de média inconnu : ${media.kind}`);
}

async function creer(request, env, membre, now) {
  const demande = await request.json();
  valider(demande.text, demande.visibility);
  const id = await store.creerPost(env.DB, membre.id, {
    text: demande.text,
    visibility: demande.visibility,
    scheduledAt: dateProgrammee(demande.scheduled_at, now),
    ...preparerMedia(demande.media),
  }, now);
  return json({ id }, 201);
}

async function stats(env, membre, id) {
  const post = await store.lirePost(env.DB, membre.id, id);
  if (!post?.post_id) return refus("Ce post n'est pas publié", 404);
  const identifiants = { token: await dechiffrer(env.TOKEN_KEY, membre.token_enc) };
  try {
    const metriques = {};
    for (const m of ["IMPRESSION", "REACTION", "COMMENT", "RESHARE"]) metriques[m] = await statistiques(identifiants, post.post_id, m);
    return json({ disponible: true, metriques });
  } catch (erreur) {
    if (erreur instanceof LinkedInError && erreur.status === 403) {
      return json({ disponible: false, raison: "LinkedIn n'a pas accordé à l'application la permission de lire les statistiques (r_member_postAnalytics)." });
    }
    throw erreur;
  }
}

/** Route une requête /api/*. `membre` est déjà authentifié par l'appelant. */
export async function api(request, env, membre, now = new Date()) {
  const { pathname } = new URL(request.url);
  const methode = request.method;
  const [, , ressource, id, action] = pathname.split("/");

  // Toute écriture doit venir de notre page : un formulaire d'un autre site
  // ne peut pas poser cet en-tête sans autorisation CORS, que l'on n'accorde pas.
  if (methode !== "GET" && request.headers.get("X-PostAgent") !== "1") return refus("Requête refusée", 403);

  try {
    if (ressource === "me" && methode === "GET") {
      const jours = Math.floor((Date.parse(membre.token_expires_at) - now.getTime()) / 86_400_000);
      return json({ name: membre.name, token_expires_at: membre.token_expires_at, jours_restants: jours, publication_ouverte: estOuvert(env) });
    }
    if (ressource === "account" && methode === "DELETE") {
      await store.supprimerCompte(env.DB, membre.id);
      return json({ supprime: true });
    }
    if (ressource === "carousel" && methode === "POST") {
      const pdf = rendreCarrousel((await request.json()).spec);
      return new Response(pdf, { headers: { "Content-Type": "application/pdf" } });
    }
    // Un brouillon seulement : rien n'est enregistré, rien n'est programmé.
    if (ressource === "generate" && methode === "POST") return json(await rediger(env, await request.json()));
    if (ressource !== "posts") return refus("Introuvable", 404);

    if (!id && methode === "GET") return json({ posts: await store.listerPosts(env.DB, membre.id) });
    // `await` obligatoire : sans lui le refus échappe au catch et devient un 500.
    if (!id && methode === "POST") return await creer(request, env, membre, now);
    if (action === "cancel" && methode === "POST") {
      return (await store.annulerPost(env.DB, membre.id, id)) ? json({ annule: true }) : refus("Ce post n'est plus annulable : il est en cours ou déjà parti.", 409);
    }
    if (action === "resolve" && methode === "POST") {
      const { scheduled_at: quand } = await request.json();
      const date = quand ? dateProgrammee(quand, now) : null;
      return (await store.trancherPost(env.DB, membre.id, id, date)) ? json({ tranche: true }) : refus("Ce post n'attend aucune décision.", 409);
    }
    if (action === "stats" && methode === "GET") return await stats(env, membre, id);
    return refus("Introuvable", 404);
  } catch (erreur) {
    // RangeError : une entrée refusée par nos contrôles, le message est pour le membre.
    if (erreur instanceof RangeError || erreur instanceof SyntaxError) return refus(erreur.message);
    throw erreur;
  }
}
