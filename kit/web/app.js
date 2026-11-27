import { createOrb } from "./orb.js?v=26";

const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};

/* ================= Configuration ================= */
// jarvis.config.json est la source unique (le futur plugin d'installation l'écrira).
// Les réglages changés à la volée s'y superposent. Maquette : dans le navigateur ;
// version en ligne : PUT /api/reglages.
const DEFAULT_CONFIG = {
  assistant: { nom: "Jarvis" },
  utilisateur: { prenom: "", adresse: "civilite", civilite: "Monsieur", tutoiement: false },
  ton: "equilibre", accent: "cyan", voix: false, genre_voix: "homme", accueil: true, sons: true,
  ville: { nom: "Nice", lat: 43.7031, lon: 7.2661, fuseau: "Europe/Paris" },
  brief: { heure: "07:30", rubriques: [] },
  garde_fous: [],
  musique: { playlist: "musique/playlist.json" },
};
let config = DEFAULT_CONFIG;
// En ligne : /config.json (config + réglages enregistrés sur le serveur) ; en maquette : le fichier.
let LIVE = false;
try {
  let r = await fetch("config.json", { cache: "no-store" });
  if (r.ok && (r.headers.get("content-type") || "").includes("json")) LIVE = true;
  else r = await fetch("jarvis.config.json", { cache: "no-store" });
  if (r.ok) config = { ...DEFAULT_CONFIG, ...(await r.json()) };
} catch {}
const overrides = LIVE ? {} : store.get("jarvis.reglages", {});
config = deepMerge(config, overrides);
// le préchargeur (preload.js) joue ses sons avant que la config arrive : il lit ce choix mémorisé
const memoriserSons = () => { try { localStorage.setItem("jarvis-sons", config.sons === false ? "0" : "1"); } catch {} };
memoriserSons();
window.__chargement?.etape("three");    // les modules (dont three.js) sont chargés
window.__chargement?.etape("config");

function deepMerge(a, b) {
  const out = { ...a };
  for (const [k, v] of Object.entries(b || {})) {
    out[k] = v && typeof v === "object" && !Array.isArray(v) ? deepMerge(a[k] || {}, v) : v;
  }
  return out;
}
function saveSetting(path, value) {
  const keys = path.split(".");
  let o = overrides, c = config;
  keys.slice(0, -1).forEach((k) => { o = o[k] ??= {}; c = c[k] ??= {}; });
  o[keys.at(-1)] = value;
  c[keys.at(-1)] = value;
  if (path === "sons") memoriserSons();
  if (!LIVE) { store.set("jarvis.reglages", overrides); return; }
  // en ligne : enregistré sur le serveur, regroupé pour ne pas envoyer chaque frappe
  clearTimeout(saveSetting.t);
  saveSetting.t = setTimeout(() => {
    const { utilisateur, ton, accent, voix, genre_voix, accueil, sons, ville, musique } = config;
    fetch("api/reglages", { method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ utilisateur, ton, accent, voix, genre_voix, accueil, sons, ville, musique }) }).catch(() => {});
  }, 600);
}

/* Formes d'adresse */
const ACCENTS = { cyan: "#5fe1ff", rouge: "#e63c2e", vert: "#4ff0b0", ambre: "#ffb547", violet: "#a993ff" };   // ancien « bleu » : repasse au cyan
const tu = () => !!config.utilisateur.tutoiement;
const V = (vous, toi) => (tu() ? toi : vous);
function nomAdresse() {
  const u = config.utilisateur;
  return u.adresse === "prenom" && u.prenom ? u.prenom : u.civilite || "Monsieur";
}

let ecritureSalutation = false;   // vrai pendant que « Bonjour, Monsieur. » s'écrit

/* ================= Orbe et états ================= */
const orb = createOrb($("#orb"));
const STATE_LABEL = { idle: "En veille", listening: "Écoute", thinking: "Réflexion", speaking: "Réponse" };
let musiquePrete = false;     // le lecteur de musique est déclaré plus bas
function setState(s) {
  orb.setState(s);
  // pendant tout l'échange (écoute, réflexion, réponse), la musique s'efface derrière la voix
  if (musiquePrete) attenuerMusique(s !== "idle");
  document.body.dataset.state = s;
  const el = $("#core-state");
  el.querySelector("span").textContent = STATE_LABEL[s];
  el.querySelector(".dot").className = "dot " + (s === "idle" ? "ok" : "busy");
}
setState("idle");

const NS = "http://www.w3.org/2000/svg";
const svgEl = (nom, attrs = {}, parent) => {
  const e = document.createElementNS(NS, nom);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
};

// Cercle gradué extérieur : 120 graduations, une plus longue tous les 30°.
(() => {
  const g = $(".hud-ticks");
  for (let i = 0; i < 120; i++) {
    const major = i % 10 === 0;
    const a = (i / 120) * Math.PI * 2;
    const r1 = 176, r2 = major ? 186 : 180;
    svgEl("line", { x1: 200 + Math.cos(a) * r1, y1: 200 + Math.sin(a) * r1,
      x2: 200 + Math.cos(a) * r2, y2: 200 + Math.sin(a) * r2, class: major ? "major" : "" }, g);
  }
  // couronne de 72 segments pour le chargement de la sphère
  const c = $(".hud-charge");
  for (let i = 0; i < 72; i++) {
    const a = (i / 72) * Math.PI * 2 - Math.PI / 2;
    svgEl("line", { x1: 200 + Math.cos(a) * 146, y1: 200 + Math.sin(a) * 146,
      x2: 200 + Math.cos(a) * 153, y2: 200 + Math.sin(a) * 153 }, c);
  }
})();

// Remplit la couronne segment par segment (dans le sens des aiguilles d'une montre), puis l'apaise.
function chargerCouronne(duree = 1100) {
  const segs = [...document.querySelectorAll(".hud-charge line")];
  const t0 = performance.now();
  return new Promise((fin) => {
    const pas = () => {
      const n = Math.min(segs.length, Math.round(((performance.now() - t0) / duree) * segs.length));
      for (let i = 0; i < n; i++) segs[i].classList.add("on");
      if (n < segs.length) requestAnimationFrame(pas);
      else setTimeout(fin, 250);
    };
    requestAnimationFrame(pas);
  });
}

/* ================= Indicateurs d'état du VPS ================= */
// seuil : à partir de cette valeur, l'indicateur passe en orange avec un triangle d'alerte
const INDICS = [
  { id: "cpu", libelle: "Processeur", unite: "%", coin: [-1, -1], seuil: 90, alerte: "processeur très chargé" },
  { id: "memoire", libelle: "Mémoire", unite: "%", coin: [1, -1], seuil: 90, alerte: "mémoire presque pleine" },
  { id: "disque", libelle: "Disque", unite: "%", coin: [-1, 1], seuil: 85, alerte: "disque presque plein" },
  { id: "hermes_ms", libelle: "Réponse Hermes", unite: "ms", coin: [1, 1], max: 500, seuil: 1500, alerte: "Hermes répond lentement" },
];
const info = $("#hud-info");
const JAUGE = 46;   // longueur des jauges, en pixels
function dessinerIndicateurs() {
  const core = $("#core");
  const w = core.clientWidth, h = core.clientHeight;
  const hud = parseFloat(getComputedStyle(core).getPropertyValue("--hud")) || 420;
  const r = (hud / 2) * (172 / 200);              // rayon du cercle extérieur, en pixels
  const libre = (w - hud) / 2;                     // place disponible de chaque côté
  info.innerHTML = "";
  for (const m of minuteursChiffres) clearTimeout(m);
  minuteursChiffres.clear();
  info.dataset.place = libre > 95 ? "oui" : "non";
  if (libre <= 95) return;                         // trop étroit (téléphone) : pas d'indicateurs
  const long = Math.min(64, libre - 20);           // traits courts : les infos restent près de la sphère
  const cx = w / 2, cy = h / 2;
  for (const d of INDICS) {
    const [sx, sy] = d.coin;
    const x0 = cx + sx * r * 0.74, y0 = cy + sy * r * 0.68;
    const x1 = x0 + sx * 20, y1 = y0 + sy * 20;
    const x2 = cx + sx * (hud / 2 + long);
    const k = INDICS.indexOf(d);
    const g = svgEl("g", { class: "indic", "data-id": d.id }, info);
    // apparition façon « callout » : le cercle se dessine, son point clignote, le trait part du
    // cercle et file jusqu'à son embout, puis les textes et les traits radar. Chaque indicateur
    // a son propre décalage, très proche des autres.
    g.style.setProperty("--d", `${[0, 0.11, 0.06, 0.17][k]}s`);
    const chemin = `M${x0},${y0} L${x1},${y1} L${x2},${y1}`;
    const p = svgEl("path", { d: chemin, class: "trait" }, g);
    const lg = Math.abs(x2 - x1) + 20 * Math.SQRT2;
    p.style.strokeDasharray = lg;
    p.style.setProperty("--lg", lg);
    const anneau = svgEl("circle", { cx: x0, cy: y0, r: 3.5, class: "anneau" }, g);
    anneau.style.strokeDasharray = 2 * Math.PI * 3.5;
    anneau.style.setProperty("--c", 2 * Math.PI * 3.5);
    svgEl("circle", { cx: x0, cy: y0, r: 1.5, class: "point" }, g);
    svgEl("rect", { x: x2 - 1.5, y: y1 - 1.5, width: 3, height: 3, class: "embout" }, g);
    const ancre = sx < 0 ? "start" : "end";
    const v = svgEl("text", { x: x2, y: y1 - 6, class: "valeur", "text-anchor": ancre }, g);
    v.textContent = "—";
    const l = svgEl("text", { x: x2, y: y1 - 20, class: "libelle", "text-anchor": ancre }, g);
    l.textContent = d.libelle;
    // triangle d'alerte (point d'exclamation), placé à côté de la valeur par majIndicateurs
    const tri = svgEl("g", { class: "alerte-icone", "data-cote": sx < 0 ? "g" : "d" }, g);
    svgEl("title", {}, tri);
    svgEl("path", { d: "M5 0.8 9.6 9.2H0.4Z", class: "tri" }, tri);
    svgEl("path", { d: "M5 3.6V6.1", class: "excl" }, tri);
    svgEl("circle", { cx: 5, cy: 7.6, r: 0.6, class: "excl-point" }, tri);
    // sous la valeur, accrochés côté extérieur : une barre fixe à la valeur sur une piste pâle,
    // un reflet qui la parcourt très lentement, puis une ligne de chiffres qui changent un à un,
    // sur place. Chaque indicateur a son rythme : rien ne bat à l'unisson.
    const jx = sx < 0 ? x2 : x2 - JAUGE;
    const radar = svgEl("g", { class: "radar", "data-cote": sx < 0 ? "g" : "d" }, g);
    svgEl("rect", { x: jx, y: y1 + 5, width: JAUGE, height: 1, class: "piste" }, radar);
    svgEl("rect", { x: jx, y: y1 + 5, width: 0, height: 1, class: "jauge", "data-max": d.max || 100 }, radar);
    const reflet = svgEl("rect", { x: sx < 0 ? jx : x2 - 5, y: y1 + 5, width: 5, height: 1, class: "reflet" }, radar);
    reflet.style.setProperty("--course", `${(JAUGE - 5) * -sx}px`);
    reflet.style.animationDuration = `${[13, 17, 15, 19][k]}s`;
    reflet.style.animationDelay = `${-[2, 9, 5, 13][k]}s`;
    const chiffres = svgEl("text", { x: x2, y: y1 + 14, class: "defile", "text-anchor": ancre }, g);
    for (const c of CHIFFRES) {
      svgEl("tspan", {}, chiffres).textContent = c === " " ? " " : String(Math.floor(Math.random() * 10));
    }
    defiler(chiffres, [2.6, 3.4, 3, 3.9][k]);
  }
  if (info.classList.contains("visible")) afficherIndicateurs(false);
  majIndicateurs(derniersStats);
}
// Chiffres qui défilent sur place : de temps en temps, un chiffre tourne quelques crans
// (60 ms chacun) puis se pose, en s'éclairant un instant. Rythme propre à chaque indicateur,
// légèrement irrégulier. Rien si l'animation réduite est demandée ou si l'onglet est caché.
const CHIFFRES = "0000 00 000";
const minuteursChiffres = new Set();
function defiler(texte, periode) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const places = [...texte.children].filter((t) => t.textContent !== " ");
  const suivant = () => {
    const m = setTimeout(() => {
      minuteursChiffres.delete(m);
      if (!texte.isConnected) return;
      if (!document.hidden) {
        const t = places[Math.floor(Math.random() * places.length)];
        let crans = 3 + Math.floor(Math.random() * 3);
        const tourne = () => {
          t.textContent = String((Number(t.textContent) + 1) % 10);
          if (--crans > 0) setTimeout(tourne, 60);
          else t.animate([{ fillOpacity: 1 }, { fillOpacity: 0.3 }], { duration: 1400, easing: "ease-out" });
        };
        tourne();
      }
      suivant();
    }, periode * 1000 * (0.6 + Math.random() * 0.8));
    minuteursChiffres.add(m);
  };
  suivant();
}
let derniersStats = null;
function afficherIndicateurs(anime = true) {
  info.classList.toggle("instant", !anime);        // redessin (fenêtre redimensionnée) : sans animation
  info.classList.add("visible");
}
function majIndicateurs(s) {
  if (!s) return;
  for (const d of INDICS) {
    const g = info.querySelector(`[data-id="${d.id}"]`);
    if (!g) continue;
    const v = s[d.id];
    const val = g.querySelector(".valeur");
    val.textContent = v == null ? "—" : `${v} ${d.unite}`;
    const alerte = v != null && v >= d.seuil;
    g.classList.toggle("alerte", alerte);
    if (alerte) {
      const tri = g.querySelector(".alerte-icone");
      const x = Number(val.getAttribute("x")), y = Number(val.getAttribute("y"));
      const lg = val.getComputedTextLength();
      tri.setAttribute("transform", `translate(${tri.dataset.cote === "g" ? x + lg + 5 : x - lg - 15}, ${y - 9})`);
      tri.querySelector("title").textContent = `${d.libelle} : ${v} ${d.unite}, ${d.alerte}`;
    }
    const j = g.querySelector(".jauge");
    j.setAttribute("width", v == null ? 0 : Math.max(1, Math.min(1, v / (d.max || 100)) * JAUGE));
  }
}
async function chargerStats() {
  if (!LIVE) {   // maquette : valeurs d'exemple
    derniersStats = { cpu: 12 + Math.round(Math.random() * 10), memoire: 41, disque: 23, hermes_ms: 38 };
  } else {
    try {
      const r = await fetch("api/vps", { cache: "no-store" });
      if (r.ok) derniersStats = await r.json();
    } catch {}
  }
  majIndicateurs(derniersStats);
}
new ResizeObserver(() => dessinerIndicateurs()).observe($("#core"));

