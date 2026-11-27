"""Voix de Jarvis : Kyutai Pocket TTS, sur le réseau Docker interne seulement. Gratuite, illimitée,
la même voix pour l'accueil et pour les réponses lues à voix haute.

Pocket TTS (binaire officiel) est lancé ici en sous-processus et n'écoute que 127.0.0.1 : rien
d'autre ne peut le joindre. L'interface découpe les longues réponses en morceaux et les enchaîne.

POST /parler  {"texte": "...", "genre": "homme"|"femme"}  →  audio/wav
              (en-tête Authorization: Bearer JARVIS_MCP_TOKEN ; genre : homme par défaut)
GET  /sante   →  {"ok": true, "pret": bool}       dès que le service écoute
GET  /etats/femme-<modèle>.safetensors           voix de femme, lue par Pocket TTS lui-même
              (127.0.0.1 seulement : Pocket n'accepte qu'une adresse http:// pour changer de voix)
"""
from __future__ import annotations

import hmac
import http.client
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("VOIX_PORT", "8730"))
JETON = os.environ.get("JARVIS_MCP_TOKEN", "")
POCKET_BIN = os.environ.get("POCKET_BIN", "/opt/pocket/pocket-tts")
POCKET_VOIX = os.environ.get("POCKET_VOIX", "peter_yearsley")   # voix intégrée ou chemin .safetensors
POCKET_LANGUE = os.environ.get("POCKET_LANGUE", "french")       # « french » (léger) ou « french_24l »
POCKET_PORT = int(os.environ.get("POCKET_PORT", "8740"))
VOIX_DIR = os.environ.get("VOIX_DIR", "/voix")                  # états des voix livrées (femme-*.safetensors)
MAX_TEXTE = 800                      # par demande ; l'interface envoie des morceaux plus courts

_verrou = threading.Lock()           # une synthèse à la fois, et un seul démarrage de Pocket
_pocket: subprocess.Popen | None = None


def journal(message: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} {message}", flush=True)


_UNITES = ("zéro un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze "
           "seize dix-sept dix-huit dix-neuf").split()
