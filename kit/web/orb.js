// Orbe de Jarvis, d'après la vidéo de référence (« JARVIS explains how he works ») :
// une sphère creuse faite de particules, plus denses et plus brillantes par amas, reliées
// par de fines liaisons courtes entre voisines. Centre sombre, pas de noyau lumineux.
// Quand Jarvis parle, la coque respire et se déforme, les amas glissent sur la sphère et
// quelques particules s'en détachent ; la taille à l'écran ne change pas ; la sphère
// tourne très lentement sur elle-même, comme une planète.
import * as THREE from "three";

const NOISE = /* glsl */ `
vec3 mod289(vec3 x){return x-floor(x*(1./289.))*289.;}
vec4 mod289(vec4 x){return x-floor(x*(1./289.))*289.;}
vec4 permute(vec4 x){return mod289(((x*34.)+1.)*x);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-.85373472095314*r;}
float snoise(vec3 v){
  const vec2 C=vec2(1./6.,1./3.);const vec4 D=vec4(0.,.5,1.,2.);
  vec3 i=floor(v+dot(v,C.yyy));vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz);vec3 l=1.-g;vec3 i1=min(g.xyz,l.zxy);vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx;vec3 x2=x0-i2+C.yyy;vec3 x3=x0-D.yyy;
  i=mod289(i);
  vec4 p=permute(permute(permute(i.z+vec4(0.,i1.z,i2.z,1.))+i.y+vec4(0.,i1.y,i2.y,1.))+i.x+vec4(0.,i1.x,i2.x,1.));
  float n_=.142857142857;vec3 ns=n_*D.wyz-D.xzx;
  vec4 j=p-49.*floor(p*ns.z*ns.z);vec4 x_=floor(j*ns.z);vec4 y_=floor(j-7.*x_);
  vec4 x=x_*ns.x+ns.yyyy;vec4 y=y_*ns.x+ns.yyyy;vec4 h=1.-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy);vec4 b1=vec4(x.zw,y.zw);
  vec4 s0=floor(b0)*2.+1.;vec4 s1=floor(b1)*2.+1.;vec4 sh=-step(h,vec4(0.));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x);vec3 p1=vec3(a0.zw,h.y);vec3 p2=vec3(a1.xy,h.z);vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
  vec4 m=max(.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.);m=m*m;
  return 42.*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}
uniform float uTime;
uniform float uAmp;     // relief lent de la coque
uniform float uSlide;   // glissement des particules sur la coque
uniform float uBreath;  // respiration et bosses de la coque (parole)
uniform float uPulse;   // énergie lissée de la voix ou du texte
uniform float uBeat;    // pulsation rythmique pendant la parole (0 à 1, battements)
uniform float uCamZ;
uniform float uIntro;   // apparition de la sphère au chargement (0 = repliée et invisible, 1 = en place)
// Position sur la coque : ne dépend que de la position d'origine, pour que points et
// liaisons restent accrochés ensemble.
vec3 shell(vec3 p){
  float t = uTime;
  // glissement tangent : chaque zone file dans sa propre direction le long de la sphère
  vec3 q = p * 1.6;
  vec3 f = vec3(snoise(q + vec3(t * 0.07, 0., 4.2)),
                snoise(q + vec3(9.1, t * 0.07, 0.)),
                snoise(q + vec3(0., 2.7, t * 0.07)));
  f -= p * dot(f, p);
  vec3 s = normalize(p + f * uSlide);
  // relief : lent au repos, bosses qui suivent la voix pendant la parole
  float n1 = snoise(s * 1.3 + vec3(0., t * 0.05, 0.));
  float n2 = snoise(s * 2.6 + vec3(t * 0.22, 0., t * 0.17));
  float r = 1. + uAmp * n1 + uBreath * (0.35 + 0.65 * n2) * (0.6 + 0.8 * uPulse);
  r *= 1. + uBeat * 0.022;                 // pulsation : la coque se gonfle à peine
  r *= 0.3 + 0.7 * uIntro;                 // apparition : la coque se déploie depuis le centre
  return s * r;
}
// Amas qui vivent : la luminosité suit un champ lent, ajouté aux amas de départ.
float clumps(vec3 p, float w){
  float n = snoise(p * 2.1 + vec3(uTime * 0.06, -uTime * 0.04, 0.));
  return clamp(w * 0.75 + 0.45 * smoothstep(-0.1, 0.75, n), 0., 1.);
}
float depthFade(vec4 mv){ return mix(0.16, 1., smoothstep(-uCamZ - 1.1, -uCamZ + 1.1, mv.z)); }
// Force de la souris : les particules proches du pointeur s'écartent à peine (dans le plan
// de l'écran). Très léger : l'essentiel de l'effet vient des fils tendus vers le pointeur.
// Calcul en coordonnées du monde.
uniform vec3 uSouris;   // point visé par la souris, sur le plan de la sphère
uniform float uForce;   // 0 = souris absente, 1 = force pleine
vec4 vue(vec3 p){
  vec4 w = modelMatrix * vec4(p, 1.);
  vec2 d = w.xy - uSouris.xy;
  float r = length(d);
  float k = uForce * exp(-(r * r) / 0.16);             // portée ~0,4 rayon de sphère
  w.xy += (d / max(r, 1e-3)) * k * 0.015;
  return viewMatrix * w;
}
// errance individuelle des particules (partagée par les points et les fils du pointeur)
vec3 errance(vec3 p, float seed){
  float ts = uTime * (0.06 + seed * 0.08);
  return p + vec3(snoise(vec3(seed * 91.7, ts, 3.1)),
                  snoise(vec3(7.3, seed * 53.9, ts)),
                  snoise(vec3(ts, 19.4, seed * 37.3))) * (0.012 + uSlide * 0.08);
}
`;

