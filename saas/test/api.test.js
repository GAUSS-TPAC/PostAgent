import assert from "node:assert/strict";
import { test } from "node:test";
import { empreinte } from "../src/crypto.js";
import worker from "../src/index.js";
import * as store from "../src/store.js";
import { CLE, fauxD1, fauxFetch } from "./d1.js";

const SID_A = "a".repeat(64);
const SID_B = "b".repeat(64);
const BASE = "https://postagent.test";

async function monde() {
  const DB = fauxD1();
  const env = { DB, TOKEN_KEY: CLE, LINKEDIN_CLIENT_ID: "id", LINKEDIN_CLIENT_SECRET: "secret", INVITE_CODE: "sesame" };
  for (const [nom, sid] of [["alan", SID_A], ["bob", SID_B]]) {
    const id = await store.enregistrerMembre(DB, { urn: `urn:li:person:${nom}`, name: nom, tokenEnc: "x", expire: "2099-01-01T00:00:00.000Z" });
    await store.ouvrirSession(DB, id, await empreinte(sid));
  }
  const appel = (chemin, { sid = SID_A, method = "GET", body, entete = true } = {}) => worker.fetch(new Request(BASE + chemin, {
    method,
    headers: { ...(sid ? { Cookie: `sid=${sid}` } : {}), ...(method !== "GET" && entete ? { "X-PostAgent": "1" } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  }), env);
  return { DB, env, appel };
}

const DEMAIN = new Date(Date.now() + 86_400_000).toISOString();
const post = (plus = {}) => ({ text: "Bonjour", visibility: "CONNECTIONS", scheduled_at: DEMAIN, ...plus });

test("sans session : 401 ; écriture sans l'en-tête de la page : 403", async () => {
  const m = await monde();
  assert.equal((await m.appel("/api/posts", { sid: null })).status, 401);
  assert.equal((await m.appel("/api/posts", { sid: "c".repeat(64) })).status, 401);
  assert.equal((await m.appel("/api/posts", { method: "POST", body: post(), entete: false })).status, 403);
});

test("création : les mêmes refus que le client LinkedIn, avant d'écrire en base", async () => {
  const m = await monde();
  const refuse = async (corps, motif) => {
    const r = await m.appel("/api/posts", { method: "POST", body: corps });
    assert.equal(r.status, 400);
    assert.match((await r.json()).erreur, motif);
  };
  await refuse(post({ visibility: undefined }), /Visibilité invalide/);
  await refuse(post({ text: "  " }), /vide/);
  await refuse(post({ scheduled_at: "2030-01-01T09:00:00" }), /sans fuseau/);
  await refuse(post({ scheduled_at: "2020-01-01T09:00:00Z" }), /dans le passé/);
  await refuse(post({ media: { kind: "image", data: btoa("pas une image") } }), /JPG, PNG ou GIF/);
  await refuse(post({ media: { kind: "document", data: btoa("%PDF-1.4") } }), /besoin d'un titre/);
  await refuse(post({ media: { kind: "carousel", spec: { pages: [{ titre: "seule" }] } } }), /2 à 10 pages/);
  assert.deepEqual((await (await m.appel("/api/posts")).json()).posts, []);
});

test("un post programmé n'est visible et annulable que par son auteur", async () => {
  const m = await monde();
  const cree = await m.appel("/api/posts", { method: "POST", body: post({ media: { kind: "carousel", spec: { pages: [{ titre: "Un" }, { titre: "Deux" }] } } }) });
  assert.equal(cree.status, 201);
  const { id } = await cree.json();
  const [mien] = (await (await m.appel("/api/posts")).json()).posts;
  assert.equal(mien.media_kind, "carousel");
  assert.equal(mien.media_title, "Un");
  assert.ok(!("media_data" in mien) && !("carousel" in mien));
  assert.deepEqual((await (await m.appel("/api/posts", { sid: SID_B })).json()).posts, []);
  assert.equal((await m.appel(`/api/posts/${id}/cancel`, { sid: SID_B, method: "POST", body: {} })).status, 409);
  assert.equal((await m.appel(`/api/posts/${id}/cancel`, { method: "POST", body: {} })).status, 200);
  assert.equal((await m.appel(`/api/posts/${id}/cancel`, { method: "POST", body: {} })).status, 409);
});

test("aperçu de carrousel : un PDF ; /api/me n'expose aucun jeton", async () => {
  const m = await monde();
  const pdf = await m.appel("/api/carousel", { method: "POST", body: { spec: { pages: [{ titre: "A" }, { titre: "B" }] } } });
  assert.equal(pdf.headers.get("Content-Type"), "application/pdf");
  assert.equal(new TextDecoder().decode((await pdf.arrayBuffer()).slice(0, 5)), "%PDF-");
  const moi = await (await m.appel("/api/me")).json();
  assert.deepEqual(Object.keys(moi).sort(), ["jours_restants", "name", "publication_ouverte", "token_expires_at"]);
  assert.equal(moi.publication_ouverte, false);
});

test("suppression de compte : tout disparaît, la session avec", async () => {
  const m = await monde();
  await m.appel("/api/posts", { method: "POST", body: post() });
  assert.equal((await m.appel("/api/account", { method: "DELETE" })).status, 200);
  assert.equal((await m.appel("/api/me")).status, 401);
  assert.equal((await m.appel("/api/me", { sid: SID_B })).status, 200);
});

test("connexion : consentement exigé, état à usage unique, invitation pour les inconnus", async (t) => {
  const m = await monde();
  const formulaire = (champs) => worker.fetch(new Request(`${BASE}/auth/login`, { method: "POST", body: new URLSearchParams(champs) }), m.env);
  const sansAccord = await formulaire({ invite: "sesame" });
  assert.match(decodeURIComponent(sansAccord.headers.get("Location")), /consentement/);

  const state = async (champs) => new URL((await formulaire(champs)).headers.get("Location")).searchParams.get("state");
  fauxFetch(t, (url) => (url.includes("accessToken")
    ? Response.json({ access_token: "jeton-carla", expires_in: 5_184_000 })
    : Response.json({ sub: "carla", name: "Carla" })));
  const retour = (s) => worker.fetch(new Request(`${BASE}/auth/callback?code=c&state=${s}`), m.env);

  const refuse = await retour(await state({ consent: "oui", invite: "faux" }));
  assert.match(decodeURIComponent(refuse.headers.get("Location")), /invitation/);
  assert.equal(await store.membreParUrn(m.DB, "urn:li:person:carla"), null);

  const bon = await state({ consent: "oui", invite: "sesame" });
  const accepte = await retour(bon);
  assert.match(accepte.headers.get("Set-Cookie"), /^sid=[0-9a-f]{64}; HttpOnly; Secure; SameSite=Lax/);
  const carla = await m.DB.prepare("SELECT token_enc FROM users WHERE person_urn = ?").bind("urn:li:person:carla").first();
  assert.ok(carla.token_enc && !carla.token_enc.includes("jeton-carla"), "le jeton doit être chiffré en base");
  assert.match(decodeURIComponent((await retour(bon)).headers.get("Location")).replaceAll("+", " "), /expiré ou déjà utilisé/);
});

test("rédaction assistée : brouillon structuré, jamais enregistré ; refus et absence de clé lisibles", async (t) => {
  const m = await monde();
  const generer = (corps) => m.appel("/api/generate", { method: "POST", body: corps });
  assert.match((await (await generer({ sujet: "le RAG" })).json()).erreur, /pas activée/);

  m.env.ANTHROPIC_API_KEY = "cle-de-test";
  const brouillon = { texte: "Un modèle ne sait que ce qu'il a lu.", titre_carrousel: "Le RAG", pages: [{ titre: "Le RAG", corps: "En bref" }, { titre: "Suite", corps: "- a" }] };
  let stop = "end_turn";
  const appels = fauxFetch(t, () => Response.json({
    id: "msg_1", type: "message", role: "assistant", model: "claude-opus-5-5", stop_reason: stop,
    content: [{ type: "text", text: JSON.stringify(brouillon) }], usage: { input_tokens: 1, output_tokens: 1 },
  }));

  const avec = await (await generer({ sujet: "le RAG", carrousel: true })).json();
  assert.equal(avec.texte, brouillon.texte);
  assert.equal(avec.carrousel.pages.length, 2);
  const sans = await (await generer({ sujet: "le RAG", carrousel: false })).json();
  assert.equal(sans.carrousel, null);

  const envoye = JSON.parse(appels[0].body);
  assert.equal(envoye.model, "claude-opus-5-5");
  assert.equal(envoye.fallbacks, "default");
  assert.equal(envoye.output_config.format.type, "json_schema");
  assert.match(new Headers(appels[0].headers).get("anthropic-beta"), /server-side-fallback-2026-07-01/);
  assert.equal(new Headers(appels[0].headers).get("x-api-key"), "cle-de-test");

  stop = "refusal";
  assert.match((await (await generer({ sujet: "x" })).json()).erreur, /refusé par le modèle/);
  assert.equal((await generer({ sujet: "a".repeat(601) })).status, 400);
  assert.deepEqual((await (await m.appel("/api/posts")).json()).posts, []);
});
