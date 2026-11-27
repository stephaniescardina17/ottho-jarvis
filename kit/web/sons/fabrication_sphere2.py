"""Allumage de la sphère, version 2 : son original synthétisé de zéro (aucun échantillon).
Reprend seulement la construction d'une vidéo de référence (« Futuristic 2050
Sci-Fi Mobile Interface HUD Animation », 0 à 3 s), analysée au spectrogramme : rien n'en est extrait.
Déroulé (2,7 s) : petits bips de données sur un bourdon, rafale de glitchs, montée de souffle granuleux
avec deux coups sourds, un bip, un « zap » descendant, puis un train de tics qui s'éteint.
python fabrication_sphere2.py DOSSIER  (numpy et soundfile)"""
import sys
import numpy as np
import soundfile as sf

sys.path.insert(0, __import__("os").path.dirname(__file__))
SR = 44100
OUT = sys.argv[1]
rng = np.random.default_rng(2050)
t_ = lambda d: np.arange(int(d * SR)) / SR


def env(n, a, r, courbe=3.0):
    e = np.ones(n); na, nr = max(1, int(a * SR)), max(1, int(r * SR))
    e[:na] = np.linspace(0, 1, na) ** 2; e[-nr:] *= np.linspace(1, 0, nr) ** courbe
    return e


def ph(f):
    return 2 * np.pi * np.cumsum(f) / SR


def passe_haut(x, fc):
    k = np.exp(-2 * np.pi * fc / SR); y = np.empty_like(x); p = px = 0.0
    for i, v in enumerate(x): p = k * (p + v - px); px = v; y[i] = p
    return y


def passe_bas(x, fc):
    a = 1 - np.exp(-2 * np.pi * fc / SR); y = np.empty_like(x); p = 0.0
    for i, v in enumerate(x): p += a * (v - p); y[i] = p
    return y


def bande(x, f1, f2):
    return passe_bas(passe_bas(passe_haut(passe_haut(x, f1), f1), f2), f2)


def blip(f0, f1, d, fm=0.0, ratio=2.0, a=0.002, r=None):
    t = t_(d); f = f0 * (f1 / f0) ** (t / d)
    x = np.sin(ph(f) + fm * np.sin(ph(f * ratio)))
    return x * env(len(t), a, r or d * 0.85)


def poser(dest, x, debut, gain=1.0):
    i = int(debut * SR); n = min(len(x), len(dest) - i)
    if n > 0: dest[i:i + n] += x[:n] * gain


def echo(x, d=0.09, g=0.22, n=4):
    y = np.concatenate([x, np.zeros(int(d * SR * n))])
    for k in range(1, n + 1):
        o = int(d * SR * k); y[o:o + len(x)] += x * (g ** k)
    return y


def stereo(x, largeur=0.004):
    """Image stéréo légère : la voie droite décalée de quelques millisecondes."""
    d = int(largeur * SR)
    return np.stack([x, np.concatenate([np.zeros(d), x[:-d]])], axis=1)


def sauver(nom, x, dbfs):
    x = passe_haut(x, 120)
    x = x / max(1e-9, np.abs(x).max()) * 10 ** (dbfs / 20)
    x[-400:] *= np.linspace(1, 0, 400)
    sf.write(f"{OUT}/{nom}.wav", stereo(x).astype(np.float32), SR)


def sphere(duree=2.8, coups=True, tics=26, souffle=1.0):
    s = np.zeros(int(duree * SR))
    # 1. bourdon discret sous les premiers bips (0,15 à 0,65 s)
    t = t_(0.5); poser(s, np.sin(ph(np.full(len(t), 185.0))) * env(len(t), 0.15, 0.3) * 0.08, 0.15)
    # 2. bips de données aigus, de plus en plus serrés (0,15 à 0,75 s)
    for k in range(22):
        debut = 0.15 + 0.6 * (k / 22) ** 0.7
        f = rng.uniform(3500, 9500); d = rng.uniform(0.008, 0.022)
        poser(s, blip(f, f * rng.uniform(0.9, 1.1), d, fm=0.8, ratio=1.5), debut, rng.uniform(0.15, 0.45))
    # 3. rafale de glitchs (0,58 à 0,74 s) : bruit écrêté par tranches, quelques clics
    for k in range(9):
        d = rng.uniform(0.006, 0.018); n = rng.standard_normal(int(d * SR))
        poser(s, np.sign(n) * np.abs(n) ** 0.3 * env(len(n), 0.0005, d * 0.6) * 0.35, 0.58 + k * 0.018)
    poser(s, blip(4300, 3800, 0.05, fm=2.0, ratio=3.1), 0.66, 0.4)
    # 4. montée de souffle granuleux (0,78 à 1,45 s), bande 1 à 3,5 kHz, grains irréguliers
    t = t_(0.7); n = bande(rng.standard_normal(len(t)), 1000, 3500)
    grains = passe_bas(np.abs(rng.standard_normal(len(t))) ** 2, 60)
    poser(s, n * grains / grains.max() * env(len(t), 0.35, 0.25, 2.0) * 3.0 * souffle, 0.78)
    #    note à 1,2 kHz qui tremble légèrement (0,85 à 1,07 s)
    t = t_(0.22); poser(s, np.sin(ph(1200 + 18 * np.sin(ph(np.full(len(t), 9.0))))) * env(len(t), 0.02, 0.12) * 0.25, 0.85)
    # 5. deux coups sourds dans le grave (0,95 et 1,28 s)
    if coups:
        for debut in (0.95, 1.28):
            t = t_(0.22); poser(s, np.sin(ph(70 * (35 / 70) ** (t / 0.22))) * env(len(t), 0.003, 0.2, 2.0) * 0.9, debut)
    # 6. bip à 600 Hz (1,50 à 1,62 s)
    poser(s, blip(610, 600, 0.12, fm=0.3, a=0.004, r=0.04), 1.50, 0.3)
    # 7. « zap » descendant de 6 kHz à 700 Hz (1,85 à 1,95 s)
    poser(s, blip(6000, 700, 0.1, fm=1.2, ratio=0.5, r=0.06), 1.85, 0.4)
    # 8. train de tics qui s'éteint (1,62 à 2,7 s), un toutes les 42 ms
    for k in range(tics):
        tic = passe_haut(rng.standard_normal(int(0.004 * SR)), 2500) * env(int(0.004 * SR), 0.0003, 0.003)
        poser(s, tic, 1.62 + k * 0.042, 0.35 * (1 - k / tics) ** 1.5)
    #    fil très aigu et très faible pendant les tics
    t = t_(0.8); poser(s, np.sin(ph(np.full(len(t), 10900.0))) * env(len(t), 0.1, 0.4) * 0.025, 1.62)
    return s


sauver("sphere_2a_fidele", echo(sphere(), 0.09, 0.18), -20)
sauver("sphere_2b_douce", echo(sphere(coups=False, tics=18, souffle=0.7), 0.09, 0.18), -22)
print("sphère v2 ok")