const pointsVert = /* glsl */ `
${NOISE}
attribute float aSize;
attribute float aSeed;
attribute float aW;
uniform float uPixel;
uniform float uFlow;
uniform float uSoft;    // 1 = couche de halo (gros points doux)
uniform float uHaloTaille;   // couches douces : taille et éclat des points
uniform float uHaloEclat;
varying float vAlpha;
varying float vWhite;
void main(){
  vec3 p = errance(shell(position), aSeed);   // errance individuelle, légère
  // pendant la parole, une particule sur quatre se détache, file vers l'extérieur et s'éteint
  float ph = fract(uTime * (0.09 + aSeed * 0.09) + aSeed * 7.);
  float fly = uFlow * step(0.75, aSeed);
  p *= 1. + fly * ph * 0.85;
  vec4 mv = vue(p);
  gl_Position = projectionMatrix * mv;
  float c = clumps(position, aW);
  float tw = 0.85 + 0.15 * sin(uTime * (0.3 + aSeed * 0.4) + aSeed * 40.);
  vAlpha = depthFade(mv) * tw * (0.3 + 0.95 * c) * (1. - fly * smoothstep(0.3, 1., ph));
  vAlpha *= mix(1., uHaloEclat * mix(c * c, 1., step(uHaloTaille, 3.)), uSoft);
  vWhite = step(0.86, aSeed) * (1. - uSoft);
  vAlpha *= 1. + uBeat * 0.14;             // léger regain d'éclat à chaque pulsation
  vAlpha *= smoothstep(aSeed * 0.6, aSeed * 0.6 + 0.4, uIntro);   // les particules s'allument en cascade
  float size = aSize * (0.75 + 0.9 * c) * (1. + uPulse * 0.25 + uBeat * 0.06);
  gl_PointSize = mix(size, size * uHaloTaille, uSoft) * uPixel * (uCamZ / -mv.z);
}`;

const pointsFrag = /* glsl */ `
uniform vec3 uColor;
varying float vAlpha;
varying float vWhite;
void main(){
  float d = length(gl_PointCoord - .5);
  float a = smoothstep(.5, 0., d);
  a *= a;
  vec3 col = mix(uColor * (1.35 + a), vec3(1.), vWhite * 0.7);
  gl_FragColor = vec4(col, a * vAlpha);
}`;

const linesVert = /* glsl */ `
${NOISE}
attribute float aW;
varying float vAlpha;
void main(){
  vec3 p = shell(position);
  vec4 mv = vue(p);
  gl_Position = projectionMatrix * mv;
  vAlpha = depthFade(mv) * (0.15 + 0.85 * clumps(position, aW)) * smoothstep(0.5, 1., uIntro);
}`;

