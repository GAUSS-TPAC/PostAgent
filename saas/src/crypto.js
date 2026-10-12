/**
 * Chiffrement des jetons LinkedIn au repos (API Terms of Use §7.1).
 *
 * AES-GCM 256. La clé est un secret du Worker (TOKEN_KEY, 32 octets en
 * base64) : elle n'est jamais dans la base, donc une fuite de la base seule
 * ne livre aucun jeton. Chaque chiffrement tire un vecteur neuf, stocké en
 * tête du résultat.
 */

const versOctets = (b64) => Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
const versBase64 = (octets) => btoa(String.fromCharCode(...octets));

async function cle(cleB64) {
  let brute = new Uint8Array();
  try {
    brute = versOctets(cleB64 ?? "");
  } catch {
    // base64 illisible : même message que pour une clé de mauvaise longueur
  }
  if (brute.byteLength !== 32) throw new Error("TOKEN_KEY absent ou invalide : 32 octets en base64 attendus");
  return crypto.subtle.importKey("raw", brute, "AES-GCM", false, ["encrypt", "decrypt"]);
}

export async function chiffrer(cleB64, clair) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const chiffre = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await cle(cleB64), new TextEncoder().encode(clair));
  const tout = new Uint8Array(12 + chiffre.byteLength);
  tout.set(iv);
  tout.set(new Uint8Array(chiffre), 12);
  return versBase64(tout);
}

/** Lève une erreur si la clé est fausse ou si le contenu a été altéré. */
export async function dechiffrer(cleB64, chiffreB64) {
  const tout = versOctets(chiffreB64);
  const clair = await crypto.subtle.decrypt({ name: "AES-GCM", iv: tout.slice(0, 12) }, await cle(cleB64), tout.slice(12));
  return new TextDecoder().decode(clair);
}

/** Empreinte SHA-256 en hexadécimal : la base ne garde que l'empreinte des
 *  identifiants de session, jamais la valeur du cookie. */
export async function empreinte(texte) {
  const h = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(texte));
  return [...new Uint8Array(h)].map((o) => o.toString(16).padStart(2, "0")).join("");
}

/** Identifiant aléatoire imprévisible (sessions, états OAuth, clés de post). */
export function aleatoire(octets = 24) {
  return [...crypto.getRandomValues(new Uint8Array(octets))].map((o) => o.toString(16).padStart(2, "0")).join("");
}
