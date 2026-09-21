/**
 * Horloge externe de Post-Agent.
 *
 * Seule responsabilité : déclencher le workflow GitHub toutes les 15 minutes.
 * Ce Worker ne lit pas la file, ne décide pas ce qui doit partir et ne connaît
 * pas LinkedIn. publisher.py décide. Une horloge qui raisonne est une horloge
 * qui tombe en panne.
 *
 * Raison d'être : le cron GitHub dérive de 2 h à 5 h 30 en conditions réelles
 * (12 exécutions mesurées sur 40 h au lieu de 160). Il est conservé en secours.
 */

const GITHUB_API = "https://api.github.com";

async function dispatch(env) {
  const url = `${GITHUB_API}/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/dispatches`;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.DISPATCH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      // GitHub rejette les requêtes sans User-Agent.
      "User-Agent": "post-agent-clock",
    },
    body: JSON.stringify({ event_type: "publish" }),
  });

  // 204 attendu. Tout le reste est une anomalie.
  if (response.status !== 204) {
    const body = await response.text();
    throw new Error(`dispatch refusé (${response.status}) : ${body}`);
  }
}

/**
 * Compare la clé fournie au secret, sans fuite par le temps de réponse.
 *
 * Un `!==` sur des chaînes s'arrête au premier caractère différent : le temps
 * de réponse laisse alors deviner la clé caractère par caractère. Le hachage
 * préalable ramène les deux valeurs à une taille fixe, ce qui évite en plus de
 * divulguer la longueur du secret.
 */
async function keyMatches(provided, expected) {
  if (typeof provided !== "string" || typeof expected !== "string") return false;
  const encoder = new TextEncoder();
  const [a, b] = await Promise.all([
    crypto.subtle.digest("SHA-256", encoder.encode(provided)),
    crypto.subtle.digest("SHA-256", encoder.encode(expected)),
  ]);
  return crypto.subtle.timingSafeEqual(a, b);
}

export default {
  // Déclenché par le Cron Trigger défini dans wrangler.toml.
  async scheduled(event, env, ctx) {
    try {
      await dispatch(env);
      // JSON plutôt que concaténation : les journaux de la plateforme sont
      // ainsi interrogeables par champ. L'horodatage est ajouté par Cloudflare.
      console.log(JSON.stringify({ event: "dispatch", ok: true, cron: event.cron }));
    } catch (error) {
      // Visible dans `wrangler tail` et dans les logs du tableau de bord.
      // La panne silencieuse est couverte par ailleurs : sans dispatch, les
      // posts dépassent STALE_AFTER et le workflow passe au rouge.
      console.error(JSON.stringify({ event: "dispatch", ok: false, error: error.message }));
      throw error;
    }
  },

  // Déclenchement manuel, pour vérifier la configuration sans attendre le cron.
  // Protégé par un secret partagé : l'URL d'un Worker est publique.
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname !== "/trigger") {
      return new Response("post-agent-clock", { status: 200 });
    }
    if (!(await keyMatches(request.headers.get("X-Trigger-Key"), env.TRIGGER_KEY))) {
      return new Response("refusé\n", { status: 403 });
    }

    try {
      await dispatch(env);
      return new Response("dispatch émis\n", { status: 200 });
    } catch (error) {
      return new Response(`${error.message}\n`, { status: 502 });
    }
  },
};
