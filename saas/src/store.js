/**
 * Accès à la base D1. Seul module qui écrit du SQL.
 *
 * Règle de cloisonnement : toute fonction appelée pour un membre prend son
 * `userId` et le met dans le WHERE. Les seules requêtes sans propriétaire
 * sont celles de l'ordonnanceur, qui traite les posts dus de tout le monde.
 */

import { aleatoire } from "./crypto.js";

// Colonnes renvoyées à l'interface : jamais le média, jamais un jeton.
const RESUME = "id, text, visibility, media_kind, media_title, scheduled_at, status, post_id, error, created_at, published_at";

export const iso = (date = new Date()) => date.toISOString();

// ---- connexion ----

export async function creerEtat(db, inviteOk, now = new Date()) {
  const state = aleatoire();
  await db.prepare("DELETE FROM oauth_states WHERE expires_at < ?").bind(iso(now)).run();
  await db.prepare("INSERT INTO oauth_states (state, invite_ok, expires_at) VALUES (?, ?, ?)")
    .bind(state, inviteOk ? 1 : 0, iso(new Date(now.getTime() + 10 * 60_000))).run();
  return state;
}

/** Consomme un état OAuth : il ne sert qu'une fois. Retourne { invite_ok } ou null. */
export async function consommerEtat(db, state, now = new Date()) {
  const ligne = await db.prepare("DELETE FROM oauth_states WHERE state = ? AND expires_at > ? RETURNING invite_ok")
    .bind(state ?? "", iso(now)).first();
  return ligne ?? null;
}

export const membreParUrn = (db, urn) => db.prepare("SELECT id FROM users WHERE person_urn = ?").bind(urn).first();

/** Crée le membre ou met à jour son jeton et son consentement. Retourne son id. */
export async function enregistrerMembre(db, { urn, name, tokenEnc, expire }, now = new Date()) {
  const existant = await membreParUrn(db, urn);
  if (existant) {
    await db.prepare("UPDATE users SET name = ?, token_enc = ?, token_expires_at = ?, consent_at = ? WHERE id = ?")
      .bind(name, tokenEnc, expire, iso(now), existant.id).run();
    return existant.id;
  }
  const id = aleatoire(12);
  await db.prepare("INSERT INTO users (id, person_urn, name, token_enc, token_expires_at, consent_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)")
    .bind(id, urn, name, tokenEnc, expire, iso(now), iso(now)).run();
  return id;
}

export async function ouvrirSession(db, userId, empreinteSid, now = new Date()) {
  await db.prepare("INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)")
    .bind(empreinteSid, userId, iso(new Date(now.getTime() + 30 * 86_400_000))).run();
}

export const membreDeSession = (db, empreinteSid, now = new Date()) =>
  db.prepare("SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.id = ? AND s.expires_at > ?")
    .bind(empreinteSid, iso(now)).first();

export const fermerSession = (db, empreinteSid) => db.prepare("DELETE FROM sessions WHERE id = ?").bind(empreinteSid).run();

/** Efface tout ce qui concerne un membre : jeton, posts, sessions (API Terms §4.4). */
export async function supprimerCompte(db, userId) {
  await db.batch([
    db.prepare("DELETE FROM posts WHERE user_id = ?").bind(userId),
    db.prepare("DELETE FROM sessions WHERE user_id = ?").bind(userId),
    db.prepare("DELETE FROM users WHERE id = ?").bind(userId),
  ]);
}

// ---- posts d'un membre ----

export async function creerPost(db, userId, post, now = new Date()) {
  const id = aleatoire(12);
  await db.prepare(
    "INSERT INTO posts (id, user_id, text, visibility, media_kind, media_title, media_data, carousel, scheduled_at, status, created_at) " +
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'scheduled', ?)",
  ).bind(id, userId, post.text, post.visibility, post.mediaKind ?? null, post.mediaTitle ?? null,
    post.mediaData ?? null, post.carousel ?? null, post.scheduledAt, iso(now)).run();
  return id;
}

export const listerPosts = async (db, userId) =>
  (await db.prepare(`SELECT ${RESUME} FROM posts WHERE user_id = ? ORDER BY scheduled_at DESC LIMIT 200`).bind(userId).all()).results;

export const lirePost = (db, userId, id) =>
  db.prepare("SELECT * FROM posts WHERE id = ? AND user_id = ?").bind(id, userId).first();

/** Annule un post encore programmé. false s'il n'est plus annulable. */
export async function annulerPost(db, userId, id) {
  const r = await db.prepare("UPDATE posts SET status = 'cancelled' WHERE id = ? AND user_id = ? AND status = 'scheduled'")
    .bind(id, userId).run();
  return r.meta.changes === 1;
}

/**
 * Tranche un post en panne (échec, périmé, ou resté « en cours »).
 * `scheduledAt` nul : abandon. Sinon : reprogrammation. C'est une décision
 * humaine — rien ne repart jamais tout seul.
 */
export async function trancherPost(db, userId, id, scheduledAt) {
  const sql = scheduledAt
    ? "UPDATE posts SET status = 'scheduled', scheduled_at = ?, error = NULL WHERE id = ? AND user_id = ? AND status IN ('failed', 'stale', 'publishing')"
    : "UPDATE posts SET status = 'cancelled' WHERE id = ? AND user_id = ? AND status IN ('failed', 'stale', 'publishing')";
  const liaison = scheduledAt ? [scheduledAt, id, userId] : [id, userId];
  return (await db.prepare(sql).bind(...liaison).run()).meta.changes === 1;
}

// ---- ordonnanceur : tous les membres ----

export async function perimer(db, limite) {
  const r = await db.prepare(
    "UPDATE posts SET status = 'stale', error = 'Heure dépassée de plus de 3 h : non publié' WHERE status = 'scheduled' AND scheduled_at < ?",
  ).bind(limite).run();
  return r.meta.changes;
}

export const postsDus = async (db, maintenant) =>
  (await db.prepare("SELECT id FROM posts WHERE status = 'scheduled' AND scheduled_at <= ? ORDER BY scheduled_at LIMIT 20").bind(maintenant).all()).results;

/**
 * Réserve un post pour publication. C'est le verrou d'idempotence : la mise
 * à jour est conditionnelle et atomique, donc deux exécutions concurrentes ne
 * peuvent pas réserver le même post. false : quelqu'un d'autre l'a pris.
 */
export async function reserver(db, id) {
  const r = await db.prepare("UPDATE posts SET status = 'publishing' WHERE id = ? AND status = 'scheduled'").bind(id).run();
  return r.meta.changes === 1;
}

export const postAvecMembre = (db, id) =>
  db.prepare("SELECT p.*, u.person_urn, u.token_enc, u.token_expires_at FROM posts p JOIN users u ON u.id = p.user_id WHERE p.id = ?").bind(id).first();

export const marquerPublie = (db, id, postId, now = new Date()) =>
  db.prepare("UPDATE posts SET status = 'published', post_id = ?, published_at = ?, media_data = NULL, error = NULL WHERE id = ?")
    .bind(postId, iso(now), id).run();

export const marquerEchec = (db, id, erreur) =>
  db.prepare("UPDATE posts SET status = 'failed', error = ? WHERE id = ?").bind(String(erreur).slice(0, 500), id).run();