/* ================= Apparence et textes selon les réglages ================= */
function applyIdentity() {
  const hex = ACCENTS[config.accent] || ACCENTS.cyan;
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const root = document.documentElement.style;
  root.setProperty("--accent", hex);
  // icône de l'onglet dans la même couleur (servie par le serveur selon l'accent enregistré)
  const icone = document.querySelector('link[rel="icon"]');
  if (icone && LIVE) icone.href = `favicon.svg?c=${encodeURIComponent(config.accent || "cyan")}`;
  root.setProperty("--accent-soft", `rgba(${r}, ${g}, ${b}, 0.12)`);
  root.setProperty("--accent-rgb", `${r}, ${g}, ${b}`);
  root.setProperty("--accent-2", hex);
  // filets et cadran : la teinte de l'accent, éclaircie
  root.setProperty("--line-rgb", [r, g, b].map((x) => Math.round(x + (255 - x) * 0.3)).join(", "));
  $("#set-adresse").closest("fieldset").querySelector("legend").textContent = V("Comment je m’adresse à vous", "Comment je m’adresse à toi");
  orb.setAccent(hex);

  const nom = config.assistant.affiche || config.assistant.nom || "Jarvis";   // affiché : J.A.R.V.I.S.
  $("#brand-name").textContent = nom.toUpperCase();
  document.querySelector("#tab-jarvis [data-name]").textContent = nom;
  document.title = nom;
  $("#prompt").placeholder = `Demandez à ${nom}…`;

  if (!ecritureSalutation) $("#greet-name").textContent = nomAdresse() + ".";
  $("#greet").setAttribute("aria-label", `${$("#greet-word").textContent}, ${nomAdresse()}.`);
  $("#lede").textContent = V(
    "Je suis prêt. Demandez-moi ce que vous voulez, ou laissez-moi un rappel.",
    "Je suis prêt. Demande-moi ce que tu veux, ou laisse-moi un rappel.");
  $("#mem-title").textContent = V("Ce que je sais de vous", "Ce que je sais de toi");
  $("#skills-hint").textContent = V(
    "Après une tâche réussie, dites « retiens comment on a fait ».",
    "Après une tâche réussie, dis « retiens comment on a fait ».");
  $("#b-hour").textContent = config.brief.heure || "07:30";
  $("#guard-list").innerHTML = (config.garde_fous || []).map((g) => `<li>${esc(g)}</li>`).join("");
  renderMemory();
}

/* ================= Heure, date, salutation ================= */
function tick() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  $("#clock-hm").textContent = `${p(d.getHours())}:${p(d.getMinutes())}`;
  $("#clock-s").textContent = p(d.getSeconds());
  const date = new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long" }).format(d);
  $("#date-line").textContent = `${cap(date)} · ${config.ville.nom}`;
  const h = d.getHours();
  if (!ecritureSalutation) $("#greet-word").textContent = h >= 5 && h < 18 ? "Bonjour" : "Bonsoir";
}

/* ================= Météo (Open-Meteo, sans clé) ================= */
const ICONS = {
  sun: '<circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.3 5.3l1.6 1.6M17.1 17.1l1.6 1.6M5.3 18.7l1.6-1.6M17.1 6.9l1.6-1.6"/>',
  moon: '<path d="M19.5 14.8A7.8 7.8 0 0 1 9.2 4.5a7.8 7.8 0 1 0 10.3 10.3Z"/>',
  partly: '<path d="M8.5 6.2a3.6 3.6 0 0 1 5.9 2.3"/><path d="M5 4.2l.9.9M8.5 2.6v1.3M2.8 8.3h1.3"/><path d="M7.5 19.5h9.8a3.7 3.7 0 0 0 .4-7.4 5 5 0 0 0-9.6 1.3 3.1 3.1 0 0 0-.6 6.1Z"/>',
  cloud: '<path d="M7 18.5h10.3a4 4 0 0 0 .5-8 5.4 5.4 0 0 0-10.4 1.4A3.3 3.3 0 0 0 7 18.5Z"/>',
  fog: '<path d="M7 13.5h10.3a4 4 0 0 0 .5-8 5.4 5.4 0 0 0-10.4 1.4A3.3 3.3 0 0 0 7 13.5Z"/><path d="M5 17h14M7 20.5h10"/>',
  rain: '<path d="M7 14.5h10.3a4 4 0 0 0 .5-8 5.4 5.4 0 0 0-10.4 1.4A3.3 3.3 0 0 0 7 14.5Z"/><path d="M9 17.5l-1 2.5M13 17.5l-1 2.5M17 17.5l-1 2.5"/>',
  snow: '<path d="M7 14.5h10.3a4 4 0 0 0 .5-8 5.4 5.4 0 0 0-10.4 1.4A3.3 3.3 0 0 0 7 14.5Z"/><path d="M9 18.5h.01M12 20.5h.01M15 18.5h.01"/>',
  storm: '<path d="M7 14.5h10.3a4 4 0 0 0 .5-8 5.4 5.4 0 0 0-10.4 1.4A3.3 3.3 0 0 0 7 14.5Z"/><path d="M12.5 15.5 10.5 19h3l-2 3"/>',
};
const svgIcon = (k) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${ICONS[k]}</svg>`;
function describe(code, isDay = 1) {
  const T = [
    [[0], "Ciel dégagé", isDay ? "sun" : "moon"],
    [[1], "Plutôt dégagé", isDay ? "sun" : "moon"],
    [[2], "Partiellement nuageux", isDay ? "partly" : "cloud"],
    [[3], "Couvert", "cloud"],
    [[45, 48], "Brouillard", "fog"],
    [[51, 53, 55, 56, 57], "Bruine", "rain"],
    [[61, 63, 65, 66, 67, 80, 81, 82], "Pluie", "rain"],
    [[71, 73, 75, 77, 85, 86], "Neige", "snow"],
    [[95, 96, 99], "Orage", "storm"],
  ];
  const row = T.find(([codes]) => codes.includes(code)) || T[3];
  return { label: row[1], icon: row[2] };
}

let weather = null;
async function loadWeather() {
  const v = config.ville;
  const q = new URLSearchParams({
    latitude: v.lat, longitude: v.lon, timezone: v.fuseau || "auto", forecast_days: 4, wind_speed_unit: "kmh",
    current: "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m,is_day",
    hourly: "temperature_2m,weather_code,is_day",
    daily: "temperature_2m_max,temperature_2m_min,weather_code",
  });
  try {
    const r = await fetch(`https://api.open-meteo.com/v1/forecast?${q}`);
    if (!r.ok) throw new Error(r.status);
    weather = await r.json();
    renderWeather();
    renderBrief();
  } catch {
    $("#w-label").textContent = "Météo indisponible";
  }
}
function renderWeather() {
  const c = weather.current, d = weather.daily;
  const { label, icon } = describe(c.weather_code, c.is_day);
  $("#w-place").textContent = config.ville.nom;
  $("#w-icon").innerHTML = svgIcon(icon);
  $("#w-temp").textContent = Math.round(c.temperature_2m);
  $("#w-label").textContent = label;
  $("#w-feel").textContent = `Ressenti ${Math.round(c.apparent_temperature)}°`;
  $("#w-minmax").textContent = `${Math.round(d.temperature_2m_min[0])}° / ${Math.round(d.temperature_2m_max[0])}°`;
  $("#w-wind").textContent = `${Math.round(c.wind_speed_10m)} km/h`;
  $("#w-hum").textContent = `${c.relative_humidity_2m} %`;

  const h = weather.hourly;
  const now = c.time.slice(0, 13);
  let start = h.time.findIndex((t) => t.slice(0, 13) > now);
  if (start < 0) start = 0;
  const items = [];
  for (let i = start; i < h.time.length && items.length < 6; i += 2) {
    const { icon: ic } = describe(h.weather_code[i], h.is_day[i]);
    items.push(`<li><span>${Number(h.time[i].slice(11, 13))} h</span>${svgIcon(ic)}<b>${Math.round(h.temperature_2m[i])}°</b></li>`);
  }
  $("#w-hours").innerHTML = items.join("");

  const dayFmt = new Intl.DateTimeFormat("fr-FR", { weekday: "long", timeZone: "UTC" });
  $("#w-days").innerHTML = d.time.slice(1, 4).map((t, k) => {
    const i = k + 1;
    const name = i === 1 ? "Demain" : cap(dayFmt.format(new Date(t + "T12:00:00Z")));
    const { icon: ic, label: lb } = describe(d.weather_code[i], 1);
    return `<li><span>${name}</span><span title="${lb}">${svgIcon(ic)}</span><span class="w-range">${Math.round(d.temperature_2m_min[i])}° / <b>${Math.round(d.temperature_2m_max[i])}°</b></span></li>`;
  }).join("");
}

