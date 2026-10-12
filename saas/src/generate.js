/**
 * Rédaction assistée : un sujet -> un brouillon de post, et s'il est demandé
 * un carrousel de 4 à 6 pages.
 *
 * Ce module ne publie rien et n'écrit rien en base : il rend un brouillon que
 * le membre relit, corrige, puis programme lui-même avec la visibilité de son
 * choix. Le brouillon n'engage personne tant qu'il n'est pas programmé.
 */

import Anthropic from "@anthropic-ai/sdk";
import { PAGES_MAX } from "./carousel.js";
import { MAX_COMMENTARY } from "./linkedin.js";

export const SUJET_MAX = 600;

const CONSIGNES = `Tu rédiges des posts LinkedIn en français pour un professionnel qui partage ce qu'il sait.

Le post
- Une accroche concrète dès la première ligne : un fait, un constat, une question précise. Pas de formule d'annonce.
- Des paragraphes courts séparés par une ligne vide, entre 600 et 1 300 caractères au total.
- Un ton direct, à la première personne, sans jargon inutile ni superlatifs. Explique comme à un collègue d'un autre métier.
- Texte brut : pas de Markdown, pas d'astérisques ni de dièses de titre. Deux ou trois hashtags à la fin, pas plus.
- N'invente ni chiffre, ni client, ni anecdote personnelle : tu ne connais pas la vie de l'auteur. Si un exemple aide, présente-le comme un exemple.

Le carrousel, quand il est demandé
- 4 à 6 pages. La première est la couverture : un titre qui donne envie d'ouvrir, et une phrase de promesse.
- Une idée par page. Un titre de moins de 40 caractères, un corps de moins de 220 caractères.
- Dans un corps, une ligne qui commence par « - » devient une puce : trois puces au plus.
- La dernière page résume ou donne la prochaine étape.
- Aucun emoji dans le carrousel : sa police ne les affiche pas.
- Quand un carrousel accompagne le post, le post l'annonce en une phrase au lieu de le répéter.

Quand aucun carrousel n'est demandé, rends une liste de pages vide.`;

const FORME = {
  type: "object",
  properties: {
    texte: { type: "string", description: "Le texte du post, prêt à relire." },
    titre_carrousel: { type: "string", description: "Titre du document, vide s'il n'y a pas de carrousel." },
    pages: {
      type: "array",
      items: {
        type: "object",
        properties: { titre: { type: "string" }, corps: { type: "string" } },
        required: ["titre", "corps"],
        additionalProperties: false,
      },
    },
  },
  required: ["texte", "titre_carrousel", "pages"],
  additionalProperties: false,
};

/**
 * Rend { texte, carrousel } où carrousel vaut null ou { titre, pages }.
 * Lève RangeError quand la demande ne peut pas être servie (message pour le membre).
 */
export async function rediger(env, { sujet, carrousel }) {
  if (!env.ANTHROPIC_API_KEY) throw new RangeError("La rédaction assistée n'est pas activée sur cette instance.");
  if (typeof sujet !== "string" || !sujet.trim()) throw new RangeError("Donne un sujet.");
  if (sujet.length > SUJET_MAX) throw new RangeError(`Sujet trop long : ${SUJET_MAX} caractères au plus.`);

  const client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });
  const reponse = await client.beta.messages.create({
    model: "claude-opus-5-5",
    max_tokens: 16000,
    // Si le modèle décline la demande, l'API la rejoue sur le modèle de repli
    // recommandé, dans le même appel.
    betas: ["server-side-fallback-2026-07-01"],
    fallbacks: "default",
    output_config: { effort: "medium", format: { type: "json_schema", schema: FORME } },
    system: CONSIGNES,
    messages: [{ role: "user", content: `Sujet : ${sujet.trim()}\nCarrousel demandé : ${carrousel ? "oui" : "non"}` }],
  });

  if (reponse.stop_reason === "refusal") throw new RangeError("Ce sujet a été refusé par le modèle. Reformule-le.");
  if (reponse.stop_reason === "max_tokens") throw new RangeError("Le brouillon a été coupé avant la fin. Réessaie avec un sujet plus précis.");
  const bloc = reponse.content.find((b) => b.type === "text");
  const brouillon = JSON.parse(bloc?.text ?? "null");
  if (!brouillon?.texte) throw new RangeError("Le modèle n'a rien rendu d'exploitable. Réessaie.");

  // Le brouillon est relu par le membre, mais on ne lui tend pas un texte que
  // LinkedIn refuserait : on coupe à la limite plutôt que de laisser échouer.
  const pages = carrousel ? brouillon.pages.slice(0, PAGES_MAX) : [];
  return {
    texte: brouillon.texte.slice(0, MAX_COMMENTARY),
    carrousel: pages.length >= 2 ? { titre: brouillon.titre_carrousel || pages[0].titre, pages } : null,
  };
}
