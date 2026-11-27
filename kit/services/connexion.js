// Page de connexion de Jarvis : envoie le mot de passe (puis le code à 6 chiffres si la double
// authentification est activée), puis affiche l'interface.
// L'interface remplace la page sur place (document.open) au lieu d'un rechargement : la
// fenêtre garde ainsi l'action de la personne (la saisie du mot de passe), et le navigateur
// autorise l'accueil parlé et la musique sans demander un clic de plus.
(() => {
const f = document.getElementById("f");
const err = document.getElementById("err");
const mdp = document.getElementById("mdp"), code = document.getElementById("code");
const tu = document.body.dataset.tu === "1";
function etapeCode() {
  mdp.hidden = true; mdp.required = false;
  code.hidden = false; code.required = true; code.value = ""; code.focus();
  document.getElementById("consigne").textContent = tu
    ? "Saisis le code à 6 chiffres de ton application d'authentification (ou un code de secours)."
    : "Saisissez le code à 6 chiffres de votre application d'authentification (ou un code de secours).";
}
async function afficherInterface() {
  try { sessionStorage.removeItem("jarvis.accueil"); } catch {}
  try {
    const r = await fetch("/", { cache: "no-store" });
    const html = await r.text();
    if (!r.ok || !html.includes('id="orb"')) throw new Error("page inattendue");
    history.replaceState(null, "", "/");
    document.open();
    document.write(html);
    document.close();
  } catch {
    location.replace("/");
  }
}
f.addEventListener("submit", async (e) => {
  e.preventDefault();
  const bouton = f.querySelector("button");
  bouton.disabled = true;
  err.textContent = "";
  try {
    const r = await fetch("/api/connexion", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mot_de_passe: mdp.value, code: code.hidden ? "" : code.value }),
    });
    const d = await r.clone().json().catch(() => ({}));
    if (r.ok && d.etape === "code") { etapeCode(); bouton.disabled = false; return; }
    if (r.ok && d.etape === "activation") { location.replace("/securite"); return; }
    if (r.ok) {
      mdp.value = "";
      // le préchargeur couvre l'écran, puis l'interface prend le relais avec le même
      document.body.classList.add("entree");
      setTimeout(afficherInterface, 350);
      return;
    }
    err.textContent = d.erreur || "Connexion impossible.";
    if (!code.hidden) code.select();
  } catch {
    err.textContent = "Serveur injoignable.";
  }
  bouton.disabled = false;
});
})();