/* ================= Données ================= */
// En ligne, elles viennent d'Hermes par /api/donnees (chargerDonnees) ; en maquette, exemples.
const reminders = [
  { day: "Auj.", time: "18:00", text: "Appeler le garage pour la révision" },
  { day: "Jeu.", time: "09:30", text: "Rendez-vous chez le dentiste" },
];
const todos = [
  { text: "Relire le devis du client avant envoi", done: false },
  { text: "Préparer la présentation de jeudi", done: false },
  { text: "Répondre au comptable", done: true },
];
const memory = {
  known: [
    { vous: "Vous habitez à Lyon.", tu: "Tu habites à Lyon." },
    { vous: "Vous travaillez surtout le matin : les rappels importants avant midi.", tu: "Tu travailles surtout le matin : les rappels importants avant midi." },
    { vous: "Vous préférez des réponses courtes, sans jargon.", tu: "Tu préfères des réponses courtes, sans jargon." },
  ],
  pending: [
    { vous: "Vous voulez la météo de la montagne le vendredi soir.", tu: "Tu veux la météo de la montagne le vendredi soir." },
  ],
};
const skills = [
  { name: "Préparer le brief du matin", uses: 12 },
  { name: "Prendre un rappel", uses: 31 },
  { name: "Résumer un article envoyé", uses: 6 },
];

/* Rappels */
function sortReminders() {
  const week = ["Dim.", "Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam."];
  const today = new Date().getDay();
  const rank = (d) => (d === "Auj." ? 0 : d === "Dem." ? 1 : (week.indexOf(d) - today + 7) % 7 || 7);
  reminders.sort((x, y) => rank(x.day) - rank(y.day) || x.time.localeCompare(y.time));
}
function renderReminders(newIndex = -1) {
  $("#r-count").textContent = String(reminders.length).padStart(2, "0");
  $("#r-list").innerHTML = reminders.length
    ? reminders.map((r, i) => `<li${i === newIndex ? ' class="is-new"' : ""}><span class="r-time">${r.time}<span class="r-day">${r.day}</span></span><span class="r-text">${esc(r.text)}</span></li>`).join("")
    : `<li class="r-empty">Aucun rappel. ${V("Dites", "Dis")} « rappelle-moi… ».</li>`;
}

/* Tâches du jour */
function renderTodos(newIndex = -1) {
  const done = todos.filter((t) => t.done).length;
  $("#t-count").textContent = `${done}/${todos.length}`;
  $("#todo-list").innerHTML = todos.map((t, i) =>
    `<li${i === newIndex ? ' class="is-new"' : ""}><label><input type="checkbox" data-i="${i}"${t.done ? " checked" : ""}><span>${esc(t.text)}</span></label></li>`).join("");
}
$("#todo-list").addEventListener("change", (e) => {
  const i = Number(e.target.dataset.i);
  if (!Number.isInteger(i)) return;
  todos[i].done = e.target.checked;
  renderTodos(); renderBrief();
  if (LIVE && todos[i].id) {
    fetch("api/taches/cocher", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: todos[i].id, fait: todos[i].done }) }).catch(() => {});
  }
});

/* Statuts : vert si le service répond, orange s'il est coupé (ou injoignable) */
function majStatut(id, nom, etat) {
  const li = document.getElementById(id);
  if (!li) return;
  li.querySelector(".dot").className = "dot " + (etat === "ok" ? "ok" : "warn");
  li.title = `${nom} : ${etat === "ok" ? "connecté" : etat === "coupe" ? "déconnecté" : "état inconnu"}`;
}
if (!LIVE) { majStatut("st-hermes", "Hermes", "ok"); majStatut("st-telegram", "Telegram", "ok"); }

/* Données réelles (en ligne) */
const toAdresse = (s) => ({ vous: s, tu: s });
async function chargerDonnees() {
  if (!LIVE) return;
  try {
    const r = await fetch("api/donnees", { cache: "no-store" });
    if (r.status === 401) { location.reload(); return; }
    if (!r.ok) { majStatut("st-hermes", "Hermes", "coupe"); return; }
    const d = await r.json();
    reminders.splice(0, reminders.length, ...d.rappels.map((x) => ({ day: x.jour, time: x.heure, text: x.texte })));
    if (d.taches) {
      todos.splice(0, todos.length, ...d.taches.du_jour.map((t) => ({ id: t.id, text: t.texte, done: !!t.fait })));
    }
    memory.known.splice(0, memory.known.length, ...d.souvenirs.map(toAdresse));
    memory.pending.splice(0, memory.pending.length, ...d.en_attente.map(toAdresse));
    skills.splice(0, skills.length, ...d.savoir_faire.map((s) => ({ name: s.nom, uses: 0, description: s.description })));
    $("#routine-list").innerHTML = d.routines.length
      ? d.routines.map((x) => `<li><span class="t-time">${esc(x.heure)}</span><span class="t-name">${esc(x.nom.replace(/-/g, " ").replace(/^./, (c) => c.toUpperCase()))}</span><span class="t-chan">${esc(x.canal)}</span></li>`).join("")
      : '<li class="r-empty">Aucune routine.</li>';
    document.querySelector("#routine-list").closest(".panel").querySelector(".panel-meta").textContent = String(d.routines.length).padStart(2, "0");
    majStatut("st-hermes", "Hermes", d.hermes ? "ok" : "coupe");
    majStatut("st-telegram", "Telegram", d.telegram || "inconnu");
    briefDuJour = d.brief || null;
    renderReminders(); renderTodos(); renderMemory(); renderSkills(); renderBrief();
  } catch { /* hors ligne : on garde l'affichage */ }
}

/* Mémoire : ce qui est retenu, et ce qui attend votre accord */
function renderMemory(newKnown = -1, newPending = -1) {
  const k = tu() ? "tu" : "vous";
  $("#m-count").textContent = String(memory.known.length).padStart(2, "0");
  $("#m-list").innerHTML = memory.known.map((m, i) => `<li${i === newKnown ? ' class="is-new"' : ""}>${esc(m[k])}</li>`).join("");
  // En ligne, la validation passe par la commande d'Hermes (memory.write_approval) : un simple « oui »
  // ne valide rien. Affichage seul ici ; la commande se tape à Jarvis sur Telegram.
  $("#m-pending").innerHTML = memory.pending.map((m, i) => `
    <li${i === newPending ? ' class="is-new"' : ""}>
      <span class="m-tag">À retenir ?</span>${esc(m[k])}
      ${LIVE ? `<p class="m-hint">${V("Pour valider, envoyez à", "Pour valider, envoie à")} ${esc(config.assistant.affiche || config.assistant.nom)} sur Telegram <code>/memory approve all</code>, ou <code>/memory reject all</code> ${V("pour refuser", "pour refuser")}. <code>/memory pending</code> ${V("liste les souvenirs en attente, avec leur numéro pour n'en valider qu'un", "liste les souvenirs en attente, avec leur numéro pour n'en valider qu'un")}.</p>` : `<div class="m-actions">
        <button type="button" class="small-btn primary" data-keep="${i}">Retenir</button>
        <button type="button" class="small-btn" data-drop="${i}">Oublier</button>
      </div>`}
    </li>`).join("");
}
$("#m-pending").addEventListener("click", (e) => {
  const keep = e.target.dataset.keep, drop = e.target.dataset.drop;
  if (keep !== undefined) {
    memory.known.unshift(memory.pending.splice(Number(keep), 1)[0]);
    renderMemory(0);
  } else if (drop !== undefined) {
    memory.pending.splice(Number(drop), 1);
    renderMemory();
  }
});

/* Savoir-faire */
function renderSkills(newIndex = -1) {
  $("#s-count").textContent = String(skills.length).padStart(2, "0");
  $("#s-list").innerHTML = skills.map((s, i) =>
    `<li${i === newIndex ? ' class="is-new"' : ""}${s.description ? ` title="${esc(s.description)}"` : ""}><span>${esc(s.name)}</span><span class="s-uses">${s.uses ? `${s.uses} fois` : "appris"}</span></li>`).join("")
    || '<li class="r-empty">Rien encore : après une tâche réussie, demandez-lui de retenir la méthode.</li>';
}

/* Brief du matin : rubriques choisies dans la config ; une fois le brief envoyé par Hermes,
   les rubriques préparées (actualité de l'IA, rubriques ajoutées) montrent son vrai contenu du jour */
