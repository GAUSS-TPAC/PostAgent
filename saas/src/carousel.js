/**
 * Générateur de carrousel : une liste de pages -> un PDF, sans dépendance.
 *
 * Sur LinkedIn, un carrousel « organique » est un document PDF. Le PDF est
 * écrit à la main (pages vectorielles, polices standard Helvetica), ce qui
 * tourne à l'identique dans un Worker, dans Node et dans un navigateur.
 *
 * Limite assumée : Helvetica standard ne couvre que le jeu cp1252. Accents,
 * guillemets et tirets français passent ; les emoji deviennent « ? ».
 */

import { BOLD, REGULAR } from "./helvetica.js";

const L = 1080; // page 4:5, le format qui occupe le plus de place dans le fil
const H = 1350;
const MARGE = 96;
export const PAGES_MIN = 2;
export const PAGES_MAX = 10;

const THEMES = {
  nuit: { fond: [0.06, 0.09, 0.16], texte: [0.96, 0.97, 0.98], accent: [0.22, 0.74, 0.97], doux: [0.58, 0.64, 0.72] },
  clair: { fond: [0.98, 0.98, 0.97], texte: [0.09, 0.11, 0.15], accent: [0.05, 0.4, 0.76], doux: [0.42, 0.45, 0.5] },
};

// Caractères cp1252 situés hors Latin-1 (guillemets courbes, tirets, œ, €…).
const CP1252_HAUT = "€\u0081‚ƒ„…†‡ˆ‰Š‹Œ\u008dŽ\u008f\u0090‘’“”•–—˜™š›œ\u009džŸ";

/** Texte -> octets cp1252. Ce qui n'existe pas dans la police devient « ? ». */
function versCp1252(texte) {
  return [...texte].map((c) => {
    const code = c.codePointAt(0);
    if (code < 128 || (code >= 160 && code <= 255)) return code;
    const i = CP1252_HAUT.indexOf(c);
    return i >= 0 ? 128 + i : 63;
  });
}

function largeur(octets, taille, gras) {
  const table = gras ? BOLD : REGULAR;
  return (octets.reduce((somme, o) => somme + (o >= 32 ? table[o - 32] || 556 : 0), 0) * taille) / 1000;
}

/** Coupe un texte en lignes qui tiennent dans `max` points. */
function couper(texte, taille, gras, max) {
  const lignes = [];
  for (const paragraphe of texte.split("\n")) {
    let ligne = "";
    for (const mot of paragraphe.split(/\s+/).filter(Boolean)) {
      const essai = ligne ? `${ligne} ${mot}` : mot;
      if (ligne && largeur(versCp1252(essai), taille, gras) > max) {
        lignes.push(ligne);
        ligne = mot;
      } else ligne = essai;
    }
    lignes.push(ligne);
  }
  return lignes;
}

/** Chaîne PDF : tout octet non ASCII part en échappement octal. */
function chainePdf(texte) {
  return `(${versCp1252(texte).map((o) =>
    o === 40 || o === 41 || o === 92 ? `\\${String.fromCharCode(o)}` : o < 32 || o > 126 ? `\\${o.toString(8).padStart(3, "0")}` : String.fromCharCode(o),
  ).join("")})`;
}

const rvb = (c) => c.map((v) => v.toFixed(3)).join(" ");
const RETRAIT = 40; // décalage du texte d'une puce, y compris sur ses lignes de suite

/** Coupe un corps de page paragraphe par paragraphe. Une ligne qui commence
 *  par « - » est une puce : son texte est en retrait sur toutes ses lignes. */
function couperCorps(corps, taille, max) {
  return corps.split("\n").flatMap((paragraphe) => {
    const puce = /^\s*[-•]\s+/.test(paragraphe);
    const texte = paragraphe.replace(/^\s*[-•]\s+/, "");
    return couper(texte, taille, false, max - (puce ? RETRAIT : 0)).map((t, i) => ({ t, retrait: puce ? RETRAIT : 0, puce: puce && i === 0 }));
  });
}

/** Réduit la taille jusqu'à ce que le bloc tienne dans `lignesMax`. */
function ajuster(decoupe, taille, lignesMax, plancher) {
  let lignes = decoupe(taille);
  while (lignes.length > lignesMax && taille > plancher) {
    taille -= 4;
    lignes = decoupe(taille);
  }
  return { lignes: lignes.slice(0, lignesMax), taille };
}