// Fils du pointeur (comme un fond de particules interactif) : de fins traits relient le
// pointeur aux particules proches, plus pâles avec la distance. Chaque fil a ses deux
// sommets sur la même particule ; aBout = 0 pour le bout posé sur le pointeur.
const filsVert = /* glsl */ `
${NOISE}
attribute float aSeed;
attribute float aBout;
uniform float uPortee;
uniform float uFlow;
varying float vAlpha;
varying float vBout;
void main(){
  vBout = aBout;
  vec3 p = errance(shell(position), aSeed);
  vec4 w = modelMatrix * vec4(p, 1.);
  float r = length(w.xy - uSouris.xy);
  float a = 1. - smoothstep(0., uPortee, r);
  vec4 particule = vue(p);
  vec4 mv = aBout > 0.5 ? particule : viewMatrix * vec4(uSouris, 1.);
  gl_Position = projectionMatrix * mv;
  // nombre de fils variable : un seuil commun monte et descend lentement (parfois deux ou
  // trois fils, parfois une vingtaine) et chaque fil s'allume ou s'éteint en long fondu
  // (plusieurs secondes), pour éviter tout clignotement
  float densite = 0.5 + 0.5 * snoise(vec3(uTime * 0.012, 11.3, 2.7));
  float seuil = mix(0.78, 0.3, densite);
  float tirage = 0.5 + 0.5 * snoise(vec3(aSeed * 37.1, uTime * 0.025, 5.9));
  float allume = smoothstep(seuil - 0.15, seuil + 0.15, tirage);
  vAlpha = uForce * a * allume * depthFade(particule) * (1. - min(1., uFlow)) * uIntro;
}`;

const filsFrag = /* glsl */ `
uniform vec3 uColor;
varying float vAlpha;
varying float vBout;
// plus lumineux près du pointeur (le point de convergence reste vif), discret vers la particule
void main(){ gl_FragColor = vec4(uColor, mix(0.5, 0.1, sqrt(vBout)) * vAlpha); }`;

const linesFrag = /* glsl */ `
uniform vec3 uColor;
uniform float uLine;
varying float vAlpha;
void main(){ gl_FragColor = vec4(uColor, uLine * vAlpha); }`;

// Cibles par état ; les valeurs glissent en douceur de l'une à l'autre.
const STATES = {
  idle:      { amp: 0.05, slide: 0.05, breath: 0.00, flow: 0.0, line: 0.13, light: 0.00 },
  listening: { amp: 0.07, slide: 0.08, breath: 0.05, flow: 0.0, line: 0.15, light: 0.08 },
  thinking:  { amp: 0.05, slide: 0.16, breath: 0.02, flow: 0.0, line: 0.17, light: 0.04 },
  speaking:  { amp: 0.09, slide: 0.32, breath: 0.27, flow: 1.0, line: 0.10, light: 0.12 },
};

const WHITE = new THREE.Color(1, 1, 1);

// Particules sur la sphère, plus nombreuses dans quelques amas (comme la référence,
// où des plaques brillantes alternent avec des zones clairsemées).
function makeShell(n) {
  const centres = Array.from({ length: 9 }, () => ({
    c: new THREE.Vector3().randomDirection(),
    w: 0.25 + Math.random() * 0.4,          // largeur angulaire de l'amas (rad)
  }));
  const poids = (v) => centres.reduce((m, k) => {
    const a = Math.acos(Math.min(1, Math.max(-1, v.dot(k.c))));
    return Math.max(m, Math.exp(-(a * a) / (k.w * k.w)));
  }, 0);
  const pts = [], ws = [];
  const v = new THREE.Vector3();
  while (pts.length < n) {
    v.randomDirection();
    const w = poids(v);
    if (Math.random() < 0.22 + 0.78 * w) {
      pts.push(v.clone());
      ws.push(w);
    }
  }
  return { pts, ws };
}

