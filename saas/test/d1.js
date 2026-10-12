// Faux D1 pour les tests : la vraie syntaxe SQLite (node:sqlite), en mémoire,
// derrière la petite partie de l'API D1 que le code utilise.
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";

const SCHEMA = readFileSync(new URL("../schema.sql", import.meta.url), "utf8");
const lier = (p) => p.map((v) => (v instanceof ArrayBuffer ? new Uint8Array(v) : v));

export function fauxD1() {
  const db = new DatabaseSync(":memory:");
  db.exec(SCHEMA);
  const requete = (sql, params = []) => ({
    bind: (...p) => requete(sql, lier(p)),
    run: async () => ({ meta: { changes: Number(db.prepare(sql).run(...params).changes) } }),
    all: async () => ({ results: db.prepare(sql).all(...params) }),
    first: async () => db.prepare(sql).get(...params) ?? null,
  });
  return { prepare: (sql) => requete(sql), batch: async (liste) => Promise.all(liste.map((r) => r.run())) };
}

/** Remplace fetch par un faux qui note chaque appel. Rend la liste des appels. */
export function fauxFetch(t, repondre) {
  const appels = [];
  const vrai = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    appels.push({ url: String(url), ...options });
    return repondre(String(url), options, appels.length);
  };
  t.after(() => { globalThis.fetch = vrai; });
  return appels;
}

/** Faux LinkedIn : accepte tout, numérote les posts. */
export function linkedinQuiAccepte(url, options, n) {
  if (url.includes("action=initializeUpload")) {
    const genre = url.includes("/documents") ? "document" : "image";
    return Response.json({ value: { uploadUrl: "https://upload.test/x", [genre]: `urn:li:${genre}:M${n}` } });
  }
  if (url.startsWith("https://upload.test/")) return new Response(null, { status: 201 });
  if (url.endsWith("/rest/posts")) return new Response(null, { status: 201, headers: { "x-restli-id": `urn:li:share:${n}` } });
  return new Response("inattendu", { status: 500 });
}

export const CLE = Buffer.alloc(32, 7).toString("base64");
