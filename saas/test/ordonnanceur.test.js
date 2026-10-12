import assert from "node:assert/strict";
import { test } from "node:test";
import { chiffrer } from "../src/crypto.js";
import { executer } from "../src/scheduler.js";
import * as store from "../src/store.js";
import { CLE, fauxD1, fauxFetch, linkedinQuiAccepte } from "./d1.js";

const T0 = new Date("2026-10-12T10:00:00Z");
const dans = (minutes) => store.iso(new Date(T0.getTime() + minutes * 60_000));

async function monde({ live = true, expire = dans(60 * 24 * 30) } = {}) {
  const DB = fauxD1();
  const env = { DB, TOKEN_KEY: CLE, ...(live ? { POSTAGENT_LIVE: "1" } : {}) };
  const membre = async (nom) => store.enregistrerMembre(DB, { urn: `urn:li:person:${nom}`, name: nom, tokenEnc: await chiffrer(CLE, `jeton-${nom}`), expire }, T0);
  const post = (userId, minutes, plus = {}) => store.creerPost(DB, userId, { text: "Bonjour", visibility: "CONNECTIONS", scheduledAt: dans(minutes), ...plus }, T0);
  return { DB, env, membre, post };
}

test("verrou fermé : rien n'est réservé, rien ne part", async (t) => {
  const m = await monde({ live: false });
  const appels = fauxFetch(t, linkedinQuiAccepte);
  const alan = await m.membre("alan");
  const id = await m.post(alan, -1);
  const bilan = await executer(m.env, T0);
  assert.deepEqual(bilan, { perimes: 0, publies: 0, echecs: 0, ignores: 1, ferme: true });
  assert.equal((await store.lirePost(m.DB, alan, id)).status, "scheduled");
  assert.equal(appels.length, 0);
});

test("post dû : publié une fois, jamais rejoué, post_id conservé", async (t) => {
  const m = await monde();
  const appels = fauxFetch(t, linkedinQuiAccepte);
  const alan = await m.membre("alan");
  const id = await m.post(alan, -1);
  const futur = await m.post(alan, 30);
  assert.equal((await executer(m.env, T0)).publies, 1);
  assert.equal((await executer(m.env, T0)).publies, 0);
  const post = await store.lirePost(m.DB, alan, id);
  assert.equal(post.status, "published");
  assert.match(post.post_id, /^urn:li:share:/);
  assert.equal((await store.lirePost(m.DB, alan, futur)).status, "scheduled");
  assert.equal(appels.filter((a) => a.url.endsWith("/rest/posts")).length, 1);
  assert.equal(appels[0].headers.Authorization, "Bearer jeton-alan");
});

test("deux exécutions concurrentes : un seul post sur LinkedIn", async (t) => {
  const m = await monde();
  const appels = fauxFetch(t, linkedinQuiAccepte);
  await m.post(await m.membre("alan"), -1);
  const bilans = await Promise.all([executer(m.env, T0), executer(m.env, T0)]);
  assert.equal(bilans[0].publies + bilans[1].publies, 1);
  assert.equal(appels.filter((a) => a.url.endsWith("/rest/posts")).length, 1);
});

test("deux membres : chacun publie avec son propre jeton et son propre URN", async (t) => {
  const m = await monde();
  const appels = fauxFetch(t, linkedinQuiAccepte);
  await m.post(await m.membre("alan"), -2);
  await m.post(await m.membre("bob"), -1);
  assert.equal((await executer(m.env, T0)).publies, 2);
  const vus = appels.map((a) => [a.headers.Authorization, JSON.parse(a.body).author]);
  assert.deepEqual(vus, [["Bearer jeton-alan", "urn:li:person:alan"], ["Bearer jeton-bob", "urn:li:person:bob"]]);
});

test("échec LinkedIn : statut failed, erreur gardée, pas de nouvel essai", async (t) => {
  const m = await monde();
  const appels = fauxFetch(t, () => new Response("panne", { status: 500 }));
  const alan = await m.membre("alan");
  const id = await m.post(alan, -1);
  assert.equal((await executer(m.env, T0)).echecs, 1);
  assert.equal((await executer(m.env, T0)).echecs, 0);
  const post = await store.lirePost(m.DB, alan, id);
  assert.equal(post.status, "failed");
  assert.match(post.error, /500/);
  assert.equal(appels.length, 1);
});

test("péremption : dû depuis plus de 3 h, déplacé en stale, aucun appel", async (t) => {
  const m = await monde();
  const appels = fauxFetch(t, linkedinQuiAccepte);
  const alan = await m.membre("alan");
  const id = await m.post(alan, -4 * 60);
  assert.equal((await executer(m.env, T0)).perimes, 1);
  assert.equal((await store.lirePost(m.DB, alan, id)).status, "stale");
  assert.equal(appels.length, 0);
});

test("jeton expiré : échec lisible avant tout appel réseau", async (t) => {
  const m = await monde({ expire: dans(-60) });
  const appels = fauxFetch(t, linkedinQuiAccepte);
  const alan = await m.membre("alan");
  const id = await m.post(alan, -1);
  await executer(m.env, T0);
  assert.match((await store.lirePost(m.DB, alan, id)).error, /reconnecte-toi/);
  assert.equal(appels.length, 0);
});

test("carrousel : rendu en PDF, envoyé comme document, média vidé après publication", async (t) => {
  const m = await monde();
  const appels = fauxFetch(t, linkedinQuiAccepte);
  const alan = await m.membre("alan");
  const carousel = JSON.stringify({ pages: [{ titre: "Le RAG" }, { titre: "Suite", corps: "- a" }] });
  const id = await m.post(alan, -1, { mediaKind: "carousel", mediaTitle: "Le RAG", carousel });
  const image = await m.post(alan, -1, { mediaKind: "image", mediaData: new Uint8Array([137, 80, 78, 71]).buffer });
  assert.equal((await executer(m.env, T0)).publies, 2);
  const envoi = appels.find((a) => a.method === "PUT");
  assert.equal(Buffer.from(envoi.body).subarray(0, 5).toString(), "%PDF-");
  const corps = appels.filter((a) => a.url.endsWith("/rest/posts")).map((a) => JSON.parse(a.body).content.media);
  assert.equal(corps[0].title, "Le RAG");
  assert.match(corps[1].id, /^urn:li:image:/);
  assert.equal((await store.lirePost(m.DB, alan, image)).media_data, null);
  assert.equal((await store.lirePost(m.DB, alan, id)).status, "published");
});

test("cloisonnement : un membre ne lit, n'annule ni ne tranche le post d'un autre", async () => {
  const m = await monde();
  const alan = await m.membre("alan");
  const bob = await m.membre("bob");
  const id = await m.post(alan, 30);
  assert.equal(await store.lirePost(m.DB, bob, id), null);
  assert.equal(await store.annulerPost(m.DB, bob, id), false);
  assert.equal(await store.trancherPost(m.DB, bob, id, null), false);
  assert.deepEqual(await store.listerPosts(m.DB, bob), []);
  assert.equal(await store.annulerPost(m.DB, alan, id), true);
  await store.supprimerCompte(m.DB, alan);
  assert.equal(await store.membreParUrn(m.DB, "urn:li:person:alan"), null);
  assert.ok(await store.membreParUrn(m.DB, "urn:li:person:bob"));
});
