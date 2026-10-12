// Interface PostAgent. Aucune bibliothèque : le DOM et fetch suffisent.
// Tout texte venu du serveur passe par textContent, jamais par innerHTML.

const $ = (id) => document.getElementById(id);
const el = (balise, texte, classe) => {
  const e = document.createElement(balise);
  if (texte != null) e.textContent = texte;
  if (classe) e.className = classe;
  return e;
};

async function appel(chemin, methode = "GET", corps) {
  const reponse = await fetch(chemin, {
    method: methode,
    headers: methode === "GET" ? {} : { "Content-Type": "application/json", "X-PostAgent": "1" },
    body: corps === undefined ? undefined : JSON.stringify(corps),
  });
  if (reponse.status === 401) return null;
  if (!reponse.ok) throw new Error((await reponse.json().catch(() => ({}))).erreur || `Erreur ${reponse.status}`);
  return reponse;
}

function dire(texte) {
  $("message").textContent = texte;
  $("message").hidden = !texte;
  if (texte) window.scrollTo({ top: 0, behavior: "smooth" });
}

const quand = (iso) => new Date(iso).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });
const VISIBILITE = { PUBLIC: "Tout le monde", CONNECTIONS: "Mes relations" };
const MEDIA = { image: "Image", document: "PDF", carousel: "Carrousel" };
const ETAT = { failed: "Échec", stale: "Heure dépassée", publishing: "Resté en cours" };

// ---- carrousel ----

function ajouterPage(titre = "", corps = "") {
  const li = el("li");
  const t = el("input");
  t.placeholder = "Titre de la page";
  t.value = titre;
  t.className = "page-titre";
  const c = el("textarea");
  c.rows = 3;
  c.placeholder = "Texte. Une ligne qui commence par « - » devient une puce.";
  c.value = corps;
  c.className = "page-corps";
  const retirer = el("button", "Retirer cette page");
  retirer.type = "button";
  retirer.onclick = () => li.remove();
  li.append(t, c, retirer);
  $("pages").append(li);
}

const lireCarrousel = () => ({
  auteur: $("auteur").value.trim(),
  theme: $("theme").value,
  pages: [...$("pages").children].map((li) => ({
    titre: li.querySelector(".page-titre").value.trim(),
    corps: li.querySelector(".page-corps").value.trim(),
  })),
});

async function apercu() {
  try {
    const reponse = await appel("/api/carousel", "POST", { spec: lireCarrousel() });
    const cadre = $("cadre-apercu");
    cadre.src = URL.createObjectURL(await reponse.blob());
    cadre.hidden = false;
  } catch (erreur) {
    dire(erreur.message);
  }
}

// ---- composer ----

const mediaChoisi = () => document.querySelector("input[name=media]:checked").value;

function afficherMedia() {
  const genre = mediaChoisi();
  $("bloc-fichier").hidden = genre !== "image" && genre !== "document";
  $("bloc-titre").hidden = genre !== "document";
  $("fichier").accept = genre === "image" ? "image/jpeg,image/png,image/gif" : "application/pdf";
  $("bloc-carrousel").hidden = genre !== "carousel";
  if (genre === "carousel" && !$("pages").children.length) for (let i = 0; i < 4; i += 1) ajouterPage();
}

const enBase64 = (fichier) => new Promise((ok, ko) => {
  const lecteur = new FileReader();
  lecteur.onload = () => ok(lecteur.result.split(",")[1]);
  lecteur.onerror = () => ko(new Error("Fichier illisible"));
  lecteur.readAsDataURL(fichier);
});

async function lireMedia() {
  const genre = mediaChoisi();
  if (!genre) return null;
  if (genre === "carousel") return { kind: "carousel", spec: lireCarrousel() };
  const fichier = $("fichier").files[0];
  if (!fichier) throw new Error("Choisis un fichier, ou repasse la pièce jointe sur « Aucune ».");
  return { kind: genre, title: $("titre-doc").value, data: await enBase64(fichier) };
}

async function programmer(evenement) {
  evenement.preventDefault();
  const formulaire = new FormData(evenement.target);
  try {
    const maintenant = formulaire.get("quand") === "now";
    if (!maintenant && !$("date").value) throw new Error("Choisis une date, ou « Dès que possible ».");
    const reponse = await appel("/api/posts", "POST", {
      text: $("texte").value,
      visibility: formulaire.get("visibility"),
      // datetime-local est en heure locale : toISOString() y met le fuseau.
      scheduled_at: maintenant ? "now" : new Date($("date").value).toISOString(),
      media: await lireMedia(),
    });
    if (!reponse) return location.reload();
    evenement.target.reset();
    $("pages").replaceChildren();
    $("cadre-apercu").hidden = true;
    afficherMedia();
    compter();
    dire("Post programmé.");
    await charger();
  } catch (erreur) {
    dire(erreur.message);
  }
}

// Même mesure que le serveur : unités UTF-16 du texte échappé.
const compter = () => { $("compteur").textContent = $("texte").value.replace(/([\\|{}@\[\]()<>*_~])/g, "\\$1").length; };

// ---- rédaction assistée ----

