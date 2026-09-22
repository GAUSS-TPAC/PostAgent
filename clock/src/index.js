/**
 * Horloge externe de Post-Agent.
 *
 * Seule responsabilité : déclencher le workflow GitHub toutes les 15 minutes.
 * Aucun handler `fetch` : le Worker n'a pas d'URL publique, donc pas de
 * surface d'attaque, et pas besoin d'un sous-domaine workers.dev. Le
 * déclenchement manuel passe par `gh workflow run publish.yml`.
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
};
