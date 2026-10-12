/**
 * Point d'entrée du Worker PostAgent (SaaS).
 *
 *   /auth/*   connexion par LinkedIn, sessions
 *   /api/*    API de l'interface, toujours pour le membre connecté
 *   le reste  fichiers statiques de public/ (servis par la plateforme)
 *   cron      l'ordonnanceur, chaque minute
 *
 * Le Worker ne garde aucun état en mémoire : tout est dans D1.
 */

import { api } from "./api.js";
import { demarrer, membreCourant, retour, sortir } from "./oauth.js";
import { executer } from "./scheduler.js";

const json = (corps, status) => Response.json(corps, { status });

async function router(request, env) {
  const { pathname } = new URL(request.url);

  if (pathname === "/auth/login" && request.method === "POST") return demarrer(request, env);
  if (pathname === "/auth/callback" && request.method === "GET") return retour(request, env);
  if (pathname === "/auth/logout" && request.method === "POST") return sortir(request, env);

  if (pathname.startsWith("/api/")) {
    const membre = await membreCourant(request, env);
    if (!membre) return json({ erreur: "Non connecté" }, 401);
    return api(request, env, membre);
  }
  return json({ erreur: "Introuvable" }, 404);
}

export default {
  async fetch(request, env) {
    try {
      const reponse = await router(request, env);
      // Les réponses de l'API portent des données personnelles : jamais en cache.
      const entetes = new Headers(reponse.headers);
      entetes.set("Cache-Control", "no-store");
      entetes.set("X-Content-Type-Options", "nosniff");
      return new Response(reponse.body, { status: reponse.status, headers: entetes });
    } catch (erreur) {
      // Le détail va dans les journaux, pas chez le visiteur. Le message
      // d'une erreur ne contient jamais de texte de post ni de jeton.
      console.error(JSON.stringify({ event: "erreur", message: String(erreur?.message ?? erreur) }));
      return json({ erreur: "Erreur interne. Rien n'a été publié par cette requête." }, 500);
    }
  },

  async scheduled(event, env) {
    const bilan = await executer(env);
    // Des nombres seulement : interrogeables par champ, sans contenu.
    if (bilan.publies || bilan.echecs || bilan.perimes || bilan.ignores) {
      console.log(JSON.stringify({ event: "ordonnanceur", ...bilan }));
    }
  },
};