function page({ titre, corps }, numero, total, auteur, theme, couverture) {
  const t = THEMES[theme] ?? THEMES.nuit;
  const utile = L - 2 * MARGE;
  const ops = [`${rvb(t.fond)} rg 0 0 ${L} ${H} re f`, `${rvb(t.accent)} rg ${MARGE} ${H - MARGE - 12} 120 12 re f`];
  const ecrire = (texte, x, y, taille, gras, couleur) =>
    ops.push(`BT /${gras ? "F2" : "F1"} ${taille} Tf ${rvb(couleur)} rg ${x.toFixed(1)} ${y.toFixed(1)} Td ${chainePdf(texte)} Tj ET`);

  const T = ajuster((taille) => couper(titre ?? "", taille, true, utile), couverture ? 104 : 76, couverture ? 6 : 4, 48);
  // La couverture est centrée verticalement ; les autres pages partent du haut.
  let y = couverture ? H / 2 + (T.lignes.length * T.taille * 1.12) / 2 : H - MARGE - 110;
  for (const ligne of T.lignes) {
    ecrire(ligne, MARGE, y - T.taille, T.taille, true, t.texte);
    y -= T.taille * 1.12;
  }

  if (corps) {
    y -= couverture ? 28 : 44;
    const place = Math.max(1, Math.floor((y - MARGE - 90) / (48 * 1.4)));
    const C = ajuster((taille) => couperCorps(corps, taille, utile), 48, place, 30);
    for (const ligne of C.lignes) {
      if (ligne.puce) ops.push(`${rvb(t.accent)} rg ${MARGE} ${(y - C.taille * 0.72).toFixed(1)} 14 14 re f`);
      ecrire(ligne.t, MARGE + ligne.retrait, y - C.taille, C.taille, false, couverture ? t.doux : t.texte);
      y -= C.taille * 1.4;
    }
  }

  if (auteur) ecrire(auteur, MARGE, MARGE, 28, false, t.doux);
  const compteur = `${numero} / ${total}`;
  ecrire(compteur, L - MARGE - largeur(versCp1252(compteur), 28, true), MARGE, 28, true, t.accent);
  return ops.join("\n");
}

/** Contrôle la forme d'un carrousel. Lève RangeError avec un message lisible. */
export function validerCarrousel(spec) {
  const pages = spec?.pages;
  if (!Array.isArray(pages) || pages.length < PAGES_MIN || pages.length > PAGES_MAX) {
    throw new RangeError(`Un carrousel compte ${PAGES_MIN} à ${PAGES_MAX} pages`);
  }
  pages.forEach((p, i) => {
    if (!p?.titre?.trim()) throw new RangeError(`Page ${i + 1} : titre manquant`);
  });
  return spec;
}

/**
 * Rend le carrousel en PDF. `spec` : { auteur?, theme?, pages: [{ titre, corps? }] }.
 * La première page sert de couverture. Retourne un Uint8Array.
 */
export function rendreCarrousel(spec) {
  const { pages, auteur = "", theme = "nuit" } = validerCarrousel(spec);
  const n = pages.length;
  // Objets : 1 catalogue, 2 arbre des pages, 3 et 4 polices, puis (page, contenu) par page.
  const objets = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    `<< /Type /Pages /Count ${n} /Kids [${pages.map((_, i) => `${5 + 2 * i} 0 R`).join(" ")}] >>`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
  ];
  pages.forEach((p, i) => {
    const flux = page(p, i + 1, n, auteur, theme, i === 0);
    objets.push(
      `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${L} ${H}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ${6 + 2 * i} 0 R >>`,
      `<< /Length ${flux.length} >>\nstream\n${flux}\nendstream`,
    );
  });

  // Le fichier est du pur ASCII (les accents sont en octal) : une position
  // dans la chaîne est donc une position en octets, ce qu'exige la table xref.
  let pdf = "%PDF-1.4\n";
  const positions = objets.map((corps, i) => {
    const position = pdf.length;
    pdf += `${i + 1} 0 obj\n${corps}\nendobj\n`;
    return position;
  });
  const xref = pdf.length;
  pdf += `xref\n0 ${objets.length + 1}\n0000000000 65535 f \n`;
  pdf += positions.map((p) => `${String(p).padStart(10, "0")} 00000 n \n`).join("");
  pdf += `trailer\n<< /Size ${objets.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Uint8Array.from(pdf, (c) => c.charCodeAt(0));
}