export function createOrb(canvas) {
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const small = Math.min(innerWidth, innerHeight) < 700;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 0);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 80);
  camera.position.set(0, 0, 6);

  const uniforms = {
    uTime: { value: 0 },
    uAmp: { value: STATES.idle.amp },
    uSlide: { value: STATES.idle.slide },
    uBreath: { value: 0 },
    uPulse: { value: 0 },
    uBeat: { value: 0 },
    uFlow: { value: 0 },
    uLine: { value: STATES.idle.line },
    uCamZ: { value: 6 },
    uPixel: { value: renderer.getPixelRatio() },
    uColor: { value: new THREE.Color(0x5fe1ff) },
    uIntro: { value: 0 },
    uSouris: { value: new THREE.Vector3(0, 0, 0) },
    uForce: { value: 0 },
  };
  const accent = new THREE.Color(0x5fe1ff);

  const group = new THREE.Group();
  group.rotation.set(0.3, 0, 0.1);
  scene.add(group);

  // --- Particules de la coque ---
  const N = small ? 2800 : 5000;
  const { pts, ws } = makeShell(N);
  const pos = new Float32Array(N * 3), size = new Float32Array(N), seed = new Float32Array(N), w = new Float32Array(N);
  pts.forEach((p, i) => {
    pos.set([p.x, p.y, p.z], i * 3);
    size[i] = 1.1 + Math.pow(Math.random(), 5) * 3.6;
    seed[i] = Math.random();
    w[i] = ws[i];
  });
  const pGeo = new THREE.BufferGeometry();
  pGeo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  pGeo.setAttribute("aSize", new THREE.BufferAttribute(size, 1));
  pGeo.setAttribute("aSeed", new THREE.BufferAttribute(seed, 1));
  pGeo.setAttribute("aW", new THREE.BufferAttribute(w, 1));
  const common = { transparent: true, depthWrite: false, blending: THREE.AdditiveBlending };
  group.add(new THREE.Points(pGeo, new THREE.ShaderMaterial({
    ...common, uniforms: { ...uniforms, uSoft: { value: 0 }, uHaloTaille: { value: 1 }, uHaloEclat: { value: 1 } }, vertexShader: pointsVert, fragmentShader: pointsFrag,
  })));
  // halo doux des amas, qui donne l'aspect de nébuleuse
  group.add(new THREE.Points(pGeo, new THREE.ShaderMaterial({
    ...common, uniforms: { ...uniforms, uSoft: { value: 1 }, uHaloTaille: { value: 6 }, uHaloEclat: { value: 0.11 } }, vertexShader: pointsVert, fragmentShader: pointsFrag,
  })));
  // lueur serrée autour de chaque particule : remplace le drop-shadow CSS du canvas, qui faisait
  // saturer la carte graphique (recalculé à chaque image sur toute la surface) et caler l'affichage
  group.add(new THREE.Points(pGeo, new THREE.ShaderMaterial({
    ...common, uniforms: { ...uniforms, uSoft: { value: 1 }, uHaloTaille: { value: 2.4 }, uHaloEclat: { value: 0.22 } }, vertexShader: pointsVert, fragmentShader: pointsFrag,
  })));

  // --- Liaisons courtes entre voisines (plexus) ---
  const lp = [], lw = [];
  // plus de particules : liaisons plus courtes et plus rares pour garder un réseau fin
  const maxD = small ? 0.12 : 0.095;
  for (let i = 0; i < N; i++) {
    let links = 0;
    for (let j = i + 1; j < N && links < 2; j++) {
      if (pts[i].distanceToSquared(pts[j]) < maxD * maxD && Math.random() < 0.38) {
        lp.push(pts[i].x, pts[i].y, pts[i].z, pts[j].x, pts[j].y, pts[j].z);
        lw.push(ws[i], ws[j]);
        links++;
      }
    }
  }
  const lGeo = new THREE.BufferGeometry();
  lGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(lp), 3));
  lGeo.setAttribute("aW", new THREE.BufferAttribute(new Float32Array(lw), 1));
  group.add(new THREE.LineSegments(lGeo, new THREE.ShaderMaterial({
    ...common, uniforms, vertexShader: linesVert, fragmentShader: linesFrag,
  })));

  // --- Fils du pointeur : un échantillon de particules qui ne s'envolent pas (aSeed < 0,75),
  // environ une sur douze ; seule une partie est allumée à un instant donné ---
  const fp = [], fs = [], fb = [];
  for (let i = 0; i < N; i++) {
    if (seed[i] >= 0.75 || Math.random() > 0.08) continue;
    const p = pts[i];
    fp.push(p.x, p.y, p.z, p.x, p.y, p.z);
    fs.push(seed[i], seed[i]);
    fb.push(0, 1);
  }
  const fGeo = new THREE.BufferGeometry();
  fGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(fp), 3));
  fGeo.setAttribute("aSeed", new THREE.BufferAttribute(new Float32Array(fs), 1));
  fGeo.setAttribute("aBout", new THREE.BufferAttribute(new Float32Array(fb), 1));
  const fils = new THREE.LineSegments(fGeo, new THREE.ShaderMaterial({
    ...common, uniforms: { ...uniforms, uPortee: { value: 0.8 } }, vertexShader: filsVert, fragmentShader: filsFrag,
  }));
  fils.frustumCulled = false;
  group.add(fils);

  // --- Lumières : cœur (seulement quand l'assistant parle) et léger halo d'ensemble ---
  const texLueur = (() => {
    const c = document.createElement("canvas");
    c.width = c.height = 256;
    const g = c.getContext("2d");
    const d = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    d.addColorStop(0, "rgba(255,255,255,1)");
    d.addColorStop(0.1, "rgba(235,250,255,0.85)");
    d.addColorStop(0.32, "rgba(150,220,255,0.28)");
    d.addColorStop(1, "rgba(80,170,255,0)");
    g.fillStyle = d;
    g.fillRect(0, 0, 256, 256);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  })();
  const coeur = new THREE.Sprite(new THREE.SpriteMaterial({
    map: texLueur, transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending, opacity: 0 }));
  coeur.scale.setScalar(0.6);
  scene.add(coeur);
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({
    map: texLueur, transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending, opacity: 0 }));
  halo.scale.setScalar(3.4);
  scene.add(halo);
  // point lumineux sous le pointeur, où convergent les fils : reste vif même quand peu de fils sont allumés
  const pointeur = new THREE.Sprite(new THREE.SpriteMaterial({
    map: texLueur, transparent: true, depthWrite: false, depthTest: false, blending: THREE.AdditiveBlending, opacity: 0 }));
  pointeur.scale.setScalar(0.09);
  scene.add(pointeur);

  renderer.compile(scene, camera);

  // --- États et énergie ---
  let state = "idle";
  let target = STATES.idle;
  let pulseTarget = 0, kickEnergy = 0, pulse = 0, beatPhase = 0;
  // Trois arcs sur le même cercle (80°, 60°, 28°, longueurs fixées dans styles.css).
  // L'ensemble tourne et se balance ; chaque arc ajoute un petit écart qui lui est propre.
  // Au repos, les trois écarts font 64° ; chaque arc s'écarte au plus de JEU de sa place :
  // deux voisins se rapprochent au plus de 2 × JEU, il reste toujours ≥ 44° entre eux.
  const JEU = 10;
  const ARCS = [
    { sel: ".hud-arc.a1", long: 80, centre: 0, f: 0.9, ph: 0 },
    { sel: ".hud-arc.a3", long: 60, centre: 134, f: 1.3, ph: 2.1 },
    { sel: ".hud-arc.a4", long: 28, centre: 242, f: 1.7, ph: 4.4 },
  ].map((a) => ({ ...a, el: canvas.parentElement?.querySelector(a.sel) }));
  let phG = 0, phA = 0, tour = 0;
  const ARC_SPEED = { idle: 0.22, listening: 0.55, thinking: 0.6, speaking: 1 };
  // cercle pointillé et cercle gradué : rotations continues, à des vitesses différentes et en sens contraires
  const pointille = canvas.parentElement?.querySelector(".hud-arc.a2");
  const gradue = canvas.parentElement?.querySelector(".hud-ticks");
  let angPointille = 0, angGradue = 0;
  // apparition au chargement
  let intro = { de: 0, a: 0, t0: 0, duree: 1 };
  let tempsReel = 0;
  const TOUR = (Math.PI * 2) / 120;   // vitesse de rotation de la sphère (rad/s)
  const tmpColor = new THREE.Color();

  function setState(s) { if (STATES[s]) { state = s; target = STATES[s]; } }
  function setAccent(hex) { accent.set(hex); }
  function setLevel(v) { pulseTarget = Math.max(0, Math.min(1, v)); }
  // un mot, un bloc de texte : l'énergie monte puis s'éteint d'elle-même, sans saut
  // chaque mot ajoute un peu d'énergie au lieu de la fixer : la courbe reste continue
  function kick(v = 0.6) { kickEnergy = Math.min(0.9, kickEnergy + Math.min(1, v) * 0.25); }

  // Taille fixe à l'écran (calée sur la fenêtre, pas sur le cadre) : pas de dézoom
  // quand la discussion s'ouvre.
  function resize() {
    const { clientWidth: cw, clientHeight: ch } = canvas;
    if (!cw || !ch) return;
    renderer.setSize(cw, ch, false);
    camera.aspect = cw / ch;
    // sphère de repos à 80 % de l'ancienne taille, cadran inchangé : plus de place pour l'éclatement
    const base = Math.max(80, Math.min(innerHeight * 0.15, innerWidth * 0.24, 160));
    const rayonPx = base * 0.8;
    const demi = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    camera.position.z = (ch / 2) / (demi * rayonPx);
    uniforms.uCamZ.value = camera.position.z;
    camera.updateProjectionMatrix();
    canvas.parentElement?.style.setProperty("--hud", `${Math.round(base * 3.0)}px`);
  }
  new ResizeObserver(resize).observe(canvas);
  addEventListener("resize", resize);
  resize();

  // Souris : le point visé se pose sur la face visible de la sphère, comme si l'on se
  // promenait sur une planète. Hors de la sphère, il reste collé à son bord, jamais au-delà.
  const rayon = new THREE.Raycaster(), ndc = new THREE.Vector2(), plan = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
  const globe = new THREE.Sphere(new THREE.Vector3(), 0.95);
  const viseCible = new THREE.Vector3(), vise = new THREE.Vector3();
  let forceCible = 0;
  canvas.addEventListener("pointermove", (e) => {
    const r = canvas.getBoundingClientRect();
    ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    rayon.setFromCamera(ndc, camera);
    if (rayon.ray.intersectSphere(globe, viseCible)) { forceCible = 1; return; }
    if (rayon.ray.intersectPlane(plan, viseCible)) {
      forceCible = viseCible.length() < 1.6 ? 1 : 0;
      viseCible.setLength(globe.radius);          // bord de la sphère, côté du pointeur
    }
  });
  canvas.addEventListener("pointerleave", () => { forceCible = 0; });

  const clock = new THREE.Clock();
  let running = true;
  document.addEventListener("visibilitychange", () => {
    running = !document.hidden;
    if (running) { clock.getDelta(); loop(); }
  });

  const ease = (cur, to, dt, rate) => cur + (to - cur) * (1 - Math.exp(-dt * rate));

  // Ressort amorti critique : départ et arrivée en douceur (courbe en S), sans rebond.
  // Un simple lissage exponentiel part trop sèchement : c'était la saccade du retour.
  // « monte » règle la vitesse de l'éclatement, « descend » celle du retour au calme.
  const springs = {};
  function spring(name, to, dt, monte, descend) {
    const s = (springs[name] ??= { x: to, v: 0 });
    const k = to > s.x ? monte : descend;          // raideur : 2π / k ≈ durée du passage
    s.v += ((to - s.x) * k * k - 2 * k * s.v) * dt;
    s.x += s.v * dt;
    return s.x;
  }

  function loop() {
    if (!running) return;
    requestAnimationFrame(loop);
    const dt = Math.min(clock.getDelta(), 0.05);
    const u = uniforms;
    u.uTime.value += dt * (reduced ? 0.3 : 2.5);   // tempo général : 2,5 fois le rythme lent d'origine

    // énergie de la voix : éclatement en ~0,35 s, retour en ~1,2 s, courbes douces
    kickEnergy = ease(kickEnergy, 0, dt, 1.4);
    const want = Math.max(pulseTarget, kickEnergy);
    pulse = Math.max(0, spring("pulse", want, dt, 9, 3.2));
    u.uPulse.value = pulse * (reduced ? 0.4 : 1);

    // états : l'éclatement part vite (~0,5 s), le retour au calme glisse (~1,5 à 2 s)
    u.uAmp.value = spring("amp", target.amp, dt, 6, 3);
    u.uSlide.value = spring("slide", target.slide, dt, 6, 2.6);
    u.uBreath.value = Math.max(0, spring("breath", target.breath, dt, 8, 2.6));
    u.uFlow.value = Math.max(0, spring("flow", target.flow, dt, 6, 2.4));
    u.uLine.value = Math.max(0, spring("line", target.line, dt, 4, 4));

    // Arcs : vitesse lissée selon l'état. L'ensemble avance lentement (~2°/s au repos, ~9°/s
    // pendant la parole) et se balance ; chaque arc respire à son rythme, dans la limite de JEU.
    const v = spring("arcs", ARC_SPEED[state] ?? 0.22, dt, 2.5, 1.5) * (reduced ? 0.3 : 1);
    phG += dt * v * 1.15;
    phA += dt * v;
    tour = (tour + dt * v * 9) % 360;
    const base = tour + Math.sin(phG) * 30;
    // (pivot au centre du cadran : transform-origin 200px 200px dans styles.css ; un tiret
    // commence à 3 h, d'où le retrait de la demi-longueur pour placer le centre de l'arc)
    for (const a of ARCS) {
      if (!a.el) continue;
      const ecart = JEU * (0.7 * Math.sin(phA * a.f + a.ph) + 0.3 * Math.sin(phA * a.f * 2.3 + a.ph * 1.7));
      a.el.style.transform = `rotate(${(base + a.centre + ecart - a.long / 2).toFixed(2)}deg)`;
    }
    angPointille = (angPointille + dt * v * 16) % 360;     // ~3,5°/s au repos, 16°/s en parole
    angGradue = (angGradue - dt * v * 4) % 360;            // ~1°/s au repos, 4°/s en parole, sens inverse
    if (pointille) pointille.style.transform = `rotate(${angPointille.toFixed(2)}deg)`;
    if (gradue) gradue.style.transform = `rotate(${angGradue.toFixed(2)}deg)`;

    // apparition (courbe douce) et lumières
    tempsReel += dt;
    // la cible de la souris est suivie avec un léger retard, la force monte et retombe en douceur
    vise.lerp(viseCible, 1 - Math.exp(-dt * 8));
    u.uSouris.value.copy(vise);
    u.uForce.value = Math.max(0, spring("souris", reduced ? 0 : forceCible, dt, 5, 2.5));
    if (intro.a !== intro.de) {
      const k = Math.min(1, (tempsReel - intro.t0) / intro.duree);
      u.uIntro.value = intro.de + (intro.a - intro.de) * (1 - Math.pow(1 - k, 3));
      if (k >= 1) intro.de = intro.a;
    }
    const parle = Math.min(1, u.uFlow.value);              // 1 pendant la réponse, retombe en douceur
    const bat = 0.5 + 0.5 * Math.sin(tempsReel * 2.6);     // battement doux du cœur
    coeur.material.opacity = parle * (0.55 + 0.3 * bat) * u.uIntro.value;
    coeur.scale.setScalar(0.5 * (1 + 0.1 * bat + pulse * 0.15));
    coeur.material.color.copy(u.uColor.value).lerp(WHITE, 0.55);
    halo.material.opacity = (0.07 + 0.04 * parle) * u.uIntro.value;
    halo.material.color.copy(u.uColor.value);
    pointeur.position.copy(vise);
    pointeur.material.opacity = u.uForce.value * 0.6 * (1 - parle) * u.uIntro.value;
    pointeur.material.color.copy(u.uColor.value).lerp(WHITE, 0.4);

    // Pulsation subtile : une onde douce toutes les 2 s environ, seulement pendant l'échange.
    beatPhase = (beatPhase + dt * 0.62) % 1;
    const d = beatPhase - 0.5;
    const onde = Math.exp(-(d * d) / (2 * 0.13 * 0.13));
    u.uBeat.value = onde * Math.min(1, u.uFlow.value) * (reduced ? 0.3 : 1);
    tmpColor.copy(accent).lerp(WHITE, target.light);
    u.uColor.value.lerp(tmpColor, 1 - Math.exp(-dt * 1.2));
    // rotation complète très lente, toujours dans le même sens, comme une planète (un tour en
    // ~2 min, en temps réel, quel que soit l'état) ; l'axe penche à peine et oscille doucement
    const tt = u.uTime.value;
    group.rotation.y = (group.rotation.y + dt * TOUR * (reduced ? 0.5 : 1)) % (Math.PI * 2);
    group.rotation.x = 0.3 + Math.sin(tt * 0.08) * 0.07;

    renderer.render(scene, camera);
  }
  loop();

  // la sphère se déploie depuis le centre et ses particules s'allument (appelé après le préchargeur)
  function apparaitre(duree = 1600) {
    intro = { de: u0(), a: 1, t0: tempsReel, duree: Math.max(0.1, duree / 1000) };
  }
  const u0 = () => uniforms.uIntro.value;

  return { setState, setLevel, kick, setAccent, apparaitre, get state() { return state; } };
}
