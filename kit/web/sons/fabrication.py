"""Sons d'interface futuristes et discrets, synthétisés de zéro (aucun échantillon)."""
import sys, numpy as np, soundfile as sf
SR = 44100; OUT = sys.argv[1]; rng = np.random.default_rng(7)
t_ = lambda d: np.arange(int(d * SR)) / SR
def env(n, a, r, courbe=3.0):
    e = np.ones(n); na, nr = max(1, int(a*SR)), max(1, int(r*SR))
    e[:na] = np.linspace(0, 1, na) ** 2; e[-nr:] *= np.linspace(1, 0, nr) ** courbe
    return e
def ph(f):  # phase d'une fréquence variable
    return 2 * np.pi * np.cumsum(f) / SR
def echo(x, d=0.11, g=0.28, n=4):  # petit écho numérique, comme un espace de verre
    y = np.concatenate([x, np.zeros(int(d * SR * n))])
    for k in range(1, n + 1):
        o = int(d * SR * k); y[o:o+len(x)] += x * (g ** k)
    return y
def passe_haut(x, fc):
    k = np.exp(-2*np.pi*fc/SR); y = np.empty_like(x); p = px = 0.0
    for i, v in enumerate(x): p = k*(p + v - px); px = v; y[i] = p
    return y
def passe_bas(x, fc):
    a = 1 - np.exp(-2*np.pi*fc/SR); y = np.empty_like(x); p = 0.0
    for i, v in enumerate(x): p += a*(v - p); y[i] = p
    return y
def niveau(x, dbfs):  # crête fixée : discret
    return x / max(1e-9, np.abs(x).max()) * 10 ** (dbfs / 20)
def blip(f0, f1, d, fm=0.0, ratio=2.0, a=0.003, r=None):
    t = t_(d); f = f0 * (f1 / f0) ** (t / d)
    mod = fm * np.sin(ph(f * ratio)); x = np.sin(ph(f) + mod)
    return x * env(len(t), a, r or d * 0.85)
def scintille(d, fmin=3000, fmax=7000, n=14):
    t = t_(d); x = np.zeros(len(t))
    for _ in range(n):
        f = rng.uniform(fmin, fmax); o = rng.uniform(0, d * 0.7); l = rng.uniform(0.03, 0.09)
        i = int(o * SR); b = blip(f, f * rng.uniform(0.97, 1.03), l, fm=0.5)
        x[i:i+len(b)] += b[:len(x)-i] * rng.uniform(0.3, 1)
    return x
def sauver(nom, x, dbfs):
    x = niveau(passe_haut(x, 150), dbfs); x[-200:] *= np.linspace(1, 0, 200)
    sf.write(f"{OUT}/{nom}.wav", x.astype(np.float32), SR)

# --- Allumage de la sphère (~1,2 à 1,8 s), crête -20 dBFS ---
# S1 balayage holographique : glissando qui monte, voile de bruit filtré, scintillement au sommet
d = 1.3; t = t_(d); f = 180 * (2400/180) ** ((t/d) ** 1.6)
s1 = np.sin(ph(f)) * env(len(t), 0.25, 0.35) * 0.5
air = passe_bas(passe_haut(rng.standard_normal(len(t)), 2000), 6000) * env(len(t), 0.6, 0.5) * 0.12
s1 = s1 + air; s1 = np.concatenate([s1, np.zeros(int(0.5*SR))]); sc = scintille(0.6)
o = int(0.95*SR); s1[o:o+len(sc)] += sc * 0.35
sauver("sphere_1_balayage", echo(s1, 0.09, 0.25), -20)
# S2 séquence de données : six bips FM qui montent (gamme pentatonique), puis une note tenue très douce
notes = [1046, 1318, 1568, 1760, 2093, 2637]; s2 = np.zeros(int(1.6*SR))
for k, fq in enumerate(notes):
    b = blip(fq, fq * 1.01, 0.07, fm=1.2, ratio=3.0); i = int(k * 0.065 * SR); s2[i:i+len(b)] += b * (0.6 + 0.08*k)
nap = np.sin(ph(np.full(int(1.1*SR), 523.25))) * 0.5 + np.sin(ph(np.full(int(1.1*SR), 784.0))) * 0.3
nap *= env(len(nap), 0.15, 0.8) * (1 + 0.15*np.sin(2*np.pi*6*t_(1.1))); i = int(0.42*SR); s2[i:i+len(nap)] += nap * 0.35
sauver("sphere_2_donnees", echo(s2, 0.07, 0.3), -20)
# S3 activation : deux sons purs qui s'ouvrent ensemble (quinte), léger trémolo rapide, souffle aigu
d = 1.2; t = t_(d); e = env(len(t), 0.35, 0.6)
s3 = (np.sin(ph(np.full(len(t), 660.0))) + 0.7*np.sin(ph(np.full(len(t), 990.0))) + 0.25*np.sin(ph(np.full(len(t), 1980.0)))) * e
s3 *= 1 + 0.25 * np.sin(2*np.pi*18*t); s3 += passe_haut(rng.standard_normal(len(t)), 5000) * env(len(t), 0.5, 0.5) * 0.05
sauver("sphere_3_activation", echo(s3, 0.12, 0.22), -21)
# S4 impulsion : petit choc numérique sourd, puis anneau métallique FM qui s'éteint, grains aigus
d = 1.5; s4 = np.zeros(int(d*SR))
coup = blip(140, 60, 0.12, fm=0.0) * 0.9; s4[:len(coup)] += coup
anneau = blip(1400, 1380, 1.2, fm=2.5, ratio=1.414, a=0.01, r=1.1) * 0.5; i = int(0.03*SR); s4[i:i+len(anneau)] += anneau
sc = scintille(0.9, 4000, 9000, 10); i = int(0.15*SR); s4[i:i+len(sc)] += sc * 0.25
sauver("sphere_4_impulsion", echo(s4, 0.1, 0.25), -20)