async function rediger() {
  const bouton = $("rediger");
  bouton.disabled = true;
  bouton.textContent = "Rédaction en cours…";
  try {
    const reponse = await appel("/api/generate", "POST", { sujet: $("sujet").value, carrousel: $("avec-carrousel").checked });
    if (!reponse) return location.reload();
    const brouillon = await reponse.json();
    $("texte").value = brouillon.texte;
    compter();
    if (brouillon.carrousel) {
      document.querySelector("input[name=media][value=carousel]").checked = true;
      $("pages").replaceChildren();
      brouillon.carrousel.pages.forEach((p) => ajouterPage(p.titre, p.corps));
      afficherMedia();
      await apercu();
    }
    dire("Brouillon prêt. Relis-le, choisis la visibilité et la date, puis programme.");
  } catch (erreur) {
    dire(erreur.message);
  } finally {
    bouton.disabled = false;
    bouton.textContent = "Rédiger un brouillon";
  }
}

// ---- listes ----

async function agir(chemin, corps, confirmation) {
  if (confirmation && !confirm(confirmation)) return;
  try {
    await appel(chemin, "POST", corps ?? {});
    await charger();
  } catch (erreur) {
    dire(erreur.message);
  }
}

async function voirStats(post, zone) {
  try {
    const s = await (await appel(`/api/posts/${post.id}/stats`)).json();
    zone.textContent = s.disponible
      ? `${s.metriques.IMPRESSION} vues · ${s.metriques.REACTION} réactions · ${s.metriques.COMMENT} commentaires · ${s.metriques.RESHARE} partages`
      : `Statistiques indisponibles : ${s.raison}`;
  } catch (erreur) {
    zone.textContent = erreur.message;
  }
}

function ligne(post) {
  const li = el("li");
  const tete = el("div");
  if (ETAT[post.status]) tete.append(el("span", ETAT[post.status], "etiquette"));
  if (post.media_kind) tete.append(el("span", MEDIA[post.media_kind], "etiquette"));
  tete.append(el("span", `${quand(post.published_at ?? post.scheduled_at)} · ${VISIBILITE[post.visibility]}`, "doux"));
  li.append(tete, el("p", post.text.length > 280 ? `${post.text.slice(0, 280)}…` : post.text, "extrait"));
  if (post.error) li.append(el("p", post.error, "erreur"));

  const actions = el("div", null, "actions");
  const bouton = (texte, action) => { const b = el("button", texte); b.onclick = action; actions.append(b); };
  if (post.status === "scheduled") bouton("Annuler", () => agir(`/api/posts/${post.id}/cancel`, null, "Annuler ce post ?"));
  if (ETAT[post.status]) {
    const date = el("input");
    date.type = "datetime-local";
    actions.append(date);
    bouton("Reprogrammer", () => (date.value
      ? agir(`/api/posts/${post.id}/resolve`, { scheduled_at: new Date(date.value).toISOString() }, "As-tu vérifié sur ton profil que ce post n'est pas déjà en ligne ?")
      : dire("Choisis une nouvelle date pour reprogrammer.")));
    bouton("Abandonner", () => agir(`/api/posts/${post.id}/resolve`, {}, "Abandonner ce post ?"));
  }
  if (post.status === "published") {
    const zone = el("span", null, "doux");
    bouton("Statistiques", () => voirStats(post, zone));
    actions.append(zone);
  }
  li.append(actions);
  return li;
}

function remplir(id, posts, vide) {
  $(id).replaceChildren(...(posts.length ? posts.map(ligne) : [el("li", vide, "doux")]));
}

async function charger() {
  const reponse = await appel("/api/posts");
  if (!reponse) return;
  const { posts } = await reponse.json();
  const a = (etats) => posts.filter((p) => etats.includes(p.status));
  const enPanne = a(["failed", "stale", "publishing"]);
  $("zone-trancher").hidden = !enPanne.length;
  remplir("liste-trancher", enPanne, "");
  remplir("liste-programmes", a(["scheduled"]).reverse(), "Aucun post programmé.");
  remplir("liste-publies", a(["published"]), "Rien de publié pour l'instant.");
}

// ---- démarrage ----

async function demarrer() {
  const retour = new URLSearchParams(location.search).get("erreur");
  if (retour) dire(retour);
  const reponse = await appel("/api/me");
  if (!reponse) { $("connexion").hidden = false; return; }
  const moi = await reponse.json();
  $("app").hidden = false;
  $("sortie").hidden = false;
  $("qui").textContent = moi.name ?? "";
  $("acces").textContent = moi.jours_restants < 0
    ? "Ton accès LinkedIn a expiré : renouvelle-le pour que tes posts partent."
    : `Accès LinkedIn valable encore ${moi.jours_restants} jour(s).`;
  if (moi.jours_restants < 7) dire("Ton accès LinkedIn expire bientôt : renouvelle-le dans « Mon compte », en bas de page.");
  if (!moi.publication_ouverte) dire("Mode démonstration : la publication est verrouillée, rien ne partira vers LinkedIn.");

  document.querySelectorAll("input[name=media]").forEach((r) => r.addEventListener("change", afficherMedia));
  $("ajouter-page").onclick = () => ($("pages").children.length < 10 ? ajouterPage() : dire("10 pages au maximum."));
  $("apercu").onclick = apercu;
  $("rediger").onclick = rediger;
  $("texte").addEventListener("input", compter);
  $("composer").addEventListener("submit", programmer);
  $("supprimer-compte").onclick = async () => {
    if (!confirm("Supprimer ton compte, ton accès LinkedIn et tous tes posts programmés ? Les posts déjà publiés restent sur LinkedIn.")) return;
    await appel("/api/account", "DELETE");
    location.href = "/";
  };
  afficherMedia();
  await charger();
}

demarrer().catch((erreur) => dire(erreur.message));
