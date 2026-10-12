import assert from "node:assert/strict";
import { test } from "node:test";
import { rendreCarrousel, validerCarrousel } from "../src/carousel.js";
import { chiffrer, dechiffrer } from "../src/crypto.js";
import * as li from "../src/linkedin.js";
import { CLE, fauxFetch, linkedinQuiAccepte } from "./d1.js";

const MOI = { token: "faux-jeton", urn: "urn:li:person:TEST" };

test("échappement little : identique à linkedin.py, # préservé", () => {
  assert.equal(li.escapeLittle("(a) [b] {c} @d #e *f* _g_ ~h~ <i> | \\"), "\\(a\\) \\[b\\] \\{c\\} \\@d #e \\*f\\* \\_g\\_ \\~h\\~ \\<i\\> \\| \\\\");
});

test("longueur en unités UTF-16 : 1 501 emoji refusés, 1 500 acceptés", () => {
  assert.throws(() => li.valider("😀".repeat(1501), "CONNECTIONS"), /3002 unités UTF-16/);
  assert.equal(li.valider("😀".repeat(1500), "CONNECTIONS").length, 3000);
  assert.throws(() => li.valider("(".repeat(1501), "CONNECTIONS"), /après échappement \(1501 avant\)/);
});

test("visibilité obligatoire, texte non vide", () => {
  assert.throws(() => li.valider("bonjour", undefined), /Visibilité invalide/);
  assert.throws(() => li.valider("   ", "PUBLIC"), /vide/);
});

test("verrou fermé : ni post, ni média, ni suppression, aucun appel réseau", async (t) => {
  const appels = fauxFetch(t, linkedinQuiAccepte);
  for (const live of [undefined, false, "1", 1]) {
    await assert.rejects(li.publier(MOI, { text: "x", visibility: "CONNECTIONS" }, { live }), li.PublicationFermee);
    await assert.rejects(li.envoyerMedia(MOI, "image", new Uint8Array(3), { live }), li.PublicationFermee);
    await assert.rejects(li.supprimer(MOI, "urn:li:share:1", { live }), li.PublicationFermee);
  }
  assert.equal(appels.length, 0);
});

test("publication avec document : forme du corps envoyé", async (t) => {
  const appels = fauxFetch(t, linkedinQuiAccepte);
  const urn = await li.envoyerMedia(MOI, "document", new Uint8Array([1, 2, 3]), { live: true });
  const id = await li.publier(MOI, { text: "Voir (ici)", visibility: "CONNECTIONS", media: { id: urn, title: "Le RAG" } }, { live: true });
  assert.match(id, /^urn:li:share:/);
  assert.equal(appels[1].method, "PUT");
  const corps = JSON.parse(appels[2].body);
  assert.deepEqual(corps.content, { media: { id: urn, title: "Le RAG" } });
  assert.equal(corps.commentary, "Voir \\(ici\\)");
  assert.equal(corps.author, MOI.urn);
  assert.equal(appels[2].headers["LinkedIn-Version"], li.LINKEDIN_VERSION);
});

test("201 sans identifiant : erreur qui demande de vérifier le profil, pas de second essai", async (t) => {
  const appels = fauxFetch(t, () => new Response(null, { status: 201 }));
  await assert.rejects(li.publier(MOI, { text: "x", visibility: "CONNECTIONS" }, { live: true }), /vérifier le profil/);
  assert.equal(appels.length, 1);
});

test("suppression : 404 rend false au lieu de lever", async (t) => {
  fauxFetch(t, () => new Response("", { status: 404 }));
  assert.equal(await li.supprimer(MOI, "urn:li:share:1", { live: true }), false);
});

test("chiffrement : aller-retour, vecteur neuf, altération détectée", async () => {
  const a = await chiffrer(CLE, "jeton-secret");
  assert.notEqual(a, await chiffrer(CLE, "jeton-secret"));
  assert.equal(await dechiffrer(CLE, a), "jeton-secret");
  assert.ok(!a.includes("jeton"));
  const altere = (a[20] === "A" ? "B" : "A") + a.slice(1);
  await assert.rejects(dechiffrer(CLE, altere));
  await assert.rejects(chiffrer("trop-court", "x"), /TOKEN_KEY/);
});

test("carrousel : PDF valide, une page par entrée, bornes respectées", () => {
  const pages = Array.from({ length: 5 }, (_, i) => ({ titre: `Page ${i + 1} — été`, corps: "- un\n- deux" }));
  const texte = Buffer.from(rendreCarrousel({ pages })).toString("latin1");
  assert.ok(texte.startsWith("%PDF-1.4") && texte.trimEnd().endsWith("%%EOF"));
  assert.equal((texte.match(/\/Type \/Page /g) ?? []).length, 5);
  assert.match(texte, /\/Count 5/);
  assert.ok(/^[\x00-\x7f]*$/.test(texte), "le PDF doit rester en ASCII pur");
  assert.throws(() => validerCarrousel({ pages: [{ titre: "seule" }] }), /2 à 10 pages/);
  assert.throws(() => validerCarrousel({ pages: [{ titre: "a" }, { corps: "sans titre" }] }), /Page 2 : titre manquant/);
});