# --- Éléments (très courts), crête -30 dBFS ---
sauver("element_1_tic", blip(2600, 2100, 0.045, fm=0.3), -30)                         # tic de données, hauteur qui retombe
sauver("element_2_chirp", blip(1800, 2700, 0.035, fm=0.6, ratio=2.0), -30)            # micro-gazouillis qui monte
x = blip(3200, 3150, 0.03, fm=1.5, ratio=3.5) + 0.4 * passe_haut(rng.standard_normal(int(0.03*SR)), 6000) * env(int(0.03*SR), 0.001, 0.025)
sauver("element_3_clic", x, -31)                                                       # clic métallique fin
x = blip(1568, 1568, 0.06, fm=0.8, ratio=2.0) + 0.5 * np.concatenate([np.zeros(int(0.025*SR)), blip(2349, 2349, 0.05, fm=0.8)])[:int(0.06*SR)]
sauver("element_4_double", x, -31)                                                     # double bip doux
print("ok")

# --- Chargement des éléments : un seul son continu pendant l'allumage (~1,3 s), crête -28 dBFS ---
D = 1.35
# C1 flux de données : grains très serrés (35 par seconde) qui forment une texture, hauteur qui monte
c1 = np.zeros(int(D*SR)); n = int(D*35)
for k in range(n):
    tt = k / 35; f = 900 * (2.2 ** (tt / D)) * rng.choice([1, 1.25, 1.5, 2])
    b = blip(f, f, 0.035, fm=0.4); i = int(tt*SR); c1[i:i+len(b)] += b[:len(c1)-i] * (0.5 + 0.5*np.sin(np.pi*tt/D))
sauver("chargement_1_flux", echo(c1, 0.06, 0.2), -28)
# C2 charge : nappe douce dont la hauteur et la vibration montent, puis se pose
t = t_(D); f = 320 * (1.9 ** ((t/D) ** 1.3)); trem = 1 + 0.3*np.sin(ph(4 + 22*(t/D)))
c2 = (np.sin(ph(f)) + 0.5*np.sin(ph(f*1.5)) + 0.2*np.sin(ph(f*3))) * trem * env(len(t), 0.25, 0.4)
sauver("chargement_2_charge", echo(c2, 0.08, 0.2), -28)
# C3 balayage filtré : souffle dont le filtre s'ouvre, battement régulier léger (comme une barre qui avance)
bruit = rng.standard_normal(len(t)); y = np.empty_like(bruit); p = 0.0
for i, v in enumerate(bruit):
    fc = 400 + 5000 * (i / len(bruit)) ** 1.5; a = 1 - np.exp(-2*np.pi*fc/SR); p += a*(v - p); y[i] = p
puls = 0.65 + 0.35*(np.sin(2*np.pi*12*t) > 0)
c3 = passe_haut(y, 300) * puls * env(len(t), 0.2, 0.35) + 0.25*np.sin(ph(f*2)) * env(len(t), 0.3, 0.4)
sauver("chargement_3_balayage", c3, -28)
# C4 calcul : arpège rapide et feutré qui monte puis redescend d'un cran, très bas
c4 = np.zeros(int(D*SR)); gam = [523, 659, 784, 988, 1047, 1319, 1568, 1976]
for k in range(20):
    tt = k * 0.06; f = gam[min(len(gam)-1, int(k * len(gam) / 16))] if k < 16 else gam[-1 - (k-16)]
    b = passe_bas(blip(f, f, 0.09, fm=0.6, ratio=2.0), 4000); i = int(tt*SR); c4[i:i+len(b)] += b[:len(c4)-i] * 0.7
sauver("chargement_4_calcul", echo(c4, 0.07, 0.25), -28)
print("chargements ok")

# S1 bis : le balayage holographique sans le scintillement final (ses petites attaques faisaient un cliquetis) ;
# il se termine sur une note cristalline lisse (quinte aiguë) qui s'ouvre et s'éteint
d = 1.3; t = t_(d); f = 180 * (2400/180) ** ((t/d) ** 1.6)
s1b = np.sin(ph(f)) * env(len(t), 0.25, 0.35) * 0.5
air = passe_bas(passe_haut(rng.standard_normal(len(t)), 2000), 6000) * env(len(t), 0.6, 0.5) * 0.12
s1b = np.concatenate([s1b + air, np.zeros(int(0.6*SR))])
tc = t_(0.9); cristal = (np.sin(ph(np.full(len(tc), 2349.3))) + 0.55*np.sin(ph(np.full(len(tc), 3520.0)))) * env(len(tc), 0.12, 0.7, 2.0)
o = int(0.95*SR); s1b[o:o+len(cristal)] += cristal * 0.22
sauver("sphere_1b_balayage_lisse", echo(s1b, 0.09, 0.22), -20)
print("sphère lisse ok")

# P : un panneau qui apparaît = version courte du chargement « charge » (même nappe qui monte), 0,55 s
D = 0.55; t = t_(D); f = 340 * (1.5 ** ((t/D) ** 1.2)); trem = 1 + 0.2*np.sin(ph(5 + 6*(t/D)))
p = (np.sin(ph(f)) + 0.5*np.sin(ph(f*1.5)) + 0.2*np.sin(ph(f*3))) * trem * env(len(t), 0.06, 0.3)
sauver("panneau_charge_court", echo(p, 0.08, 0.2), -30)
print("panneau ok")
