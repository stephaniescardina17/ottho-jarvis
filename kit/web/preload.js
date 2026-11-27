// Progression du préchargeur, de 0 à 100 %. Script classique (pas un module) chargé tout de
// suite : il mesure le vrai téléchargement de three.js (la plus grosse ressource), puis
// app.js signale ses étapes. La barre n'atteint le bout que lorsque tout est prêt.
(() => {
  const URL_THREE = "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js";
    const POIDS = { three: 55, polices: 10, config: 10, orbe: 10, donnees: 15 };
  const fait = {};
  let fracThree = 0, affiche = 0, fin = null;
  const barre = document.getElementById("pl-barre-i");
  const texte = document.getElementById("pl-pct");

  // Sons de la barre (règle « Sons du motion design », web/sons/LICENCES.md) : un tic toutes les
  // 95 ms pendant le chargement, un son à 100 %. Coupés si « Sons de l'interface » est décoché
  // (choix mémorisé par app.js). Le contexte audio est ensuite repris par app.js.
  const sons = (() => {
    try { if (localStorage.getItem("jarvis-sons") === "0") return null; } catch {}
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    let ctx;
    try { ctx = window.__sonCtx = new AC(); } catch { return null; }
    ctx.resume?.().catch(() => {});
    const charger = (u) => fetch(u).then((r) => r.arrayBuffer()).then((b) => ctx.decodeAudioData(b)).catch(() => null);
    const tampons = { tic: charger("sons/tic.mp3?v=1"), complet: charger("sons/complet.mp3?v=1") };
    return async (nom, hauteur = 1) => {
      const t = await tampons[nom];
      if (!t || ctx.state !== "running") return;      // page sans geste de l'utilisateur : silence
      const s = ctx.createBufferSource();
      s.buffer = t; s.playbackRate.value = hauteur; s.connect(ctx.destination); s.start();
    };
  })();
  let dernierTic = 0;

  const cible = () => {
    let p = 0;
    for (const k in POIDS) p += POIDS[k] * (k === "three" ? fracThree : fait[k] ? 1 : 0);
    return Math.min(100, p);
  };

  window.__chargement = {
    etape(nom) { fait[nom] = true; if (nom === "three") fracThree = 1; },
    quandFini(cb) { fin = cb; },
  };

  // Le même fichier sera repris du cache par l'import du module : pas de double téléchargement.
  fetch(URL_THREE).then(async (r) => {
    const total = Number(r.headers.get("content-length")) || 1300000;
    const lecteur = r.body.getReader();
    let recu = 0;
    for (;;) {
      const { done, value } = await lecteur.read();
      if (done) break;
      recu += value.length;
      fracThree = Math.min(0.98, recu / total);
    }
    fracThree = 1;
  }).catch(() => { fracThree = 1; });
  document.fonts?.ready.then(() => { fait.polices = true; });

  // progression lissée dans le temps (et non par image) : même vitesse sur un écran lent ou rapide
  let avant = performance.now();
  function boucle() {
    const maintenant = performance.now();
    const dt = Math.min(0.5, (maintenant - avant) / 1000);
    avant = maintenant;
    const c = cible();
    affiche += (c - affiche) * (1 - Math.exp(-dt * 9));
    if (c - affiche < 0.6) affiche = c;
    const v = Math.floor(affiche);
    if (barre) barre.style.transform = `scaleX(${v / 100})`;
    if (texte) texte.textContent = `${v} %`;
    if (sons && v < 100 && maintenant - dernierTic >= 95) { dernierTic = maintenant; sons("tic", 0.97 + Math.random() * 0.06); }
    if (v >= 100 && fin) {
      const f = fin;
      fin = null;
      sons?.("complet");
      setTimeout(f, 220);      // laisser voir 100 % un instant
      return;
    }
    requestAnimationFrame(boucle);
  }
  requestAnimationFrame(boucle);

  // si l'onglet est ralenti (arrière-plan), on termine sans attendre l'image suivante
  setInterval(() => {
    if (cible() >= 100 && fin) { affiche = 100; const f = fin; fin = null; f(); }
  }, 700);

  // filet de sécurité : jamais bloqué plus de 15 s
  setTimeout(() => { for (const k in POIDS) fait[k] = true; fracThree = 1; }, 15000);
})();