let briefDuJour = null;   // { heure, rubriques: { "titre normalise": [lignes] } } ou null avant l'envoi
const cleTitre = (t) => t.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
function contenuBrief(titre) {
  const c = cleTitre(titre), r = briefDuJour?.rubriques || {};
  const k = Object.keys(r).find((x) => x === c || x.startsWith(c + " "));
  return k ? r[k] : null;
}
function rubriquePreparee(titre, attente) {
  const lignes = contenuBrief(titre);
  if (!lignes || !lignes.length) return `<b>${esc(titre)}</b> : ${attente}`;
  if (lignes.length === 1) return `<b>${esc(titre)}</b> : ${esc(lignes[0])}`;
  return `<b>${esc(titre)}</b><ul class="b-titres">${lignes.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
}
function renderBrief() {
  const on = (id) => (config.brief.rubriques || []).some((r) => r.id === id && r.actif);
  const items = [];
  if (on("meteo") && weather) {
    const d = weather.daily;
    const { label } = describe(d.weather_code[0], 1);
    items.push(`<b>Météo</b> : ${label.toLowerCase()}, de ${Math.round(d.temperature_2m_min[0])}° à ${Math.round(d.temperature_2m_max[0])}° à ${esc(config.ville.nom)}.`);
  }
  if (on("rappels")) {
    const today = reminders.filter((r) => r.day === "Auj.").length;
    items.push(`<b>Rappels</b> : ${today ? `${today} aujourd’hui` : "rien aujourd’hui"}, ${reminders.length} au total.`);
  }
  if (on("taches_veille")) {
    const left = todos.filter((t) => !t.done).length;
    items.push(`<b>Tâches</b> : ${left} reprise${left > 1 ? "s" : ""} d’hier.`);
  }
  const [hh, mm] = (config.brief.heure || "07:30").split(":");
  const heure = `${Number(hh)} h${mm === "00" ? "" : " " + mm}`;   // « 7 h 30 »
  if (on("actu_ia")) items.push(rubriquePreparee("Actualité de l’IA", `trois titres choisis au brief de ${heure}.`));
  // rubriques ajoutées par la personne à l'installation
  for (const r of config.brief.rubriques || []) {
    if (r.actif && !["meteo", "rappels", "taches_veille", "actu_ia"].includes(r.id)) items.push(rubriquePreparee(r.titre, `préparé par ${esc(config.assistant.affiche || config.assistant.nom)} au brief de ${heure}.`));
  }
  $("#b-list").innerHTML = items.map((t) => `<li><span>${t}</span></li>`).join("");
}

/* Onglets */
const tabs = [...document.querySelectorAll('.tabs [role="tab"]')];
tabs.forEach((t) => t.addEventListener("click", () => {
  tabs.forEach((x) => {
    const on = x === t;
    x.setAttribute("aria-selected", String(on));
    document.getElementById(x.getAttribute("aria-controls")).hidden = !on;
  });
}));
function showTab(id) { document.getElementById(id).click(); }

/* ================= Discussion ================= */
// Markdown minimal et sûr : paragraphes, listes, gras, et blocs ```carte {json}```.
function md(s) {
  const parts = [];
  const text = s.replace(/```carte\s*\n?([\s\S]*?)```/g, (_, json) => {
    parts.push(json);
    return `\n\n@@CARTE${parts.length - 1}@@\n\n`;
  }).replace(/```carte[\s\S]*$/, ""); // carte encore en cours de réception
  const html = esc(text).split(/\n{2,}/).map((b) => {
    const m = b.trim().match(/^@@CARTE(\d+)@@$/);
    if (m) return renderCard(parts[Number(m[1])]);
    if (!b.trim()) return "";
    const lines = b.split("\n");
    if (lines.every((l) => /^\s*[-•]\s+/.test(l))) {
      return "<ul>" + lines.map((l) => `<li>${l.replace(/^\s*[-•]\s+/, "")}</li>`).join("") + "</ul>";
    }
    return `<p>${lines.join("<br>")}</p>`;
  }).join("");
  return html.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}
function renderCard(json) {
  try {
    const c = JSON.parse(json);
    const rows = (c.lignes || []).map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("");
    return `<div class="card"><p class="card-title">${esc(c.titre || "Résultat")}</p><dl class="card-rows">${rows}</dl>${c.note ? `<p class="card-note">${esc(c.note)}</p>` : ""}</div>`;
  } catch {
    return ""; // carte encore incomplète pendant le flux
  }
}

const transcript = $("#transcript");
const hhmm = () => new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
function addMsg(who, text = "") {
  const el = document.createElement("div");
  el.className = `msg ${who}`;
  el.innerHTML = `<span class="msg-meta">${who === "user" ? V("Vous", "Toi") : esc(config.assistant.affiche || config.assistant.nom)} · ${hhmm()}</span><div class="msg-body"></div>`;
  el.querySelector(".msg-body").innerHTML = md(text);
  transcript.appendChild(el);
  scrollDown();
  return el.querySelector(".msg-body");
}
function scrollDown() {
  transcript.scrollTop = transcript.scrollHeight;
  if (matchMedia("(max-width: 1099px)").matches) window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

// L'API réelle (/api/chat, flux SSE au format OpenAI) en ligne, sinon la maquette.
// L'historique de la discussion est renvoyé à chaque message (24 derniers au plus).
const historique = [];
async function ask(text, onDelta) {
  historique.push({ role: "user", content: text });
  if (LIVE) {
    try {
      const r = await fetch("api/chat", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: historique.slice(-24) }),
      });
      if (r.status === 401) { location.reload(); return ""; }
      if (!r.ok || !r.body) {
        const d = await r.json().catch(() => ({}));
        const msg = d.erreur || "Jarvis ne répond pas pour le moment.";
        onDelta(msg);
        return msg;
      }
      const full = await lireFlux(r, onDelta);
      historique.push({ role: "assistant", content: full });
      return full;
    } catch {
      const msg = "La connexion avec Jarvis a été coupée. Réessayez dans un instant.";
      onDelta(msg);
      return msg;
    }
  }
  try {
    const r = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: historique.slice(-24) }),
    });
    if (!r.ok || !r.body || !(r.headers.get("content-type") || "").includes("text/event-stream")) throw new Error("maquette");
    return await lireFlux(r, onDelta);
  } catch {
    const reply = await mockReply(text);
    for (const chunk of reply.match(/```carte[\s\S]*?```|\S+\s*|\s+/g) || []) {
      await sleep(chunk.startsWith("```") ? 120 : 28 + Math.random() * 40);
      onDelta(chunk);
    }
    historique.push({ role: "assistant", content: reply });
    return reply;
  }
}
async function lireFlux(r, onDelta) {
  {
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "", full = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const ev = buf.slice(0, i); buf = buf.slice(i + 2);
        const data = ev.split("\n").filter((l) => l.startsWith("data:")).map((l) => l.slice(5).trim()).join("");
        if (!data || data === "[DONE]") continue;
        let delta = "";
        try { delta = JSON.parse(data).choices?.[0]?.delta?.content || ""; } catch {}
        if (delta) { full += delta; onDelta(delta); }
      }
    }
    return full;
  }
}

