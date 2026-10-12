/**
 * Client LinkedIn du SaaS, sans état. Portage de linkedin.py, médias en plus.
 *
 * Ne connaît ni la base, ni les sessions, ni l'ordonnanceur : chaque fonction
 * reçoit les identifiants du membre ({ token, urn }) et rien d'autre.
 *
 * Verrou de publication : toute écriture (envoi de média, post, suppression)
 * exige `live === true`. L'appelant le tire de env.POSTAGENT_LIVE, qui n'est
 * posé qu'en production. Sans lui, rien ne part — ni en test, ni en local.
 *
 * Les règles ci-dessous viennent chacune d'une mesure ou d'un incident de
 * l'instance Python (voir files/CLAUDE.md) : ne pas les « simplifier ».
 */

// Vérifié sur Microsoft Learn le 14/09/2026. À remonter avant l'été 2027.
export const LINKEDIN_VERSION = "202608";
export const MAX_COMMENTARY = 3000;
const API = "https://api.linkedin.com";
const VISIBILITES = ["PUBLIC", "CONNECTIONS"];

/** Réponse inattendue de l'API. Porte le code HTTP et le corps brut. */
export class LinkedInError extends Error {
  constructor(status, body) {
    super(`LinkedIn a répondu ${status} : ${body}`);
    this.status = status;
    this.body = body;
  }
}

/** Écriture demandée alors que le verrou de publication est fermé. */
export class PublicationFermee extends Error {}

function exigerOuvert(live, action) {
  if (live !== true) {
    throw new PublicationFermee(
      `${action} refusé avant tout appel réseau : POSTAGENT_LIVE n'est pas posé.`,
    );
  }
}

/** Échappe le texte brut pour le champ commentary (format « little »).
 *  '#' reste tel quel pour garder les hashtags actifs. */
export function escapeLittle(text) {
  return text.replace(/([\\|{}@\[\]()<>*_~])/g, "\\$1");
}

/** Longueur en unités UTF-16 : c'est exactement `length` en JavaScript. */
export const utf16Length = (text) => text.length;

/** Contrôles communs, sans réseau. Retourne le commentary échappé. */
export function valider(text, visibility) {
  if (!text || !text.trim()) throw new RangeError("Texte de post vide");
  // Pas de valeur par défaut : l'omission est une erreur, jamais un
  // consentement à publier en public (incident du 14/09/2026).
  if (!VISIBILITES.includes(visibility)) {
    throw new RangeError(`Visibilité invalide : ${visibility}`);
  }
  const commentary = escapeLittle(text);
  if (commentary.length > MAX_COMMENTARY) {
    let detail = `${commentary.length} unités UTF-16`;
    if (commentary.length !== text.length) detail += ` après échappement (${text.length} avant)`;
    throw new RangeError(`Texte trop long : ${detail}, maximum ${MAX_COMMENTARY}`);
  }
  return commentary;
}

function entetes(token, json = true) {
  const h = {
    Authorization: `Bearer ${token}`,
    "LinkedIn-Version": LINKEDIN_VERSION,
    "X-Restli-Protocol-Version": "2.0.0",
  };
  if (json) h["Content-Type"] = "application/json";
  return h;
}

/**
 * Envoie un média et retourne son URN. `genre` vaut "image" ou "document".
 * Un média envoyé n'est pas un post : il n'apparaît nulle part tant qu'aucun
 * post ne le cite. Il passe quand même par le verrou — il écrit sur le compte.
 */
export async function envoyerMedia({ token, urn }, genre, octets, { live }) {
  if (!["image", "document"].includes(genre)) throw new RangeError(`Média inconnu : ${genre}`);
  if (!octets || !octets.byteLength) throw new RangeError("Média vide");
  exigerOuvert(live, "Envoi de média");

  const init = await fetch(`${API}/rest/${genre}s?action=initializeUpload`, {
    method: "POST",
    headers: entetes(token),
    body: JSON.stringify({ initializeUploadRequest: { owner: urn } }),
  });
  if (!init.ok) throw new LinkedInError(init.status, await init.text());
  const { value } = await init.json();
  // La doc ne montre pas le corps de la réponse pour les documents : on
  // refuse d'avancer à l'aveugle si la forme n'est pas celle attendue.
  if (!value?.uploadUrl || !value?.[genre]) {
    throw new LinkedInError(init.status, `initializeUpload sans uploadUrl ou sans ${genre}`);
  }

  const envoi = await fetch(value.uploadUrl, {
    method: "PUT",
    headers: { Authorization: `Bearer ${token}` },
    body: octets,
  });
  if (!envoi.ok) throw new LinkedInError(envoi.status, await envoi.text());
  return value[genre];
}

