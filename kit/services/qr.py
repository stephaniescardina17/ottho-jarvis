"""QR code en SVG, bibliothèque standard Python seulement (pour l'activation de la double
authentification : l'adresse otpauth:// ne quitte jamais le serveur vers un service tiers).

Mode octets, correction d'erreur M, versions 1 à 10 (jusqu'à 213 octets), masque choisi
par la pénalité de la norme ISO/IEC 18004.
"""
from __future__ import annotations

# par version (index 1 à 10), niveau M : octets de correction par bloc, nombre de blocs
_ECC_M = [None, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26]
_BLOCS_M = [None, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5]
_FORMAT_M = 0  # bits de niveau pour M


def _modules_bruts(v: int) -> int:
    r = (16 * v + 128) * v + 64
    if v >= 2:
        n = v // 7 + 2
        r -= (25 * n - 10) * n - 55
        if v >= 7:
            r -= 36
    return r


def _octets_donnees(v: int) -> int:
    return _modules_bruts(v) // 8 - _ECC_M[v] * _BLOCS_M[v]


def _alignements(v: int) -> list[int]:
    if v == 1:
        return []
    n = v // 7 + 2
    pas = (v * 8 + n * 3 + 5) // (n * 4 - 4) * 2
    taille = v * 4 + 17
    return [6] + sorted(taille - 7 - i * pas for i in range(n - 1))


# --- Reed-Solomon sur GF(256), polynôme 0x11D ---
def _mul(x: int, y: int) -> int:
    z = 0
    for i in range(7, -1, -1):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _diviseur(degre: int) -> list[int]:
    r = [0] * (degre - 1) + [1]
    racine = 1
    for _ in range(degre):
        for j in range(degre):
            r[j] = _mul(r[j], racine)
            if j + 1 < degre:
                r[j] ^= r[j + 1]
        racine = _mul(racine, 0x02)
    return r


def _reste(donnees: list[int], div: list[int]) -> list[int]:
    r = [0] * len(div)
    for b in donnees:
        f = b ^ r.pop(0)
        r.append(0)
        for i, c in enumerate(div):
            r[i] ^= _mul(c, f)
    return r


def _bch_format(masque: int) -> int:
    d = (_FORMAT_M << 3) | masque
    r = d
    for _ in range(10):
        r = (r << 1) ^ ((r >> 9) * 0x537)
    return ((d << 10) | r) ^ 0x5412


def _bch_version(v: int) -> int:
    r = v
    for _ in range(12):
        r = (r << 1) ^ ((r >> 11) * 0x1F25)
    return (v << 12) | r