async function mockReply(text) {
  await sleep(900);
  const t = text.toLowerCase();
  const nom = nomAdresse();

  if (/m[ée]t[ée]o|quel temps|pluie|fait-il|temp[ée]rature/.test(t) && weather) {
    const c = weather.current, d = weather.daily;
    const { label } = describe(c.weather_code, c.is_day);
    return `À ${config.ville.nom}, ${nom} : **${Math.round(c.temperature_2m)}°**, ${label.toLowerCase()}, ressenti ${Math.round(c.apparent_temperature)}°.\n\nAujourd’hui, de ${Math.round(d.temperature_2m_min[0])}° à ${Math.round(d.temperature_2m_max[0])}°, vent à ${Math.round(c.wind_speed_10m)} km/h.`;
  }

  if (/rappel/.test(t)) {
    const m = t.match(/(\d{1,2})\s*h\s*(\d{2})?/);
    const time = m ? `${m[1].padStart(2, "0")}:${m[2] || "00"}` : "09:00";
    const days = { demain: "Dem.", lundi: "Lun.", mardi: "Mar.", mercredi: "Mer.", jeudi: "Jeu.", vendredi: "Ven.", samedi: "Sam.", dimanche: "Dim." };
    const key = Object.keys(days).find((k) => t.includes(k));
    const what = text
      .replace(/^.*?rappel(le|les)?[- ]?(moi|nous)?\s*/i, "")
      .replace(/(^|\s)(demain|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)(?=\s|$)/gi, " ")
      .replace(/(^|\s)(à|a|vers)?\s*\d{1,2}\s*h\s*\d{0,2}(?=\s|$)/gi, " ")
      .replace(/\s+/g, " ").trim()
      .replace(/^(de |d’|d')/i, "") || "votre rappel";
    const r = { day: key ? days[key] : "Auj.", time, text: cap(what) };
    reminders.push(r);
    sortReminders();
    showTab("tab-today");
    renderReminders(reminders.indexOf(r));
    renderBrief();
    return `C’est noté, ${nom}. Je ${V("vous", "te")} rappellerai **${what}** ${key || "aujourd’hui"} à ${time.replace(/^0/, "").replace(":00", " h").replace(":", " h ")}.`;
  }

  if (/(note|ajoute).*(t[âa]che)|t[âa]che.*(note|ajoute)/.test(t)) {
    const what = text.replace(/^.*?t[âa]che\s*(:|de |d’|d')?\s*/i, "").trim() || "Nouvelle tâche";
    todos.push({ text: cap(what), done: false });
    renderTodos(todos.length - 1);
    renderBrief();
    return `Ajouté aux tâches du jour : **${what}**.`;
  }

  if (/retiens comment|cr[ée]e?.*skill|retiens la m[ée]thode|apprends/.test(t)) {
    const name = cap(text.replace(/^.*?(comment|m[ée]thode|skill|apprends)\s*(on a fait|pour|de|d’|d')?\s*/i, "").trim() || "Méthode de cette tâche");
    skills.unshift({ name, uses: 0 });
    showTab("tab-jarvis");
    renderSkills(0);
    return `C’est retenu, ${nom}. La prochaine fois, je referai **${name.toLowerCase()}** de la même façon, étape par étape, sans qu’${V("il vous faille", "il te faille")} me réexpliquer.`;
  }

  if (/retiens que|souviens-toi|je pr[ée]f[èe]re|n'oublie pas que|n’oublie pas que/.test(t)) {
    const raw = text.replace(/^.*?(retiens que|souviens-toi que|souviens-toi|je pr[ée]f[èe]re|n['’]oublie pas que)\s*/i, "").trim();
    const fact = cap(raw.replace(/\.$/, "")) + ".";
    memory.pending.unshift({ vous: fact, tu: fact });
    showTab("tab-jarvis");
    renderMemory(-1, 0);
    return `Je propose de retenir : « ${fact} »\n\nCela attend ${V("votre", "ton")} accord dans le panneau « ${V("Ce que je sais de vous", "Ce que je sais de toi")} ».`;
  }

  if (/point|rapport|bilan|r[ée]sum[ée]/.test(t)) {
    const left = todos.filter((x) => !x.done).length;
    const next = reminders[0];
    const card = {
      titre: "Point de la journée",
      lignes: [
        ["Rappels aujourd’hui", String(reminders.filter((r) => r.day === "Auj.").length)],
        ["Prochain rappel", next ? `${next.day} ${next.time}` : "aucun"],
        ["Tâches faites", `${todos.length - left} / ${todos.length}`],
        ["Météo", weather ? `${Math.round(weather.current.temperature_2m)}°, ${describe(weather.current.weather_code, 1).label.toLowerCase()}` : "—"],
      ],
      note: left ? `Il ${V("vous", "te")} reste ${left} tâche${left > 1 ? "s" : ""}.` : "Tout est fait pour aujourd’hui.",
    };
    return `Voici le point, ${nom}.\n\n\`\`\`carte\n${JSON.stringify(card)}\n\`\`\``;
  }

  if (/^(bonjour|salut|hello|bonsoir|hey)/.test(t)) {
    return `Bonjour, ${nom}. Tout est en ordre. Que puis-je faire pour ${V("vous", "toi")} ?`;
  }

  return `Je ne suis encore qu’une maquette, ${nom} : une fois relié à Hermes, je ${V("vous", "te")} répondrai pour de vrai.\n\n${V("Vous pouvez", "Tu peux")} déjà essayer :\n- « Fais-moi le point »\n- « Rappelle-moi jeudi à 18 h d’appeler le garage »\n- « Note la tâche : envoyer la facture »\n- « Retiens que je préfère le café sans sucre »\n- « Retiens comment on a fait le brief »`;
}

/* ================= Voix du navigateur ================= */
const voiceBtn = $("#voice");
function setVoice(on) {
  voiceBtn.setAttribute("aria-pressed", String(on));
  $("#set-voix").checked = on;
  if (!on && "speechSynthesis" in window) speechSynthesis.cancel();
  if (!on) { paroleId++; voixEnCours?.pause(); }
}
voiceBtn.addEventListener("click", () => { const on = !config.voix; saveSetting("voix", on); setVoice(on); });
// Voix française masculine, les voix « naturelles » (Edge, Windows) d'abord.
function choisirVoix() {
  const vs = speechSynthesis.getVoices().filter((x) => x.lang.startsWith("fr"));
  const homme = /henri|remy|rémy|paul|thomas|homme|male/i;
  return vs.find((x) => homme.test(x.name) && /natural|online/i.test(x.name))
    || vs.find((x) => homme.test(x.name)) || vs[0] || null;
}
// les voix arrivent parfois après le chargement de la page
function voixPretes() {
  if (!("speechSynthesis" in window) || speechSynthesis.getVoices().length) return Promise.resolve();
  return Promise.race([new Promise((r) => speechSynthesis.addEventListener("voiceschanged", r, { once: true })), sleep(1500)]);
}
// --- Voix du serveur (locale, gratuite) : Pocket TTS, la même voix pour l'accueil et les réponses ---
// Le serveur renvoie l'audio ; il passe ici par un léger traitement « IA » (filtre, doublage
// très court, à peine audible) et son volume réel anime la sphère.
let sonCtx = null, sonEntree = null, sonMesure = null, voixEnCours = null;
function chaineSon() {
  if (sonCtx) return sonCtx;
  sonCtx = window.__sonCtx || new (window.AudioContext || window.webkitAudioContext)();   // celui du préchargeur, s'il existe
  sonEntree = sonCtx.createGain();
  const passeHaut = sonCtx.createBiquadFilter();
  passeHaut.type = "highpass"; passeHaut.frequency.value = 110;
  const presence = sonCtx.createBiquadFilter();
  presence.type = "peaking"; presence.frequency.value = 3200; presence.Q.value = 0.8; presence.gain.value = 2.5;
  const echo = sonCtx.createDelay(0.1);
  echo.delayTime.value = 0.014;
  const echoGain = sonCtx.createGain();
  echoGain.gain.value = 0.16;
  sonMesure = sonCtx.createAnalyser();
  sonMesure.fftSize = 1024;
  // Pocket TTS sort très bas (environ -31 dB RMS, quand un morceau du commerce tourne vers -9) :
  // compresseur doux, gain, puis limiteur. Mesuré : -18 dB RMS, crêtes à -2 dB (+13 dB).
  const compresseur = sonCtx.createDynamicsCompressor();
  compresseur.threshold.value = -32; compresseur.knee.value = 12; compresseur.ratio.value = 3;
  compresseur.attack.value = 0.004; compresseur.release.value = 0.2;
  const gainVoix = sonCtx.createGain();
  gainVoix.gain.value = 1.6;
  const limiteur = sonCtx.createDynamicsCompressor();
  limiteur.threshold.value = -6; limiteur.knee.value = 0; limiteur.ratio.value = 20;
  limiteur.attack.value = 0.001; limiteur.release.value = 0.1;
  sonEntree.connect(passeHaut).connect(presence);
  presence.connect(sonMesure);
  presence.connect(echo).connect(echoGain).connect(sonMesure);
  sonMesure.connect(compresseur).connect(gainVoix).connect(limiteur).connect(sonCtx.destination);
  return sonCtx;
}
// --- Sons de l'interface (règle « Sons du motion design ») ---
// Fichiers et licences : web/sons/LICENCES.md. Discrets, coupés par le réglage « Sons de l'interface ».
// Ils passent par le contexte audio de la page, sans le filtre de la voix.
const SONS = { sphere: "sons/sphere.mp3?v=3", element: "sons/element.mp3?v=1", frappe: "sons/frappe.mp3?v=1",
  fin: "sons/fin.mp3?v=1" };   // fin : aucun son livré ; joué seulement si la personne en a déposé un (envoyer-son fin)   // ?v : changer à chaque nouveau son
const tampons = {};
let sortieSons = null;
function preparerSons() {
  if (config.sons === false || !window.AudioContext && !window.webkitAudioContext) return;
  let ctx;
  try { ctx = chaineSon(); } catch { return; }
  if (!sortieSons) { sortieSons = ctx.createGain(); sortieSons.connect(ctx.destination); }
  for (const [nom, url] of Object.entries(SONS)) {
    tampons[nom] ??= fetch(url).then((r) => r.arrayBuffer()).then((b) => ctx.decodeAudioData(b)).catch(() => null);
  }
}
// volume : 0 à 1 ; hauteur : 1 = normale ; dans : délai en secondes
async function jouerSon(nom, { volume = 0.2, hauteur = 1, dans = 0 } = {}) {
  if (config.sons === false || !sonCtx || !tampons[nom]) return;
  const tampon = await tampons[nom];
  if (!tampon) return;
  if (sonCtx.state === "suspended") await sonCtx.resume().catch(() => {});
  const src = sonCtx.createBufferSource(), g = sonCtx.createGain();
  src.buffer = tampon; src.playbackRate.value = hauteur; g.gain.value = volume;
  src.connect(g).connect(sortieSons);
  src.start(sonCtx.currentTime + dans);
}

// L'audio du serveur (Blob), ou null en cas d'échec.
async function obtenirAudio(texte) {
  try {
    const r = await fetch("api/voix", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texte, genre: config.genre_voix === "femme" ? "femme" : "homme" }) });
    return r.ok ? await r.blob() : null;
  } catch { return null; }
}
// audio : Blob (ou promesse) déjà préparé ; onDebut : appelé quand le son démarre vraiment.
async function parlerServeur(texte, { audio: pret, onDebut } = {}) {
  const blob = await (pret || obtenirAudio(texte));
  if (!blob) return "serveur";
  const url = URL.createObjectURL(blob);
  const el = new Audio(url);
  try {
    const ctx = chaineSon();
    if (ctx.state === "suspended") await ctx.resume().catch(() => {});
    ctx.createMediaElementSource(el).connect(sonEntree);
  } catch {}
  const mesures = new Float32Array(sonMesure ? sonMesure.fftSize : 0);
  let anim = 0;
  const suivre = () => {
    if (sonMesure) {
      sonMesure.getFloatTimeDomainData(mesures);
      let s = 0;
      for (const x of mesures) s += x * x;
      orb.setLevel(Math.min(1, Math.sqrt(s / mesures.length) * 5));
    }
    anim = requestAnimationFrame(suivre);
  };
  const fin = (res) => { cancelAnimationFrame(anim); orb.setLevel(0); URL.revokeObjectURL(url); return res; };
  try { await el.play(); } catch (e) { return fin(e.name === "NotAllowedError" ? "not-allowed" : "lecture"); }
  if (onDebut) onDebut();
  suivre();
  voixEnCours = el;
  await new Promise((ok) => { el.onended = ok; el.onerror = ok; el.onpause = ok; });
  voixEnCours = null;
  return fin(null);
}

// Découpe en morceaux de quelques phrases (~280 caractères, le premier ~150) : le premier part vite, le suivant
// se prépare pendant que le précédent se lit.
function decouper(texte, max = 280) {
  const phrases = texte.replace(/\s+/g, " ").match(/[^.!?…]+(?:[.!?…]+|$)/g) || [texte];
  const morceaux = [];
  let cours = "";
  for (let p of phrases.map((x) => x.trim()).filter(Boolean)) {
    while (p.length > max) {                         // phrase trop longue : coupée à une virgule
      const i = Math.max(p.lastIndexOf(", ", max), p.lastIndexOf(" ", max));
      const tete = p.slice(0, i > 40 ? i + 1 : max).trim();
      if (cours) { morceaux.push(cours); cours = ""; }
      morceaux.push(tete);
      p = p.slice(tete.length).trim();
    }
    const limite = morceaux.length ? max : 150;     // premier morceau court : le son part plus vite
    if (cours && (cours + " " + p).length > limite) { morceaux.push(cours); cours = ""; }
    cours = cours ? cours + " " + p : p;
  }
  if (cours) morceaux.push(cours);
  return morceaux;
}
let paroleId = 0;    // change à chaque nouvelle parole ou quand on coupe la voix : la lecture en cours s'arrête
async function parlerParMorceaux(clean, opts) {
  const id = ++paroleId;
  const morceaux = opts.morceaux || (opts.audio ? [clean] : decouper(clean));
  let suivant = opts.audio || obtenirAudio(morceaux[0]);
  for (let i = 0; i < morceaux.length; i++) {
    const blob = await suivant;
    if (id !== paroleId) return null;
    if (!blob) return i === 0 ? "serveur" : null;
    suivant = i + 1 < morceaux.length ? obtenirAudio(morceaux[i + 1]) : null;
    const err = await parlerServeur(morceaux[i], { audio: blob, onDebut: i === 0 ? opts.onDebut : undefined });
    if (err || id !== paroleId) return err;
  }
  return null;
}

// force : parler même si la lecture des réponses est coupée (accueil). Renvoie l'erreur éventuelle.
// Voix du serveur (Pocket TTS) ; sans elle, ou en cas d'échec, voix du navigateur.
async function speak(text, opts = {}) {
  if (!config.voix && !opts.force) return "coupe";
  const clean = text.replace(/```carte[\s\S]*?```/g, "").replace(/\*\*/g, "").replace(/^- /gm, "").trim();
  if (LIVE && config.voix_locale && clean) {
    const err = await parlerParMorceaux(clean, opts);
    if (err === null || err === "not-allowed") return err;
  }
  await voixPretes();
  return parlerNavigateur(clean, opts);
}
function parlerNavigateur(clean, { rate = 1.02, pitch = 1, onDebut } = {}) {
  return new Promise((resolve) => {
    if (!("speechSynthesis" in window)) return resolve("coupe");
    const u = new SpeechSynthesisUtterance(clean);
    u.lang = "fr-FR";
    const v = choisirVoix();
    if (v) u.voice = v;
    u.rate = rate;
    u.pitch = pitch;
    u.onboundary = () => orb.kick(0.55 + Math.random() * 0.4);
    if (onDebut) u.onstart = onDebut;
    u.onend = () => resolve(null);
    u.onerror = (e) => resolve(e.error || "erreur");
    speechSynthesis.speak(u);
  });
}

/* ================= Accueil parlé à la connexion ================= */
// Comme Jarvis au réveil de Tony Stark : phrases courtes et posées. L'heure, la météo de la
// ville en une phrase qui suit le temps qu'il fait, la température, un mot sur le vent ou
// l'humidité, puis le nombre de tâches du jour. Rien de plus.
function phraseHeure(d) {
  const h = d.getHours(), m = d.getMinutes();
  const heures = h === 0 ? "minuit" : h === 12 ? "midi" : `${h} heure${h > 1 ? "s" : ""}`;
  return m ? `${heures} ${m}` : heures;
}
function phraseCiel(code, jour) {
  if (code === 0) return jour ? "Il fait beau, pas un nuage dans le ciel." : "Le ciel est parfaitement dégagé.";
  if (code === 1) return jour ? "Il fait beau, à peine quelques nuages." : "Le ciel est dégagé, à peine quelques nuages.";
  if (code === 2) return "Le ciel est partiellement nuageux.";
  if (code === 3) return "Le ciel est couvert.";
  if ([45, 48].includes(code)) return "Un brouillard couvre la ville.";
  if ([51, 53, 55].includes(code)) return "Une légère bruine tombe.";
  if ([56, 57, 66, 67].includes(code)) return "Une pluie verglaçante tombe, prudence sur la route.";
  if ([61, 80].includes(code)) return "Il pleut légèrement.";
  if ([63, 81].includes(code)) return "Il pleut.";
  if ([65, 82].includes(code)) return "Il pleut fortement.";
  if ([71, 73, 75, 77, 85, 86].includes(code)) return "Il neige.";
  if ([95, 96, 99].includes(code)) return "Un orage est en cours.";
  return "";
}
const degres = (t) => `${t < 0 ? "moins " : ""}${Math.abs(t)} degré${Math.abs(t) > 1 ? "s" : ""}`;
function phraseComplement(c) {
  const vent = Math.round(c.wind_speed_10m), hum = Math.round(c.relative_humidity_2m);
  if (vent >= 40) return `Le vent souffle fort, ${vent} kilomètres heure.`;
  if (vent >= 20) return `Le vent est soutenu, ${vent} kilomètres heure.`;
  if (hum >= 85) return `L'air est très humide, ${hum} pour cent.`;
  if (hum <= 35) return `L'air est sec, ${hum} pour cent d'humidité.`;
  if (vent < 8) return "Le vent est presque nul.";
  return `Le vent est faible, ${vent} kilomètres heure.`;
}
function texteAccueil() { return partiesAccueil().join(" "); }
function partiesAccueil() {
  const d = new Date();
  const h = d.getHours();
  const nom = nomAdresse();
  // seul point d'exclamation : la salutation (le juste milieu entre un ton froid et trop d'enthousiasme)
  const p = [`${h >= 5 && h < 18 ? "Bonjour" : "Bonsoir"}, ${nom} ! Démarrage des diagnostics.`, `À ${config.ville.nom}, il est ${phraseHeure(d)}.`];
  if (weather) {
    const c = weather.current;
    const t = Math.round(c.temperature_2m), r = Math.round(c.apparent_temperature);
    const ciel = phraseCiel(c.weather_code, c.is_day);
    if (ciel) p.push(ciel);
    p.push(`Il fait ${degres(t)}${Math.abs(r - t) >= 3 ? `, ressenti ${degres(r)}` : ""}.`);
    p.push(phraseComplement(c));
  }
  const n = todos.filter((x) => !x.done).length;
  // n : tâches du jour pas encore faites
  p.push(n === 0 ? V("Vous n'avez aucune tâche en cours.", "Tu n'as aucune tâche en cours.")
    : n === 1 ? V("Vous avez une tâche en cours.", "Tu as une tâche en cours.")
    : V(`Vous avez ${n} tâches en cours.`, `Tu as ${n} tâches en cours.`));
  return p;
}
// Une fois par session du navigateur (une nouvelle connexion remet le compteur à zéro).
// Si le navigateur refuse le son avant toute action, l'accueil attend le premier clic ou la première touche.
function accueilAFaire() {
  if (config.accueil === false || !(config.voix_locale || "speechSynthesis" in window)) return false;
  try { return sessionStorage.getItem("jarvis.accueil") !== "fait"; } catch { return true; }
}
// La voix du serveur met quelques secondes à produire l'accueil : on la lance dès que la météo
// et les tâches sont là (pendant le chargement), pour qu'elle parte avec l'animation de la sphère.
let accueilPrepare = null;
function preparerAccueil() {
  if (!LIVE || !config.voix_locale || !accueilAFaire() || accueilPrepare) return;
  // en deux temps : la salutation, courte, est synthétisée en moins d'une seconde ; le reste se
  // prépare pendant qu'elle est dite (sinon la voix partait 2 à 3 s après la sphère)
  const parties = partiesAccueil();
  const morceaux = [parties[0], ...decouper(parties.slice(1).join(" "))];
  accueilPrepare = { texte: parties.join(" "), morceaux, audio: obtenirAudio(morceaux[0]) };
  // la chaîne audio se crée maintenant (pendant le chargement) et pas au premier son : sa création
  // peut bloquer la page un instant, ce qui faisait « sauter » la sphère au démarrage de la voix
  try { chaineSon(); } catch {}
}
async function accueilParle() {
  if (!accueilAFaire()) return false;
  const dire = async () => {
    try { sessionStorage.setItem("jarvis.accueil", "fait"); } catch {}
    attenuerMusique(true);                        // la musique s'efface pendant que Jarvis parle
    const prep = accueilPrepare;
    // la sphère passe en « parole » au moment où le son démarre, pas avant
    const err = await speak(prep ? prep.texte : texteAccueil(), {
      force: true, mode: "accueil", rate: 0.96, pitch: 0.92,
      audio: prep && prep.audio, morceaux: prep && prep.morceaux, onDebut: () => setState("speaking"),
    });
    setState("idle");                             // et revient en fondu
    return err;
  };
  const geste = navigator.userActivation ? navigator.userActivation.hasBeenActive : true;
  if (geste && (await dire()) !== "not-allowed") return true;
  try { sessionStorage.removeItem("jarvis.accueil"); } catch {}
  await new Promise((go) => ["pointerdown", "keydown"].forEach((t) => addEventListener(t, go, { capture: true, once: true })));
  if (config.accueil !== false) await dire();
  return true;
}

/* ================= Envoi ================= */
const form = $("#composer");
const input = $("#prompt");
let busy = false;
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text || busy) return;
  busy = true;
  form.querySelector(".send").disabled = true;
  input.value = "";
  addMsg("user", text);
  setState("thinking");
  const body = addMsg("jarvis");
  body.classList.add("typing");
  let acc = "", first = true;
  const full = await ask(text, (delta) => {
    if (first) { setState("speaking"); first = false; }
    acc += delta;
    body.innerHTML = md(acc);
    orb.kick(0.35 + Math.min(delta.length, 12) / 30);
    scrollDown();
  });
  body.classList.remove("typing");
  // l'orbe reste animée le temps de la lecture du texte, puis retombe ; en conversation, la réponse
  // est toujours dite à voix haute
  if (config.voix || conversation) await speak(full, { force: conversation });
  else await sleep(Math.min(2500, 400 + full.length * 12));
  setState("idle");
  chargerDonnees();   // un rappel ou une tâche a pu être créé pendant l'échange
  busy = false;
  form.querySelector(".send").disabled = false;
  // conversation : le micro se rouvre après la réponse, sauf après « merci Jarvis »
  if (conversation) {
    if (finDemandee) { finDemandee = false; finirConversation(); }
    else { startMic(); return; }
  }
  if (matchMedia("(hover: hover)").matches) input.focus();
});

/* ================= Micro et mode conversation ================= */
// Un clic sur le micro ouvre une conversation : après chaque réponse (dite à voix haute), le micro
// se rouvre seul. Elle se ferme après 8 s sans parole, sur « merci Jarvis » (Jarvis répond alors
// d'une formule de politesse, consigne de sa personnalité) ou sur un nouveau clic.
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const micBtn = $("#mic");
if (!SR) micBtn.hidden = true;
const SILENCE_MAX = 8000;
let rec = null, stream = null, raf = 0;
let conversation = false, finDemandee = false, ouvertA = 0, minuteurSilence = 0;
const placeholderInitial = input.placeholder;
function estUnMerci(texte) {
  const nom = cleTitre(config.assistant.nom || "Jarvis");
  const t = cleTitre(texte);
  return /\bmerci\b/.test(t) && t.includes(nom) && t.split(" ").length <= 8;
}
function finirConversation() {
  conversation = false;
  clearTimeout(minuteurSilence);
  micBtn.classList.remove("conversation");
  input.placeholder = placeholderInitial;
  attenuerMusique(false);
}
async function startMic() {
  rec = new SR();
  rec.lang = "fr-FR";
  rec.interimResults = true;
  rec.continuous = false;
  rec.onresult = (e) => {
    clearTimeout(minuteurSilence);                 // on parle : plus de coupure au bout de 8 s
    input.value = Array.from(e.results).map((r) => r[0].transcript).join("");
  };
  // chaque reconnaissance ne ferme qu'elle-même (son « onend » arrive après « onerror », parfois
  // quand la suivante est déjà ouverte)
  const r = rec;
  r.onend = () => { if (rec === r) stopMic(); };
  r.onerror = (e) => { if (rec === r) stopMic(e && e.error); };
  r.start();
  if (!ouvertA) ouvertA = performance.now();
  clearTimeout(minuteurSilence);
  minuteurSilence = setTimeout(() => { if (rec && !input.value.trim()) { finirConversation(); stopMic(); } }, Math.max(0, SILENCE_MAX - (performance.now() - ouvertA)));
  micBtn.classList.add("recording");
  if (conversation) {
    micBtn.classList.add("conversation");
    input.placeholder = `${V("Je vous écoute…", "Je t’écoute…")} « merci ${config.assistant.nom || "Jarvis"} » pour finir`;
    attenuerMusique(true);                         // la musique s'efface pendant qu'on parle
  }
  setState("listening");
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const ctx = new AudioContext();
    const an = ctx.createAnalyser();
    an.fftSize = 512;
    ctx.createMediaStreamSource(stream).connect(an);
    const data = new Uint8Array(an.fftSize);
    const loop = () => {
      an.getByteTimeDomainData(data);
      let sum = 0;
      for (const v of data) sum += ((v - 128) / 128) ** 2;
      orb.setLevel(Math.min(1, Math.sqrt(sum / data.length) * 6));
      raf = requestAnimationFrame(loop);
    };
    loop();
  } catch { /* pas de niveau sonore : l'orbe reste en écoute */ }
}
function stopMic(erreur) {
  if (!rec) return;
  const r = rec; rec = null;
  try { r.stop(); } catch {}
  cancelAnimationFrame(raf);
  orb.setLevel(0);
  stream?.getTracks().forEach((t) => t.stop());
  stream = null;
  micBtn.classList.remove("recording");
  const texte = input.value.trim();
  if (texte) {
    ouvertA = 0;
    clearTimeout(minuteurSilence);
    if (conversation && estUnMerci(texte)) finDemandee = true;
    form.requestSubmit();
    return;
  }
  // rien entendu : en conversation, le navigateur coupe parfois avant 8 s (« no-speech ») ; on rouvre
  if (conversation && erreur !== "not-allowed" && erreur !== "aborted" && performance.now() - ouvertA < SILENCE_MAX - 500) {
    startMic();
    return;
  }
  ouvertA = 0;
  if (conversation) finirConversation();
  setState("idle");
}
micBtn.addEventListener("click", () => {
  if (rec || conversation) { finirConversation(); stopMic("aborted"); setState("idle"); return; }
  conversation = true; finDemandee = false; ouvertA = 0;
  startMic();
});

/* ================= Lecteur de musique ================= */
const audio = $("#p-audio");
const player = $("#player");
let playlist = [], track = 0;
// Volume : celui choisi (0,6 par défaut) multiplié par un facteur qui descend à 12 % pendant que
// Jarvis écoute, réfléchit ou parle (environ -18 dB), en fondu, puis remonte doucement.
const MUSIQUE_ATTENUEE = 0.12;
const volumeMusique = store.get("jarvis.volume", 0.6);
let facteurMusique = 1, cibleMusique = 1, fonduMusique = 0, retourMusique = 0;
audio.volume = volumeMusique;
function fondu(cible, duree) {
  cibleMusique = cible;
  const depart = facteurMusique, t0 = performance.now(), id = ++fonduMusique;
  const pas = () => {
    if (id !== fonduMusique) return;
    const k = Math.min(1, (performance.now() - t0) / duree);
    facteurMusique = depart + (cible - depart) * k * k * (3 - 2 * k);
    audio.volume = Math.max(0, Math.min(1, volumeMusique * facteurMusique));
    if (k < 1) setTimeout(pas, 30);       // minuterie et non image : marche aussi onglet en arrière-plan
  };
  pas();
}
function attenuerMusique(oui) {
  clearTimeout(retourMusique);
  if (oui) { if (cibleMusique !== MUSIQUE_ATTENUEE) fondu(MUSIQUE_ATTENUEE, 400); }
  else if (cibleMusique !== 1) retourMusique = setTimeout(() => fondu(1, 1500), 800);   // pas de pompage entre deux phrases
}
musiquePrete = true;

function loadTrack(i, autoplay = false) {
  if (!playlist.length) return;
  track = (i + playlist.length) % playlist.length;
  const t = playlist[track];
  audio.src = t.fichier;
  $("#p-title").textContent = t.titre;
  $("#p-artist").textContent = t.artiste || "";
  player.dataset.empty = "false";
  $("#p-play").setAttribute("aria-label", `Lire ${t.titre}`);
  if (autoplay) audio.play().catch(() => {});
}
async function loadPlaylist() {
  try {
    const r = await fetch(config.musique.playlist, { cache: "no-store" });
    const list = r.ok ? await r.json() : [];
    // ne garder que les fichiers présents
    const ok = await Promise.all(list.map((t) => fetch(t.fichier, { method: "HEAD" }).then((x) => x.ok).catch(() => false)));
    playlist = list.filter((_, i) => ok[i]);
  } catch { playlist = []; }
  if (playlist.length) loadTrack(0);
}
$("#p-play").addEventListener("click", () => {
  if (!playlist.length) { openSettings("#set-mp3"); return; }
  audio.paused ? audio.play().catch(() => {}) : audio.pause();
});
// Musique à l'ouverture (option, active par défaut) : elle part dès que la page est chargée, en
// même temps que l'accueil parlé (atténuée sous la voix). Les navigateurs refusent le son avant
// toute action de la personne (page rouverte sans saisir le mot de passe) : elle démarre alors au
// premier clic ou à la première touche.
let playlistChargee = Promise.resolve();
async function lancerMusiqueAuto() {
  await playlistChargee;
  if (config.musique?.auto === false || !playlist.length || !audio.paused) return;
  audio.play().catch(() => {
    const go = (e) => {
      ["pointerdown", "keydown"].forEach((t) => removeEventListener(t, go, true));
      // un clic sur ▶ est géré par le bouton lui-même (sinon il relancerait puis couperait aussitôt)
      if (e.target?.closest?.("#p-play")) return;
      if (config.musique?.auto !== false && audio.paused) audio.play().catch(() => {});
    };
    ["pointerdown", "keydown"].forEach((t) => addEventListener(t, go, { capture: true, once: true }));
  });
}
audio.addEventListener("play", () => player.classList.add("is-playing"));
audio.addEventListener("pause", () => player.classList.remove("is-playing"));
audio.addEventListener("ended", () => loadTrack(track + 1, true));
audio.addEventListener("timeupdate", () => {
  $("#p-progress").style.width = audio.duration ? `${(audio.currentTime / audio.duration) * 100}%` : "0";
});
// Musique d'ouverture : en ligne, le fichier est envoyé au serveur et gardé pour les prochaines
// ouvertures (un seul morceau, 10 Mo au plus, le nouveau remplace l'ancien). En maquette : lu sur place.
const MUSIQUE_MAX = 10 * 1024 * 1024;
const noteMp3 = $("#mp3-note");
function noterMp3(texte, erreur = false) {
  noteMp3.textContent = texte;
  noteMp3.classList.toggle("is-error", erreur);
}
$("#set-mp3").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  e.target.value = "";                 // rechoisir le même fichier relance l'envoi
  if (!f) return;
  if (!/\.(mp3|m4a|ogg)$/i.test(f.name)) return noterMp3("Format non pris en charge : MP3, M4A ou OGG.", true);
  if (f.size > MUSIQUE_MAX) return noterMp3(`Fichier trop gros (${(f.size / 1048576).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Mo) : 10 Mo au plus.`, true);
  if (!LIVE) {
    const base = f.name.replace(/\.[^.]+$/, "");
    const [artiste, titre] = base.includes(" - ") ? base.split(" - ", 2) : ["", base];
    playlist = [{ titre: titre.trim(), artiste: artiste.trim(), fichier: URL.createObjectURL(f) }];
    return loadTrack(0, true);
  }
  noterMp3("Envoi en cours…");
  try {
    const r = await fetch("api/musique", { method: "POST", body: f,
      headers: { "Content-Type": "application/octet-stream", "X-Nom-Fichier": encodeURIComponent(f.name) } });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) return noterMp3(d.erreur || "Envoi impossible.", true);
    noterMp3(`« ${d.fichier} » est gardée pour les prochaines ouvertures. Un nouveau MP3 la remplacera.`);
    audio.pause();
    await loadPlaylist();
    if (playlist.length) audio.play().catch(() => {});
  } catch { noterMp3("Envoi impossible : connexion au serveur perdue.", true); }
});

