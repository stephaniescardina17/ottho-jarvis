"""Sons HUD de l'interface, synthétisés de zéro (aucun échantillon tiers).

python fabrication_hud.py DOSSIER [SPHERE.wav]
Écrit element.wav (apparition d'un panneau), tic.wav (barre de chargement), complet.wav (100 %),
frappe.wav (une lettre de la salutation) et, si SPHERE.wav est donné, ecoute_hud.wav : la séquence
réelle (préchargeur, sphère, panneaux, salutation écrite) aux vrais instants de l'interface.
"""
import sys, numpy as np, soundfile as sf
SR = 44100; OUT = sys.argv[1]; SPHERE = sys.argv[2] if len(sys.argv) > 2 else None
rng = np.random.default_rng(23)
t_ = lambda d: np.arange(int(d * SR)) / SR
ph = lambda f: 2 * np.pi * np.cumsum(f) / SR
def env(n, a, r, c=3.0):
    e = np.ones(n); na, nr = max(1, int(a*SR)), max(1, int(r*SR))
    e[:na] = np.linspace(0, 1, na); e[-nr:] *= np.linspace(1, 0, nr) ** c; return e
def passe_haut(x, fc):
    k = np.exp(-2*np.pi*fc/SR); y = np.empty_like(x); p = px = 0.0
    for i, v in enumerate(x): p = k*(p + v - px); px = v; y[i] = p
    return y
def crete(x, db): return x / max(1e-9, np.abs(x).max()) * 10 ** (db / 20)
def mix(x, son, at, g=1.0):
    i = int(at*SR)
    if i < len(x): x[i:i+len(son)] += son[:len(x)-i] * g
    return x
def ton(f, d, fm=0.0, ratio=2.0, a=0.001, r=None):
    t = t_(d); f = np.full(len(t), f) if np.isscalar(f) else f
    return np.sin(ph(f) + fm*np.sin(ph(f*ratio))) * env(len(t), a, r or d*0.9)
def glisse(f0, f1, d, **k):
    t = t_(d); return ton(f0 * (f1/f0) ** (t/d), d, **k)

# Élément : bégaiement de données (grains FM hachés, aigus, qui s'éteignent), puis glissando qui descend
el = np.zeros(int(0.55*SR)); at = 0.0
while at < 0.24:
    g = ton(rng.uniform(2500, 9000), 0.016, fm=rng.uniform(0.5, 2.5), ratio=rng.choice([1.5, 2.0, 3.0]), r=0.006)
    g += passe_haut(rng.standard_normal(len(g)), 4000) * env(len(g), 0.001, 0.01) * 0.25
    mix(el, g, at, 1 - at * 2.5); at += rng.choice([0.022, 0.026, 0.03])
mix(el, glisse(6800, 1100, 0.09, fm=0.4, r=0.07), 0.25, 0.9)
for _ in range(5):
    mix(el, ton(rng.uniform(5000, 10000), 0.012, fm=1.0, r=0.01), rng.uniform(0.27, 0.42), 0.35)
element = crete(passe_haut(el, 900), -30)
# Tic de la barre de chargement : souffle très court + petite note aiguë (~9,8 kHz)
tic = ton(9800, 0.03, r=0.028) * 0.6 + passe_haut(rng.standard_normal(int(0.03*SR)), 3000) * env(int(0.03*SR), 0.0005, 0.02, 4) * 0.5
tic = crete(tic, -36)
# 100 % : deux glissandos croisés, courts et doux
co = np.zeros(int(0.3*SR)); mix(co, glisse(4200, 8400, 0.12, fm=0.3, r=0.1), 0); mix(co, glisse(8400, 4600, 0.16, fm=0.3, r=0.14), 0.07, 0.7)
complet = crete(passe_haut(co, 900), -33)
# Frappe : clic de touche numérique (~2,7 kHz + harmonique), très court
fr = ton(2700, 0.028, r=0.026); mix(fr, ton(7400, 0.012, r=0.011), 0, 0.35)
fr += passe_haut(rng.standard_normal(len(fr)), 5000) * env(len(fr), 0.0005, 0.008, 4) * 0.3
frappe = crete(fr, -33)
for nom, x in [("element", element), ("tic", tic), ("complet", complet), ("frappe", frappe)]:
    sf.write(f"{OUT}/{nom}.wav", x.astype(np.float32), SR)

if SPHERE:   # séquence réelle, mêmes instants que l'interface
    sph = sf.read(SPHERE)[0]; sph = sph.mean(axis=1) if sph.ndim > 1 else sph
    def repitch(x, r): return np.interp(np.arange(0, len(x), r), np.arange(len(x)), x)
    x = np.zeros(int(5.5*SR)); T = 0.0
    for k in range(16): mix(x, repitch(tic, rng.uniform(0.97, 1.03)), T + k * 0.095)   # préchargeur ~1,5 s
    T = 16 * 0.095; mix(x, complet, T)                                                  # 100 %
    S0 = T + 0.22 + 0.15; mix(x, sph, S0)                                               # sphère
    for k, d in enumerate((0.36, 0.72, 0.99, 1.26)): mix(x, repitch(element, 1 + 0.04*k), S0 + 0.2 + d)
    at = S0 + 0.2 + 0.47                                                                 # salutation écrite
    for c in "Bonjour, Monsieur":
        if c != " ": mix(x, repitch(frappe, rng.uniform(0.95, 1.05)), at, rng.uniform(0.75, 1))
        at += 0.26 if c == "," else rng.uniform(0.055, 0.11)
    sf.write(f"{OUT}/ecoute_hud.wav", x.astype(np.float32), SR)
print("ok")