/**
 * Publie un post. Retourne le post_id — ne jamais jeter ce retour : sans lui
 * le post est irrécupérable, l'API refuse de lister les posts d'un membre.
 *
 * `media` est facultatif : { id: "urn:li:image:…" | "urn:li:document:…", title?, altText? }.
 * Aucune nouvelle tentative : un 5xx peut masquer un post réellement créé.
 */
export async function publier({ token, urn }, { text, visibility, media }, { live }) {
  const commentary = valider(text, visibility);
  if (media && !/^urn:li:(image|document):/.test(media.id ?? "")) {
    throw new RangeError(`URN de média invalide : ${media.id}`);
  }
  // Dernier point d'arrêt avant le réseau, après les contrôles : la
  // validation reste testable, seule la publication est interdite.
  exigerOuvert(live, "Publication");

  const corps = {
    author: urn,
    commentary,
    visibility,
    distribution: { feedDistribution: "MAIN_FEED", targetEntities: [], thirdPartyDistributionChannels: [] },
    lifecycleState: "PUBLISHED",
    isReshareDisabledByAuthor: false,
  };
  if (media) {
    corps.content = { media: { id: media.id } };
    if (media.title) corps.content.media.title = media.title;
    if (media.altText) corps.content.media.altText = media.altText;
  }

  const reponse = await fetch(`${API}/rest/posts`, {
    method: "POST",
    headers: entetes(token),
    body: JSON.stringify(corps),
  });
  if (reponse.status !== 201) throw new LinkedInError(reponse.status, await reponse.text());
  const postId = reponse.headers.get("x-restli-id");
  // Le post est probablement parti : on le signale plutôt que de réessayer.
  if (!postId) throw new LinkedInError(201, "réponse sans en-tête x-restli-id, vérifier le profil");
  return postId;
}

/** Supprime un post. true s'il a été supprimé, false s'il n'existait plus.
 *  LinkedIn annonce l'opération idempotente mais renvoie 404 (constat du 21/09). */
export async function supprimer({ token }, postId, { live }) {
  if (!postId?.startsWith("urn:li:")) throw new RangeError(`post_id invalide : ${postId}`);
  exigerOuvert(live, "Suppression");
  const reponse = await fetch(`${API}/rest/posts/${encodeURIComponent(postId)}`, {
    method: "DELETE",
    headers: { ...entetes(token, false), "X-RestLi-Method": "DELETE" },
  });
  if (reponse.status === 200 || reponse.status === 204) return true;
  if (reponse.status === 404) return false;
  throw new LinkedInError(reponse.status, await reponse.text());
}

/** Identité du membre du token. Une lecture : ne passe pas par le verrou. */
export async function moi(token) {
  const reponse = await fetch(`${API}/v2/userinfo`, { headers: { Authorization: `Bearer ${token}` } });
  if (!reponse.ok) throw new LinkedInError(reponse.status, await reponse.text());
  const data = await reponse.json();
  return { urn: `urn:li:person:${data.sub}`, name: data.name ?? null };
}

/**
 * Statistiques d'un post (impressions, réactions…). Exige la permission
 * `r_member_postAnalytics`, incluse seulement dans la Community Management
 * API : sans elle LinkedIn répond 403, que l'appelant doit dire tel quel.
 */
export async function statistiques({ token }, postId, metrique = "IMPRESSION") {
  const genre = postId.startsWith("urn:li:ugcPost:") ? "ugc" : "share";
  const entite = `(${genre}:${encodeURIComponent(postId)})`;
  const url = `${API}/rest/memberCreatorPostAnalytics?q=entity&entity=${entite}&queryType=${metrique}&aggregation=TOTAL`;
  const reponse = await fetch(url, { headers: entetes(token, false) });
  if (!reponse.ok) throw new LinkedInError(reponse.status, await reponse.text());
  const data = await reponse.json();
  return data.elements?.[0]?.count ?? 0;
}