/* ================= Réglages ================= */
const settings = $("#settings");
const scrim = $("#scrim");
let lastFocus = null, savedScroll = 0;
function openSettings(focusSel) {
  lastFocus = document.activeElement;
  settings.hidden = false;
  scrim.hidden = false;
  // bloque le défilement de la page derrière (iOS ignore overflow:hidden sur body)
  savedScroll = scrollY;
  Object.assign(document.body.style, { position: "fixed", top: `-${savedScroll}px`, left: "0", right: "0" });
  document.body.classList.add("settings-open");
  $("#settings-body").scrollTop = 0;
  syncSettings();
  (focusSel ? $(focusSel) : $("#close-settings")).focus();
}
function closeSettings() {
  settings.hidden = true;
  scrim.hidden = true;
  document.body.classList.remove("settings-open");
  Object.assign(document.body.style, { position: "", top: "", left: "", right: "" });
  scrollTo(0, savedScroll);
  lastFocus?.focus();
}
$("#open-settings").addEventListener("click", () => openSettings());
$("#close-settings").addEventListener("click", closeSettings);
scrim.addEventListener("click", closeSettings);
addEventListener("keydown", (e) => { if (e.key === "Escape" && !settings.hidden) closeSettings(); });

function pressSeg(sel, v) {
  document.querySelectorAll(`${sel} button`).forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === v)));
}
function syncSettings() {
  const u = config.utilisateur;
  pressSeg("#set-adresse", u.adresse === "prenom" ? "prenom" : u.civilite);
  $("#set-prenom").value = u.prenom || "";
  $("#row-prenom").hidden = u.adresse !== "prenom";
  $("#set-tu").checked = !!u.tutoiement;
  pressSeg("#set-ton", config.ton);
  pressSeg("#set-accent", config.accent);
  $("#set-voix").checked = !!config.voix;
  pressSeg("#set-genre-voix", config.genre_voix === "femme" ? "femme" : "homme");
  $("#set-genre-voix").style.display = LIVE && config.voix_locale ? "" : "none";     // voix du serveur seulement
  $("#set-accueil").checked = config.accueil !== false;
  $("#set-sons").checked = config.sons !== false;
  $("#set-musique-auto").checked = config.musique?.auto !== false;
  $("#set-city-input").value = config.ville.nom;
}
$("#set-musique-auto").addEventListener("change", (e) => saveSetting("musique.auto", e.target.checked));
$("#set-accueil").addEventListener("change", (e) => saveSetting("accueil", e.target.checked));
$("#set-sons").addEventListener("change", (e) => saveSetting("sons", e.target.checked));
$("#set-adresse").addEventListener("click", (e) => {
  const v = e.target.dataset.v;
  if (!v) return;
  if (v === "prenom") saveSetting("utilisateur.adresse", "prenom");
  else { saveSetting("utilisateur.adresse", "civilite"); saveSetting("utilisateur.civilite", v); }
  syncSettings(); applyIdentity();
  if (v === "prenom" && !config.utilisateur.prenom) $("#set-prenom").focus();
});
$("#set-prenom").addEventListener("input", (e) => { saveSetting("utilisateur.prenom", e.target.value.trim()); applyIdentity(); });
$("#set-tu").addEventListener("change", (e) => { saveSetting("utilisateur.tutoiement", e.target.checked); applyIdentity(); renderReminders(); });
$("#set-ton").addEventListener("click", (e) => { if (e.target.dataset.v) { saveSetting("ton", e.target.dataset.v); syncSettings(); } });
$("#set-accent").addEventListener("click", (e) => { if (e.target.dataset.v) { saveSetting("accent", e.target.dataset.v); syncSettings(); applyIdentity(); } });
$("#set-voix").addEventListener("change", (e) => { saveSetting("voix", e.target.checked); setVoice(e.target.checked); });
// voix d'homme ou de femme : la nouvelle voix se présente tout de suite
$("#set-genre-voix").addEventListener("click", (e) => {
  const v = e.target.dataset.v;
  if (!v || v === config.genre_voix) return;
  saveSetting("genre_voix", v);
  syncSettings();
  speak(`${V("Bonjour", "Salut")} ${nomAdresse()}, voici ma ${v === "femme" ? "nouvelle " : ""}voix.`, { force: true, onDebut: () => setState("speaking") })
    .finally(() => setState("idle"));
});
$("#set-city").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("#set-city-input").value.trim();
  const note = $("#set-city-note");
  if (!name) return;
  note.textContent = "Recherche…";
  try {
    const r = await fetch(`https://geocoding-api.open-meteo.com/v1/search?${new URLSearchParams({ name, count: 1, language: "fr" })}`);
    const hit = (await r.json()).results?.[0];
    if (!hit) { note.textContent = "Ville introuvable."; return; }
    saveSetting("ville", { nom: hit.name, lat: hit.latitude, lon: hit.longitude, fuseau: hit.timezone });
    note.textContent = `${hit.name}${hit.admin1 ? `, ${hit.admin1}` : ""} (${hit.country}).`;
    tick();
    loadWeather();
  } catch { note.textContent = "Recherche impossible pour le moment."; }
});