def matrice(texte: str) -> list[list[bool]]:
    donnees = texte.encode("utf-8")
    for v in range(1, 11):
        bits_long = 8 if v <= 9 else 16
        if 4 + bits_long + 8 * len(donnees) <= _octets_donnees(v) * 8:
            break
    else:
        raise ValueError("texte trop long pour le QR code")
    capacite = _octets_donnees(v) * 8
    # flux de bits : mode octets (0100), longueur, données, terminaison, remplissage
    bits: list[int] = []
    ajout = lambda val, n: bits.extend((val >> i) & 1 for i in range(n - 1, -1, -1))
    ajout(0b0100, 4)
    ajout(len(donnees), bits_long)
    for b in donnees:
        ajout(b, 8)
    ajout(0, min(4, capacite - len(bits)))
    ajout(0, (-len(bits)) % 8)
    octets = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    remplissage = 0xEC
    while len(octets) < capacite // 8:
        octets.append(remplissage)
        remplissage ^= 0xEC ^ 0x11
    # blocs et correction d'erreur, puis entrelacement
    nb, ecc = _BLOCS_M[v], _ECC_M[v]
    total = _modules_bruts(v) // 8
    courts = nb - total % nb
    long_court = total // nb
    div = _diviseur(ecc)
    blocs, k = [], 0
    for i in range(nb):
        n = long_court - ecc + (0 if i < courts else 1)
        dat = octets[k:k + n]
        k += n
        blocs.append((dat, _reste(dat, div)))
    final = []
    for i in range(long_court - ecc + 1):
        for j, (dat, _) in enumerate(blocs):
            if i < len(dat):
                final.append(dat[i])
    for i in range(ecc):
        for _, e in blocs:
            final.append(e[i])

    taille = v * 4 + 17
    m = [[False] * taille for _ in range(taille)]
    fonction = [[False] * taille for _ in range(taille)]

    def pose(x, y, noir):
        m[y][x] = noir
        fonction[y][x] = True

    for i in range(taille):  # motifs de synchronisation
        pose(6, i, i % 2 == 0)
        pose(i, 6, i % 2 == 0)
    for cx, cy in ((3, 3), (taille - 4, 3), (3, taille - 4)):  # repères de position
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                x, y = cx + dx, cy + dy
                if 0 <= x < taille and 0 <= y < taille:
                    d = max(abs(dx), abs(dy))
                    pose(x, y, d not in (2, 4))
    al = _alignements(v)
    for i, ax in enumerate(al):
        for j, ay in enumerate(al):
            if (i == 0 and j == 0) or (i == 0 and j == len(al) - 1) or (i == len(al) - 1 and j == 0):
                continue
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    pose(ax + dx, ay + dy, max(abs(dx), abs(dy)) != 1)

    def poser_format(masque):
        b = _bch_format(masque)
        bit = lambda i: (b >> i) & 1 == 1
        for i in range(6):
            pose(8, i, bit(i))
        pose(8, 7, bit(6))
        pose(8, 8, bit(7))
        pose(7, 8, bit(8))
        for i in range(9, 15):
            pose(14 - i, 8, bit(i))
        for i in range(8):
            pose(taille - 1 - i, 8, bit(i))
        for i in range(8, 15):
            pose(8, taille - 15 + i, bit(i))
        pose(8, taille - 8, True)  # module toujours noir

    poser_format(0)  # réserve les zones de format
    if v >= 7:
        b = _bch_version(v)
        for i in range(18):
            noir = (b >> i) & 1 == 1
            a, c = taille - 11 + i % 3, i // 3
            pose(a, c, noir)
            pose(c, a, noir)

    # placement des données en zigzag
    i = 0
    flux = [(octet >> (7 - j)) & 1 for octet in final for j in range(8)]
    droite = taille - 1
    while droite >= 1:
        if droite == 6:
            droite = 5
        for vert in range(taille):
            for j in range(2):
                x = droite - j
                monte = ((droite + 1) & 2) == 0
                y = taille - 1 - vert if monte else vert
                if not fonction[y][x] and i < len(flux):
                    m[y][x] = flux[i] == 1
                    i += 1
        droite -= 2

    masques = [
        lambda x, y: (x + y) % 2 == 0, lambda x, y: y % 2 == 0, lambda x, y: x % 3 == 0,
        lambda x, y: (x + y) % 3 == 0, lambda x, y: (x // 3 + y // 2) % 2 == 0,
        lambda x, y: x * y % 2 + x * y % 3 == 0, lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
        lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
    ]

    def appliquer(k):
        for y in range(taille):
            for x in range(taille):
                if not fonction[y][x] and masques[k](x, y):
                    m[y][x] = not m[y][x]

    def penalite() -> int:
        p = 0
        lignes = [row for row in m] + [[m[y][x] for y in range(taille)] for x in range(taille)]
        for ligne in lignes:  # suites de 5 ou plus
            n, prec = 0, None
            for c in ligne:
                if c == prec:
                    n += 1
                else:
                    if n >= 5:
                        p += n - 2
                    n, prec = 1, c
            if n >= 5:
                p += n - 2
            s = "".join("1" if c else "0" for c in ligne)  # motifs proches des repères
            for motif in ("10111010000", "00001011101"):
                p += 40 * sum(1 for k in range(len(s) - 10) if s[k:k + 11] == motif)
        for y in range(taille - 1):  # carrés 2x2
            for x in range(taille - 1):
                if m[y][x] == m[y][x + 1] == m[y + 1][x] == m[y + 1][x + 1]:
                    p += 3
        noirs = sum(c for row in m for c in row)
        p += abs(noirs * 20 - taille * taille * 10) // (taille * taille) * 10
        return p

    meilleur, score = 0, None
    for k in range(8):
        appliquer(k)
        poser_format(k)
        s = penalite()
        if score is None or s < score:
            meilleur, score = k, s
        appliquer(k)  # annule (le masque est son propre inverse)
    appliquer(meilleur)
    poser_format(meilleur)
    return m


def svg(texte: str, module: int = 6, marge: int = 4) -> str:
    """QR code noir sur blanc (lisible par toutes les applications), en un seul chemin SVG."""
    m = matrice(texte)
    n = len(m) + 2 * marge
    chemin = "".join(f"M{x + marge},{y + marge}h1v1h-1z" for y, row in enumerate(m) for x, c in enumerate(row) if c)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" width="{n * module}" height="{n * module}" '
            f'shape-rendering="crispEdges" role="img" aria-label="QR code"><rect width="{n}" height="{n}" fill="#fff"/>'
            f'<path d="{chemin}" fill="#000"/></svg>')
