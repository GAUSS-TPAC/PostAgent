/**
 * Connexion par LinkedIn (OAuth 2.0, code d'autorisation) et sessions.
 *
 * Le même parcours sert à s'inscrire, à se connecter et à renouveler l'accès :
 * LinkedIn ne donne pas de refresh token à ce type d'app, donc tous les deux
 * mois le membre repasse ici. Chaque passage redemande son consentement
 * (API Terms of Use §5.2) et remplace le jeton chiffré.
 *
 * Inscription sur invitation : un membre inconnu doit fournir INVITE_CODE.
 * Un membre déjà inscrit n'en a plus besoin.
 */

import { aleatoire, chiffrer, empreinte } from "./crypto.js";
import { moi } from "./linkedin.js";
import * as store from "./store.js";

const AUTORISER = "https://www.linkedin.com/oauth/v2/authorization";
const JETON = "https://www.linkedin.com/oauth/v2/accessToken";
const PORTEE = "openid profile email w_member_social";
const COOKIE = "sid";

const origine = (request, env) => env.PUBLIC_URL || new URL(request.url).origin;
const retourUrl = (request, env) => `${origine(request, env)}/auth/callback`;
const accueil = (message) => new Response(null, { status: 303, headers: { Location: `/?${new URLSearchParams(message)}` } });

/** Comparaison en temps constant, pour ne pas laisser deviner le code d'invitation. */
function egal(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let ecart = 0;
  for (let i = 0; i < a.length; i += 1) ecart |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return ecart === 0;
}

/** POST /auth/login : contrôle le consentement, puis envoie vers LinkedIn. */
export async function demarrer(request, env) {
  const formulaire = await request.formData();
  if (formulaire.get("consent") !== "oui") return accueil({ erreur: "Le consentement est nécessaire pour connecter LinkedIn." });
  const inviteOk = Boolean(env.INVITE_CODE) && egal(String(formulaire.get("invite") ?? ""), env.INVITE_CODE);
  const state = await store.creerEtat(env.DB, inviteOk);
  const params = new URLSearchParams({
    response_type: "code",
    client_id: env.LINKEDIN_CLIENT_ID,
    redirect_uri: retourUrl(request, env),
    state,
    scope: env.LINKEDIN_SCOPES || PORTEE,
  });
  return new Response(null, { status: 303, headers: { Location: `${AUTORISER}?${params}` } });
}

/** GET /auth/callback : échange le code, enregistre le membre, ouvre la session. */
export async function retour(request, env, now = new Date()) {
  const url = new URL(request.url);
  if (url.searchParams.get("error")) return accueil({ erreur: "Connexion LinkedIn annulée." });
  // L'état ne sert qu'une fois : un retour rejoué ou forgé est refusé ici.
  const etat = await store.consommerEtat(env.DB, url.searchParams.get("state"), now);
  if (!etat) return accueil({ erreur: "Lien de connexion expiré ou déjà utilisé. Recommence." });

  const echange = await fetch(JETON, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code: url.searchParams.get("code") ?? "",
      redirect_uri: retourUrl(request, env),
      client_id: env.LINKEDIN_CLIENT_ID,
      client_secret: env.LINKEDIN_CLIENT_SECRET,
    }),
  });
  if (!echange.ok) return accueil({ erreur: `LinkedIn a refusé la connexion (${echange.status}).` });
  const { access_token: jeton, expires_in: duree } = await echange.json();

  const membre = await moi(jeton);
  if (!etat.invite_ok && !(await store.membreParUrn(env.DB, membre.urn))) {
    // Le jeton reçu n'est gardé nulle part : il disparaît avec cette requête.
    return accueil({ erreur: "Inscription sur invitation : le code est absent ou faux." });
  }

  const userId = await store.enregistrerMembre(env.DB, {
    urn: membre.urn,
    name: membre.name,
    tokenEnc: await chiffrer(env.TOKEN_KEY, jeton),
    expire: store.iso(new Date(now.getTime() + duree * 1000)),
  }, now);

  const sid = aleatoire(32);
  await store.ouvrirSession(env.DB, userId, await empreinte(sid), now);
  return new Response(null, {
    status: 303,
    headers: { Location: "/", "Set-Cookie": `${COOKIE}=${sid}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=2592000` },
  });
}

function lireSid(request) {
  const trouve = (request.headers.get("Cookie") ?? "").match(/(?:^|;\s*)sid=([0-9a-f]{64})/);
  return trouve ? trouve[1] : null;
}

/** Le membre de la requête, ou null. */
export async function membreCourant(request, env, now = new Date()) {
  const sid = lireSid(request);
  return sid ? store.membreDeSession(env.DB, await empreinte(sid), now) : null;
}

/** POST /auth/logout */
export async function sortir(request, env) {
  const sid = lireSid(request);
  if (sid) await store.fermerSession(env.DB, await empreinte(sid));
  return new Response(null, { status: 303, headers: { Location: "/", "Set-Cookie": `${COOKIE}=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0` } });
}