/* ================= Démarrage ================= */
applyIdentity();
setVoice(!!config.voix);
tick();
setInterval(tick, 1000);
renderReminders();
renderTodos();
renderSkills();
renderBrief();
// données du premier écran : la barre de chargement attend qu'elles soient là (4 s au plus)
Promise.race([Promise.allSettled([loadWeather(), chargerDonnees(), (playlistChargee = loadPlaylist()), chargerStats()]), sleep(4000)])
  .then(() => {
    preparerAccueil();
    preparerSons();
    window.__chargement?.etape("donnees");
  });
setInterval(loadWeather, 15 * 60 * 1000);
setInterval(chargerDonnees, 60 * 1000);
setInterval(chargerStats, 10 * 1000);

// Fin du préchargeur, quand la barre atteint 100 % : fondu, puis la couronne se remplit, la sphère
// apparaît, les indicateurs se tracent et la musique démarre (si l'option est active).
// « Bonjour, Monsieur. » s'écrit lettre à lettre, comme au clavier, avec un curseur qui clignote
// puis s'efface. Rythme irrégulier, petite pause après la virgule.
async function ecrireSalutation(attente = 0) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const mot = $("#greet-word"), virgule = $("#greet-comma"), nom = $("#greet-name");
  const morceaux = [[mot, mot.textContent], [virgule, virgule.textContent], [nom, nom.textContent]];
  ecritureSalutation = true;
  for (const [el] of morceaux) el.textContent = "";
  const curseur = document.createElement("span");
  curseur.className = "curseur-texte";
  curseur.setAttribute("aria-hidden", "true");
  morceaux[0][0].after(curseur);
  await sleep(attente);             // titre vide pendant que la salutation s'allume
  for (const [el, texte] of morceaux) {
    el.after(curseur);
    for (const c of texte) {
      el.textContent += c;
      if (c.trim()) jouerSon("frappe", { volume: 0.75 + Math.random() * 0.25, hauteur: 0.95 + Math.random() * 0.1 });   // touche, -33 dBFS
      await sleep(c === "," ? 260 : 55 + Math.random() * 55);
    }
  }
  ecritureSalutation = false;
  await sleep(1400);
  curseur.classList.add("fini");
  setTimeout(() => curseur.remove(), 600);
}