_DIZAINES = {2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante"}


def _moins_de_cent(n: int) -> str:
    if n < 20:
        return _UNITES[n]
    d, u = divmod(n, 10)
    if d in (7, 9):                       # soixante-dix…, quatre-vingt-dix…
        base = "soixante" if d == 7 else "quatre-vingt"
        return base + (" et onze" if n == 71 else "-" + _UNITES[10 + u])
    if d == 8:
        return "quatre-vingts" if u == 0 else "quatre-vingt-" + _UNITES[u]
    return _DIZAINES[d] + ("" if u == 0 else " et un" if u == 1 else "-" + _UNITES[u])


def _moins_de_mille(n: int) -> str:
    c, r = divmod(n, 100)
    if c == 0:
        return _moins_de_cent(r)
    tete = "cent" if c == 1 else _UNITES[c] + " cent" + ("s" if r == 0 else "")
    return tete + ("" if r == 0 else " " + _moins_de_cent(r))


def nombre_en_lettres(n: int, feminin: bool = False) -> str:
    """Entier en toutes lettres (français de France), jusqu'aux milliards."""
    if n < 0:
        return "moins " + nombre_en_lettres(-n, feminin)
    if n == 0:
        return "zéro"
    morceaux = []
    for valeur, nom in ((10**9, "milliard"), (10**6, "million"), (1000, "mille")):
        q, n = divmod(n, valeur)
        if q:
            if nom == "mille":
                morceaux.append("mille" if q == 1 else re.sub(r"(vingt|cent)s$", r"\1", _moins_de_mille(q)) + " mille")
            else:
                morceaux.append(f"{_moins_de_mille(q)} {nom}{'s' if q > 1 else ''}")
    if n:
        morceaux.append(_moins_de_mille(n))
    texte = " ".join(morceaux)
    if feminin and texte.endswith("un"):  # une heure, vingt et une heures
        texte += "e"
    return texte


def texte_lisible(texte: str) -> str:
    """Pocket TTS ne sait pas lire les chiffres ni les symboles : « 14 heures 25 » donne du charabia.
    Tout est écrit en lettres avant la synthèse."""
    texte = re.sub(r"(\d)\s*°\s*C?\b", r"\1 degrés", texte)
    texte = re.sub(r"(?<![\w-])-\s?(?=\d)", "moins ", texte)
    texte = re.sub(r"(\d)\s*%", r"\1 pour cent", texte)
    texte = re.sub(r"(\d)\s*km/h\b", r"\1 kilomètres heure", texte)
    # heures : « 14 h », « 9h », « 14 h 30 », « 14h05 », « 14:30 » → « 14 heures (30) » ;
    # sans cela Pocket lit « h » comme une lettre (« quatorze ache »)
    def heure(m: re.Match) -> str:
        h, mn = int(m.group(1)), m.group(2)
        if h > 24 or (mn and int(mn) > 59):
            return m.group(0)
        mot = "heure" if h <= 1 else "heures"
        return f"{h} {mot}" + (f" {int(mn)}" if mn and int(mn) else "")
    texte = re.sub(r"(?<![\d.,:])(\d{1,2})\s?[hH](?:\s?(\d{2}))?(?![\w])", heure, texte)
    texte = re.sub(r"(?<![\d.,:])(\d{1,2}):(\d{2})(?![\d:])", heure, texte)

    def decimal(m: re.Match) -> str:
        return f"{nombre_en_lettres(int(m.group(1)))} virgule {' '.join(_UNITES[int(c)] for c in m.group(2))}" \
            if len(m.group(2)) > 1 and m.group(2).startswith("0") else \
            f"{nombre_en_lettres(int(m.group(1)))} virgule {nombre_en_lettres(int(m.group(2)))}"
    texte = re.sub(r"\b(\d+)[.,](\d+)\b", decimal, texte)

    def entier(m: re.Match) -> str:
        suite = texte[m.end():m.end() + 12].lstrip().lower()
        feminin = suite.startswith(("heure", "tâche", "fois", "minute", "seconde", "semaine", "personne"))
        return nombre_en_lettres(int(m.group(0).replace(" ", "").replace(" ", "")), feminin)
    return re.sub(r"(?<![\w-])\d{1,3}(?:[  ]\d{3})+(?![\d\w])|\d+", entier, texte)


def _pocket_pret() -> bool:
    try:
        c = http.client.HTTPConnection("127.0.0.1", POCKET_PORT, timeout=2)
        c.request("GET", "/")
        ok = c.getresponse().status == 200
        c.close()
        return ok
    except OSError:
        return False


def env_pocket() -> dict:
    """Environnement de Pocket TTS. Il met en cache chaque voix lue par voice_url dans
    $HOME/.cache : dans le conteneur (utilisateur sans dossier personnel, disque en lecture
    seule), sans cela la voix de femme échoue (500) et l'interface retombe sur la voix du
    navigateur. Le cache va donc dans /tmp (tmpfs)."""
    env = dict(os.environ)
    if not os.access(env.get("HOME", ""), os.W_OK):
        env["HOME"] = tempfile.gettempdir()
    env.setdefault("XDG_CACHE_HOME", os.path.join(env["HOME"], ".cache"))
    return env


def demarrer_pocket() -> bool:
    """Lance (ou relance) le serveur Pocket TTS. À appeler sous _verrou."""
    global _pocket
    if not os.path.isfile(POCKET_BIN):
        return False
    if _pocket is not None and _pocket.poll() is None:
        return _pocket_pret()
    _pocket = subprocess.Popen(
        [POCKET_BIN, "serve", "--host", "127.0.0.1", "--port", str(POCKET_PORT),
         "--language", POCKET_LANGUE, "--quantize", "--default-voice", POCKET_VOIX],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env_pocket())
    for _ in range(240):            # le modèle se charge en quelques secondes
        if _pocket.poll() is not None:
            journal(f"Pocket TTS s'est arrêté (code {_pocket.returncode})")
            return False
        if _pocket_pret():
            return True
        time.sleep(0.5)
    journal("Pocket TTS ne répond pas")
    return False


def url_voix(genre: str) -> str | None:
    """Adresse de la voix demandée pour Pocket TTS ; None = sa voix par défaut (homme)."""
    if genre != "femme" or not os.path.isfile(os.path.join(VOIX_DIR, f"femme-{POCKET_LANGUE}.safetensors")):
        return None
    return f"http://127.0.0.1:{PORT}/etats/femme-{POCKET_LANGUE}.safetensors"


def multipart(texte: str, voix: str | None = None) -> tuple[bytes, str]:
    """Corps multipart/form-data : « text », et « voice_url » pour changer de voix."""
    f = uuid.uuid4().hex
    nl = "\r\n"
    champs = [("text", texte)] + ([("voice_url", voix)] if voix else [])
    corps = "".join(f"--{f}{nl}Content-Disposition: form-data; name=\"{k}\"{nl}{nl}{v}{nl}" for k, v in champs)
    return (corps + f"--{f}--{nl}").encode("utf-8"), f


def parler(texte: str, genre: str = "homme") -> bytes:
    """WAV de Pocket TTS. Lève RuntimeError si Pocket n'est pas disponible."""
    texte = texte_lisible(texte[:MAX_TEXTE])
    corps, frontiere = multipart(texte, url_voix(genre))
    with _verrou:
        if not demarrer_pocket():
            raise RuntimeError("Pocket TTS indisponible")
        c = http.client.HTTPConnection("127.0.0.1", POCKET_PORT, timeout=120)
        try:
            c.request("POST", "/tts", corps, {"Content-Type": f"multipart/form-data; boundary={frontiere}"})
            r = c.getresponse()
            audio = r.read()
        except (OSError, http.client.HTTPException) as e:
            raise RuntimeError(f"Pocket TTS injoignable ({type(e).__name__})") from None
        finally:
            c.close()
    if r.status != 200 or not audio.startswith(b"RIFF"):
        raise RuntimeError(f"Pocket TTS a répondu {r.status}")
    return audio


class Gestion(BaseHTTPRequestHandler):
    server_version = "jarvis-voix"
    sys_version = ""

    def log_message(self, *args):
        pass

    def _envoyer(self, code: int, corps: bytes, type_: str = "application/json; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def do_GET(self):  # noqa: N802
        if self.path == "/sante":
            pret = _pocket is not None and _pocket.poll() is None
            return self._envoyer(200, json.dumps({"ok": True, "pret": pret}).encode())
        m = re.fullmatch(r"/etats/(femme-[a-z0-9_]+\.safetensors)", self.path)
        if m and self.client_address[0] == "127.0.0.1" and os.path.isfile(os.path.join(VOIX_DIR, m.group(1))):
            with open(os.path.join(VOIX_DIR, m.group(1)), "rb") as f:
                return self._envoyer(200, f.read(), "application/octet-stream")
        self._envoyer(404, b"{}")

    def do_POST(self):  # noqa: N802
        if self.path != "/parler":
            return self._envoyer(404, b"{}")
        if not hmac.compare_digest(self.headers.get("Authorization", ""), f"Bearer {JETON}"):
            return self._envoyer(401, b'{"erreur": "jeton"}')
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            if n > 20000:
                raise ValueError
            d = json.loads(self.rfile.read(n) or b"{}")
            texte = " ".join(str(d.get("texte", "")).split())
            genre = "femme" if d.get("genre") == "femme" else "homme"
        except (ValueError, AttributeError):
            return self._envoyer(400, b'{"erreur": "requete invalide"}')
        if not texte:
            return self._envoyer(400, b'{"erreur": "texte vide"}')
        try:
            self._envoyer(200, parler(texte, genre), "audio/wav")
        except RuntimeError as e:
            journal(f"synthèse impossible : {e}")
            self._envoyer(503, b'{"erreur": "voix indisponible"}')


def main() -> None:
    if not JETON:
        raise SystemExit("JARVIS_MCP_TOKEN est requis")

    def lancer():
        with _verrou:
            pret = demarrer_pocket() and bool(parler_essai())
            if pret:
                parler_essai(url_voix("femme"))     # la voix de femme se charge une fois, dès le départ
        journal(f"voix {'prête' if pret else 'indisponible'} (Pocket TTS {POCKET_LANGUE}, {os.path.basename(POCKET_VOIX)})")

    def parler_essai(voix: str | None = None) -> bool:     # premier passage : la première vraie phrase part tout de suite
        if voix is None and parler_essai.fait:
            return True
        parler_essai.fait = True
        try:
            c = http.client.HTTPConnection("127.0.0.1", POCKET_PORT, timeout=60)
            corps, frontiere = multipart("Bonjour.", voix)
            c.request("POST", "/tts", corps, {"Content-Type": f"multipart/form-data; boundary={frontiere}"})
            ok = c.getresponse().status == 200
            c.close()
            return ok
        except OSError:
            return False
    parler_essai.fait = False
    # en tâche de fond : /sante répond tout de suite ; une demande pendant le chargement attend (verrou)
    threading.Thread(target=lancer, daemon=True).start()
    journal(f"service de voix sur le port {PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Gestion).serve_forever()


if __name__ == "__main__":
    main()
