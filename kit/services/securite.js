// Activation de la double authentification : mot de passe, QR code à scanner, premier code,
// puis codes de secours montrés une seule fois. Le secret ne passe que par cette page.
(() => {
const $ = (s) => document.getElementById(s);
const tu = document.body.dataset.tu === "1";
const nom = document.body.dataset.nom || "Jarvis";
const V = (vous, toi) => (tu ? toi : vous);
const TEXTES = {
  intro: V(`Après le mot de passe, ${nom} vous demandera un code à 6 chiffres, donné par une application sur votre téléphone. Même avec votre mot de passe, personne ne pourra entrer sans votre téléphone. Saisissez votre mot de passe pour commencer.`,
           `Après le mot de passe, ${nom} te demandera un code à 6 chiffres, donné par une application sur ton téléphone. Même avec ton mot de passe, personne ne pourra entrer sans ton téléphone. Saisis ton mot de passe pour commencer.`),
  appli: V("Ouvrez une application d'authentification (Google Authenticator, 2FAS, Aegis, 1Password, Microsoft Authenticator…).",
           "Ouvre une application d'authentification (Google Authenticator, 2FAS, Aegis, 1Password, Microsoft Authenticator…)."),
  scanner: V("Ajoutez un compte et scannez ce QR code, ou saisissez la clé à la main.", "Ajoute un compte et scanne ce QR code, ou saisis la clé à la main."),
  saisir: V("Saisissez le code à 6 chiffres affiché par l'application.", "Saisis le code à 6 chiffres affiché par l'application."),
  secours: V("Voici 10 codes de secours. Chacun ouvre la porte une seule fois si vous n'avez plus votre téléphone. Ils ne seront plus jamais affichés : gardez-les à l'abri (gestionnaire de mots de passe ou papier).",
             "Voici 10 codes de secours. Chacun ouvre la porte une seule fois si tu n'as plus ton téléphone. Ils ne seront plus jamais affichés : garde-les à l'abri (gestionnaire de mots de passe ou papier)."),
  garde: V("J'ai mis ces codes à l'abri.", "J'ai mis ces codes à l'abri."),
  desactiver: V("Pour changer de téléphone, désactivez puis réactivez. Il faut le mot de passe et un code.",
                "Pour changer de téléphone, désactive puis réactive. Il faut le mot de passe et un code."),
};
for (const el of document.querySelectorAll("[data-t]")) el.textContent = TEXTES[el.dataset.t];
const err = $("err");
const montrer = (id) => {
  for (const e of document.querySelectorAll(".etape")) e.hidden = e.id !== id;
  err.textContent = "";
  document.querySelector(`#${id} input:not([type=checkbox])`)?.focus();
};
async function appel(chemin, corps) {
  const r = await fetch(chemin, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps) });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.erreur || "Erreur, réessayez.");
  return d;
}
function occupe(form, oui) { for (const b of form.querySelectorAll("button")) b.disabled = oui; }

// même entrée que la page de connexion : l'interface remplace la page, le geste est gardé
async function afficherInterface() {
  try {
    const r = await fetch("/", { cache: "no-store" });
    const html = await r.text();
    if (!r.ok || !html.includes('id="orb"')) throw new Error();
    history.replaceState(null, "", "/");
    document.open(); document.write(html); document.close();
  } catch { location.replace("/"); }
}

let codesSecours = [];
$("e-debut").addEventListener("submit", async (e) => {
  e.preventDefault(); occupe(e.target, true); err.textContent = "";
  try {
    const d = await appel("/api/2fa/debut", { mot_de_passe: $("mdp").value });
    $("mdp").value = "";
    $("qr").innerHTML = d.qr;            // SVG fabriqué par le serveur (qr.py)
    $("cle").textContent = d.cle;
    montrer("e-scan");
  } catch (x) { err.textContent = x.message; }
  occupe(e.target, false);
});
$("e-scan").addEventListener("submit", async (e) => {
  e.preventDefault(); occupe(e.target, true); err.textContent = "";
  try {
    const d = await appel("/api/2fa/confirmer", { code: $("code-scan").value });
    $("qr").innerHTML = ""; $("cle").textContent = "";
    codesSecours = d.codes_secours;
    $("codes").replaceChildren(...codesSecours.map((c) => Object.assign(document.createElement("span"), { textContent: c })));
    montrer("e-codes");
  } catch (x) { err.textContent = x.message; $("code-scan").select(); }
  occupe(e.target, false);
});
const texteCodes = () => `${nom} : codes de secours de la double authentification (chacun sert une fois)\n\n${codesSecours.join("\n")}\n`;
$("copier").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(texteCodes()); $("copier").textContent = "Copié"; } catch { err.textContent = "Copie impossible : sélectionnez les codes à la main."; }
});
$("telecharger").addEventListener("click", () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([texteCodes()], { type: "text/plain" }));
  a.download = `${nom.replace(/[^\w-]+/g, "")}-codes-de-secours.txt`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
});
$("garde").addEventListener("change", (e) => { $("continuer").disabled = !e.target.checked; });
$("continuer").addEventListener("click", () => { codesSecours = []; afficherInterface(); });
$("e-active").addEventListener("submit", async (e) => {
  e.preventDefault(); occupe(e.target, true); err.textContent = "";
  try {
    const d = await appel("/api/2fa/desactiver", { mot_de_passe: $("mdp-off").value, code: $("code-off").value });
    $("mdp-off").value = ""; $("code-off").value = "";
    await demarrer(d.activation ? null : "desactivee");
  } catch (x) { err.textContent = x.message; }
  occupe(e.target, false);
});

async function demarrer(apres) {
  let etat = {};
  try { etat = await (await fetch("/api/2fa", { cache: "no-store" })).json(); } catch {}
  if (etat.actif) {
    const n = etat.codes_secours_restants ?? 0;
    $("restants").textContent = `${n} code${n > 1 ? "s" : ""} de secours restant${n > 1 ? "s" : ""}.` +
      (n <= 3 ? V(" Pensez à désactiver puis réactiver pour en obtenir de nouveaux.", " Pense à désactiver puis réactiver pour en obtenir de nouveaux.") : "");
    return montrer("e-active");
  }
  $("plus-tard").hidden = etat.mode === "maintenant";       // obligatoire : pas de « plus tard »
  montrer("e-debut");
  if (apres === "desactivee") err.textContent = "Double authentification désactivée.";
}
demarrer();
})();