// Allumage : barre du haut, salutation, panneaux, onglets et saisie s'allument à tour de rôle.
// rend une promesse tenue quand le dernier élément a fini de s'allumer
function allumerPanneaux() {
  const ordre = [".brand", ".clock", ".top-right", ".greeting", ".col-left .panel", ".tabs",
    ".col-right .pane:not([hidden]) .panel", ".core-state", ".composer"];
  let i = 0, panneaux = 0;
  for (const sel of ordre) {
    for (const el of document.querySelectorAll(sel)) {
      // les panneaux (météo, rappels, tâches, brief) sont espacés de deux pas de plus, et chacun a
      // son petit son HUD (bégaiement de données puis glissando), un cran plus haut que le précédent
      if (el.classList.contains("panel") && !el.closest(".pane[hidden]")) {
        if (panneaux) i += 2;
        jouerSon("element", { volume: 1, hauteur: 1 + 0.04 * panneaux, dans: i * 0.09 });   // crête -30 dBFS dans le fichier
        panneaux++;
      }
      el.classList.add("allumable");
      el.style.setProperty("--i", i++);
    }
  }
  // les panneaux de l'onglet caché : déjà allumés quand on y passe
  document.querySelectorAll(".col-right .pane[hidden] .panel").forEach((el) => el.classList.remove("allumable"));
  document.body.classList.replace("avant-allumage", "allumage");
  const fini = new Promise((ok) => setTimeout(ok, 800 + i * 90));
  // une fois fini, plus d'animation en attente (les panneaux ajoutés ensuite n'en ont pas)
  setTimeout(() => {
    document.body.classList.remove("allumage");
    document.querySelectorAll(".allumable").forEach((el) => { el.classList.remove("allumable"); el.style.removeProperty("--i"); });
  }, 800 + i * 90 + 1000);
  return fini;
}

function finDuChargement() {
  const pl = document.getElementById("preloader");
  if (pl) {
    // retiré à la fin de son animation de sortie (et non sur une minuterie qui pouvait tomber juste
    // après la fin d'une transition, quand Firefox et Zen le réaffichaient un instant)
    pl.addEventListener("animationend", (e) => { if (e.animationName === "pl-sortie") pl.remove(); });
    setTimeout(() => pl.remove(), 1500);           // secours
    pl.classList.add("fini");
  }
  // Un seul mouvement, sans attente : la sphère se déploie pendant que la couronne se remplit
  // (pleine = particules en place), les panneaux s'allument presque aussitôt, la voix part avec
  // la sphère (sa première phrase, courte, est prête pendant le chargement).
  setTimeout(async () => {
    orb.apparaitre(1100);
    jouerSon("sphere", { volume: 1 });          // niveau réglé dans le fichier (-20 dBFS)
    const couronne = chargerCouronne(1100);
    // l'accueil parlé part avec la sphère, la musique en même temps, atténuée sous la voix
    accueilParle();
    lancerMusiqueAuto();
    const panneaux = new Promise((ok) => setTimeout(() => { ok(allumerPanneaux()); ecrireSalutation(3 * 90 + 200); }, 200));   // salutation : 4e élément
    await couronne;
    afficherIndicateurs();
    // tout est chargé (panneaux allumés, indicateurs tracés jusqu'à leurs chiffres, ~1,9 s) : son de fin
    await Promise.all([panneaux, new Promise((ok) => setTimeout(ok, 1900))]);
    jouerSon("fin", { volume: 1 });
  }, 150);
}
if (window.__chargement) {
  requestAnimationFrame(() => requestAnimationFrame(() => window.__chargement.etape("orbe")));
  window.__chargement.quandFini(finDuChargement);
} else {
  finDuChargement();
}
// Double authentification : état dans les réglages, rappel tant qu'elle n'est pas activée
if (LIVE && config.deux_facteurs) {
  const df = config.deux_facteurs;
  $("#field-securite").hidden = false;
  $("#etat-2fa").textContent = df.actif ? "Double authentification activée" : "Double authentification non activée";
  let vu = false;
  try { vu = sessionStorage.getItem("jarvis.rappel2fa") === "vu"; } catch {}
  if (!df.actif && !vu) {
    $("#rappel-2fa-texte").textContent = V("Seul un mot de passe protège votre interface.", "Seul un mot de passe protège ton interface.");
    setTimeout(() => { $("#rappel-2fa").hidden = false; }, 3500);     // après l'allumage
    $("#rappel-2fa-fermer").addEventListener("click", () => {
      $("#rappel-2fa").hidden = true;
      try { sessionStorage.setItem("jarvis.rappel2fa", "vu"); } catch {}
    });
  }
}
if (LIVE) {
  $("#logout").hidden = false;
  $("#logout").addEventListener("click", async () => {
    await fetch("api/deconnexion", { method: "POST" }).catch(() => {});
    location.reload();
  });
}
