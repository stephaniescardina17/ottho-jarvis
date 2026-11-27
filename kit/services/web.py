"""Interface web de Jarvis : page protégée par mot de passe (et double authentification
en option), discussion en flux avec le
profil Hermes `jarvis`, et données des panneaux (tâches, rappels, routines, mémoire,
savoir-faire). Bibliothèque standard Python seulement.

Exposée par Traefik en HTTPS. Les clés (API Hermes, jeton MCP) restent ici : le navigateur
ne les voit jamais. Les fichiers d'Hermes sont montés en lecture seule, sans le .env.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import json
import os
import re
import secrets
import sys
import threading
import time
import unicodedata
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))     # qr.py, à côté (aussi avec python -I)
import qr  # noqa: E402
from politesse import consigne_adresse  # noqa: E402

PORT = int(os.environ.get("WEB_PORT", "8720"))
STATIC = Path(os.environ.get("STATIC_DIR", "/app/web")).resolve()
DONNEES = Path(os.environ.get("WEB_DATA_DIR", "/data/web")).resolve()
HERMES = Path(os.environ.get("HERMES_DIR", "/hermes")).resolve()
HERMES_URL = urllib.parse.urlparse(os.environ.get("HERMES_URL", "http://hermes-agent-abcd-hermes-agent-1:8642/p/jarvis/v1"))
MCP_URL = urllib.parse.urlparse(os.environ.get("MCP_URL", "http://jarvis-services:8710/mcp"))
API_KEY = os.environ.get("JARVIS_API_KEY", "")
MCP_TOKEN = os.environ.get("JARVIS_MCP_TOKEN", "")
MDP_HASH = os.environ.get("JARVIS_PASSWORD_HASH", "")
SECRET = (os.environ.get("SESSION_SECRET", "") or secrets.token_hex(32)).encode()
TZ = ZoneInfo(os.environ.get("TZ", "Europe/Paris"))
DUREE_SESSION = 30 * 24 * 3600
COOKIE = "jarvis_session"
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".js": "text/javascript; charset=utf-8", ".json": "application/json; charset=utf-8",
         ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".svg": "image/svg+xml",
         ".wav": "audio/wav", ".png": "image/png", ".ico": "image/x-icon", ".webmanifest": "application/manifest+json"}


def journal(message: str) -> None:
    print(f"{datetime.now(TZ).strftime('%H:%M:%S')} {message}", flush=True)


# --- Mot de passe et sessions --------------------------------------------------

def verifier_mdp(mdp: str) -> bool:
    """Format : scrypt:n:r:p:sel_b64:empreinte_b64 (écrit par « ottho-jarvis mot-de-passe » ; pas de « $ »,
    que Docker Compose interpréterait dans le .env)."""
    try:
        _, n, r, p, sel, attendu = MDP_HASH.split(":")
        calcul = hashlib.scrypt(mdp.encode(), salt=base64.b64decode(sel), n=int(n), r=int(r), p=int(p),
                                maxmem=128 * 1024 * 1024, dklen=len(base64.b64decode(attendu)))
        return hmac.compare_digest(calcul, base64.b64decode(attendu))
    except (ValueError, TypeError):
        return False


def signer(valeur: str) -> str:
    return hmac.new(SECRET, valeur.encode(), hashlib.sha256).hexdigest()


# Une session porte son niveau (« c » : complète ; « i » : mot de passe accepté mais double
# authentification à activer d'abord, 15 min) et la génération de securite.json : changer la
# double authentification ou le mot de passe ferme toutes les sessions ouvertes avant.
DUREE_ACTIVATION = 15 * 60


def creer_session(niveau: str = "c") -> str:
    exp = str(int(time.time()) + (DUREE_SESSION if niveau == "c" else DUREE_ACTIVATION))
    corps = f"{secrets.token_urlsafe(16)}.{exp}.{niveau}.{generation()}"
    return f"{corps}.{signer(corps)}"


def niveau_session(valeur: str) -> str | None:
    try:
        jeton, exp, niveau, gen, sig = valeur.split(".")
        if not hmac.compare_digest(sig, signer(f"{jeton}.{exp}.{niveau}.{gen}")):
            return None
        if int(exp) <= time.time() or int(gen) != generation() or niveau not in ("c", "i"):
            return None
    except ValueError:
        return None
    if niveau == "c" and MODE_2FA == "maintenant" and not deux_facteurs_actifs():
        return "i"
    return niveau


def cookie_session(niveau: str) -> str:
    duree = DUREE_SESSION if niveau == "c" else DUREE_ACTIVATION
    return f"{COOKIE}={creer_session(niveau)}; Path=/; Max-Age={duree}; HttpOnly; Secure; SameSite=Strict"


class Limiteur:
    """N essais ratés par clé (adresse) et par quart d'heure (5 par défaut)."""

    def __init__(self, maxi: int = 5):
        self.maxi = maxi
        self.essais: dict[str, list[float]] = {}
        self.verrou = threading.Lock()

    def autorise(self, ip: str) -> bool:
        with self.verrou:
            maintenant = time.time()
            liste = [t for t in self.essais.get(ip, []) if maintenant - t < 900]
            self.essais[ip] = liste
            return len(liste) < self.maxi

    def echec(self, ip: str) -> None:
        with self.verrou:
            self.essais.setdefault(ip, []).append(time.time())


LIMITEUR = Limiteur()
LIMITEUR_CODES = Limiteur(5)          # codes à 6 chiffres ratés, par adresse
LIMITEUR_CODES_TOUS = Limiteur(20)    # et toutes adresses confondues (clé « tous »)


# --- Double authentification (codes à 6 chiffres, RFC 6238) ------------------------
# Le secret est créé ici et montré une seule fois à la personne (QR code et clé) ; il reste
# dans data/web/securite.json (droits 600, ce conteneur seulement). Les codes de secours n'y
# sont gardés qu'en empreinte, chacun sert une fois. « generation » augmente à chaque
# changement : les sessions ouvertes avant sont refusées.
MODE_2FA = os.environ.get("JARVIS_2FA", "") if os.environ.get("JARVIS_2FA", "") in ("maintenant", "plus_tard") else "plus_tard"
SECURITE = DONNEES / "securite.json"
VERROU_SECURITE = threading.Lock()
ALPHABET_SECOURS = "abcdefghjkmnpqrstuvwxyz23456789"     # sans 0/o, 1/l/i


def lire_securite() -> dict:
    try:
        d = json.loads(SECURITE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def ecrire_securite(d: dict) -> None:
    tmp = SECURITE.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, SECURITE)


def generation() -> int:
    try:
        return int(lire_securite().get("generation", 0))
    except (TypeError, ValueError):
        return 0


def deux_facteurs_actifs(d: dict | None = None) -> bool:
    d = lire_securite() if d is None else d
    return bool((d.get("totp") or {}).get("secret"))


def etat_deux_facteurs() -> dict:
    d = lire_securite()
    return {"actif": deux_facteurs_actifs(d), "mode": MODE_2FA, "codes_secours_restants": len(d.get("secours") or []),
            "depuis": (d.get("totp") or {}).get("depuis")}


def code_totp(secret: str, pas: int) -> str:
    cle = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    h = hmac.new(cle, pas.to_bytes(8, "big"), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    return f"{(int.from_bytes(h[o:o + 4], 'big') & 0x7FFFFFFF) % 1_000_000:06d}"


def pas_valide(secret: str, code: str, apres: int = -1) -> int | None:
    """Pas de temps (30 s) du code s'il est juste, à ±30 s près ; jamais un pas déjà utilisé."""
    code = re.sub(r"\s", "", code)
    if not re.fullmatch(r"\d{6}", code):
        return None
    maintenant = int(time.time() // 30)
    for pas in (maintenant - 1, maintenant, maintenant + 1):
        if pas > apres and hmac.compare_digest(code_totp(secret, pas), code):
            return pas
    return None


def _empreinte_secours(code: str) -> str:
    return hashlib.sha256(re.sub(r"[\s-]", "", code.lower()).encode()).hexdigest()


def nouveaux_codes_secours() -> list[str]:
    tirer = lambda: "".join(secrets.choice(ALPHABET_SECOURS) for _ in range(4))
    return [f"{tirer()}-{tirer()}" for _ in range(10)]


def verifier_second_facteur(code: str) -> str | None:
    """« totp », « secours » (code de secours, alors effacé) ou None."""
    with VERROU_SECURITE:
        d = lire_securite()
        t = d.get("totp") or {}
        if not t.get("secret"):
            return None
        pas = pas_valide(t["secret"], code, int(t.get("dernier_pas", -1)))
        if pas is not None:
            t["dernier_pas"] = pas
            d["totp"] = t
            ecrire_securite(d)
            return "totp"
        restants = d.get("secours") or []
        e = _empreinte_secours(code)
        if len(re.sub(r"[\s-]", "", code)) == 8 and e in restants:
            restants.remove(e)
            d["secours"] = restants
            ecrire_securite(d)
            return "secours"
    return None


def commencer_activation() -> dict:
    """Nouveau secret en attente (10 min) ; renvoie la clé et le QR code à montrer une fois."""
    secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
    with VERROU_SECURITE:
        d = lire_securite()
        d["en_attente"] = {"secret": secret, "expire": int(time.time()) + 600}
        ecrire_securite(d)
    c = config_fusionnee()
    emetteur = str((c.get("assistant") or {}).get("affiche") or (c.get("assistant") or {}).get("nom") or "Jarvis")
    compte = str((c.get("utilisateur") or {}).get("prenom") or "interface")
    uri = (f"otpauth://totp/{urllib.parse.quote(emetteur + ':' + compte)}?secret={secret}"
           f"&issuer={urllib.parse.quote(emetteur)}")
    return {"cle": " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)), "qr": qr.svg(uri)}


def confirmer_activation(code: str) -> list[str] | None:
    with VERROU_SECURITE:
        d = lire_securite()
        a = d.get("en_attente") or {}
        if not a.get("secret") or int(a.get("expire", 0)) < time.time():
            return None
        pas = pas_valide(a["secret"], code)
        if pas is None:
            return None
        codes = nouveaux_codes_secours()
        d["totp"] = {"secret": a["secret"], "dernier_pas": pas, "depuis": datetime.now(TZ).isoformat(timespec="seconds")}
        d["secours"] = [_empreinte_secours(x) for x in codes]
        d.pop("en_attente", None)
        d["generation"] = int(d.get("generation", 0)) + 1
        ecrire_securite(d)
    return codes


def desactiver_deux_facteurs() -> None:
    with VERROU_SECURITE:
        d = lire_securite()
        for k in ("totp", "en_attente"):
            d.pop(k, None)
        d["secours"] = []
        d["generation"] = int(d.get("generation", 0)) + 1
        ecrire_securite(d)


# --- Appels internes -----------------------------------------------------------

def _connexion(url: urllib.parse.ParseResult, timeout: float) -> http.client.HTTPConnection:
    return http.client.HTTPConnection(url.hostname, url.port or 80, timeout=timeout)


def mcp(outil: str, arguments: dict | None = None):
    corps = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": outil, "arguments": arguments or {}}})
    c = _connexion(MCP_URL, 15)
    try:
        c.request("POST", MCP_URL.path, corps, {"Authorization": f"Bearer {MCP_TOKEN}",
                                                 "Content-Type": "application/json"})
        r = json.loads(c.getresponse().read())
    finally:
        c.close()
    res = r.get("result", {})
    texte = (res.get("content") or [{}])[0].get("text", "")
    if res.get("isError"):
        raise RuntimeError(texte)
    return json.loads(texte)


def hermes_en_ligne() -> bool:
    try:
        c = _connexion(HERMES_URL, 4)
        c.request("GET", "/health")
        ok = c.getresponse().status == 200
        c.close()
        return ok
    except OSError:
        return False


# --- Données des panneaux --------------------------------------------------------

JOURS = ["Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."]


def _jour(dt: datetime) -> str:
    j = (dt.date() - datetime.now(TZ).date()).days
    return "Auj." if j == 0 else "Dem." if j == 1 else JOURS[dt.weekday()]


def taches_cron() -> tuple[list, list]:
    try:
        jobs = json.loads((HERMES / "cron" / "jobs.json").read_text(encoding="utf-8")).get("jobs", [])
    except (OSError, ValueError):
        return [], []
    rappels, routines = [], []
    for j in jobs:
        if not j.get("enabled", True) or j.get("state") in ("completed", "paused"):
            continue
        prochain = j.get("next_run_at")
        dt = datetime.fromisoformat(prochain).astimezone(TZ) if prochain else None
        unique = (j.get("schedule") or {}).get("kind") != "cron" or (j.get("repeat") or {}).get("times") == 1
        texte = (j.get("prompt") or j.get("name") or "").strip()
        texte = re.sub(r"^(rappel\s*:\s*)", "", texte, flags=re.I)
        if unique:
            if dt:
                rappels.append({"jour": _jour(dt), "heure": dt.strftime("%H:%M"), "texte": texte[:160],
                                "quand": dt.isoformat()})
        else:
            expr = (j.get("schedule") or {}).get("expr", "")
            m = re.match(r"^(\d+)\s+(\d+)\s", expr)
            routines.append({"nom": j.get("name") or "Routine", "heure": f"{int(m[2]):02d}:{int(m[1]):02d}" if m else expr,
                             "canal": (j.get("deliver") or "").capitalize(),
                             "prochain": dt.isoformat() if dt else None})
    rappels.sort(key=lambda r: r["quand"])
    routines.sort(key=lambda r: r["heure"])
    return rappels, routines


def memoire() -> tuple[list, list]:
    entrees = []
    for nom in ("USER.md", "MEMORY.md"):
        try:
            texte = (HERMES / "memories" / nom).read_text(encoding="utf-8")
        except OSError:
            continue
        morceaux = re.split(r"\n\s*§\s*\n", texte) if "§" in texte else re.split(r"\n\s*\n", texte)
        for m in morceaux:
            m = re.sub(r"^\s*[-*]\s+", "", m.strip())
            if m and not m.startswith("#"):
                entrees.append(m[:300])
    attente = []
    for f in sorted((HERMES / "pending" / "memory").glob("*.json")) if (HERMES / "pending" / "memory").is_dir() else []:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            for op in (d.get("payload") or {}).get("operations", []):
                if op.get("content"):
                    attente.append(op["content"][:300])
        except (OSError, ValueError):
            continue
    return entrees, attente


def savoir_faire() -> list:
    """Skills appris en travaillant : ceux qui ne figurent pas dans la liste de base."""
    try:
        base = set((DONNEES / "skills-de-base.txt").read_text(encoding="utf-8").split())
    except OSError:
        base = set()
    liste = []
    racine = HERMES / "skills"
    for f in racine.rglob("SKILL.md") if racine.is_dir() else []:
        nom = f.parent.name
        if nom in base:
            continue
        description = ""
        try:
            for ligne in f.read_text(encoding="utf-8").splitlines()[:12]:
                if ligne.startswith("description:"):
                    description = ligne[12:].strip().strip('"')
                    break
        except OSError:
            pass
        liste.append({"nom": nom.replace("-", " ").capitalize(), "description": description[:160],
                      "modifie": int(f.stat().st_mtime)})
    liste.sort(key=lambda s: -s["modifie"])
    return liste


def _cle_titre(t: str) -> str:
    """Titre comparable : minuscules, sans apostrophes ni ponctuation (« Actualité de l’IA » = « actualite de l'ia »)."""
    t = unicodedata.normalize("NFKD", t.lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in t if not unicodedata.combining(c))).strip()


def brief_du_jour() -> dict | None:
    """Le brief du matin envoyé aujourd'hui par Hermes (routine « brief-du-matin »), découpé par rubrique :
    {"heure": "07:30", "rubriques": {"actualite de l ia": ["titre 1", …]}}. Lu dans cron/output du profil,
    côté serveur ; None s'il n'a pas encore été envoyé aujourd'hui."""
    try:
        jobs = json.loads((HERMES / "cron" / "jobs.json").read_text(encoding="utf-8")).get("jobs", [])
        job = next(j for j in jobs if j.get("name") == "brief-du-matin")
        dossier = HERMES / "cron" / "output" / str(job["id"])
        f = max(dossier.glob("*.md"), key=lambda x: x.name)
    except (OSError, ValueError, StopIteration, KeyError):
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})_(\d{2})-(\d{2})", f.name)
    if not m or m[1] != datetime.now(TZ).date().isoformat():
        return None
    texte = f.read_text(encoding="utf-8", errors="replace")[:60_000]
    reponse = texte.split("## Response", 1)[1] if "## Response" in texte else ""
    rubriques, cle, lignes = {}, None, []

    def ranger():
        if cle and lignes:
            rubriques[cle] = lignes[:6]

    for brute in reponse.splitlines():
        ligne = brute.strip()
        titre = re.match(r"^(?:#+\s*|\*\*)([^*:]{2,80})(?:\*\*)?\s*:?\s*(?:\*\*)?\s*:?\s*(.*)$", ligne)
        if titre and (ligne.startswith("#") or ligne.startswith("**")):
            ranger()
            cle, lignes = _cle_titre(titre[1]), []
            reste = titre[2].strip(" *:")
            if reste:
                lignes.append(reste)
        elif cle and re.match(r"^([-*•]|\d+[.)])\s+", ligne):
            lignes.append(re.sub(r"^([-*•]|\d+[.)])\s+", "", ligne))
        elif cle and ligne and not lignes:
            lignes.append(ligne)
    ranger()
    propre = lambda x: re.sub(r"\*\*|__|`", "", x).strip()[:300]
    return {"heure": f"{m[2]}:{m[3]}", "rubriques": {k: [propre(x) for x in v if propre(x)] for k, v in rubriques.items()}}


def donnees() -> dict:
    rappels, routines = taches_cron()
    souvenirs, attente = memoire()
    try:
        taches = mcp("taches_lister")
    except Exception as e:  # noqa: BLE001
        journal(f"tâches indisponibles : {type(e).__name__}")
        taches = None
    return {"rappels": rappels, "routines": routines, "souvenirs": souvenirs, "en_attente": attente,
            "savoir_faire": savoir_faire(), "taches": taches, "hermes": hermes_en_ligne(),
            "telegram": etat_telegram(), "brief": brief_du_jour()}


def etat_telegram() -> str:
    """« ok », « coupe » ou « inconnu », d'après les derniers événements Telegram du journal du profil.
    Le journal est lu côté serveur seulement : rien de son contenu n'est envoyé au navigateur."""
    f = HERMES / "logs" / "gateway.log"
    try:
        with f.open("rb") as fh:
            fh.seek(max(0, f.stat().st_size - 200_000))
            lignes = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return "inconnu"
    for ligne in reversed(lignes):
        if "Telegram" not in ligne:
            continue
        # « polling recovered » : Hermes s'est reconnu seul après une coupure passagère de Telegram
        # (Bad Gateway, Timed out). La ligne « restarted after network error » qui la précède contient
        # « network error » : sans ce test, l'interface croyait Telegram coupé (constaté le 2026-11-26).
        if re.search(r"Connected to Telegram|polling recovered", ligne):
            return "ok"
        if re.search(r"Conflict|Unauthorized|Invalid token|Disconnected|disconnect|failed to connect|Network ?error|Polling stopped", ligne, re.I):
            return "coupe"
    return "inconnu"


# --- État du VPS (pour les indicateurs autour de la sphère) ---------------------------

_CPU_AVANT: tuple[int, int] | None = None


def _cpu_brut() -> tuple[int, int]:
    with open("/proc/stat", encoding="ascii") as f:
        v = [int(x) for x in f.readline().split()[1:]]
    inactif = v[3] + (v[4] if len(v) > 4 else 0)
    return sum(v), inactif


def stats_vps() -> dict:
    """CPU, mémoire et disque de la machine hôte (vus depuis /proc et le disque monté), et temps de
    réponse de Hermes. Aucune donnée personnelle."""
    global _CPU_AVANT
    res = {}
    try:
        t1 = _cpu_brut()
        if _CPU_AVANT is None:
            time.sleep(0.25)
            _CPU_AVANT, t1 = t1, _cpu_brut()
        total, inactif = t1[0] - _CPU_AVANT[0], t1[1] - _CPU_AVANT[1]
        _CPU_AVANT = t1
        res["cpu"] = round(100 * (1 - inactif / total)) if total > 0 else None
    except (OSError, ValueError):
        res["cpu"] = None
    try:
        info = {}
        with open("/proc/meminfo", encoding="ascii") as f:
            for ligne in f:
                k, _, v = ligne.partition(":")
                info[k] = int(v.split()[0])
        res["memoire"] = round(100 * (1 - info["MemAvailable"] / info["MemTotal"]))
    except (OSError, KeyError, ValueError):
        res["memoire"] = None
    try:
        s = os.statvfs(DONNEES)
        res["disque"] = round(100 * (1 - s.f_bavail / s.f_blocks))
    except (OSError, AttributeError, ZeroDivisionError):
        res["disque"] = None
    try:
        t = time.perf_counter()
        c = _connexion(HERMES_URL, 4)
        c.request("GET", "/health")
        ok = c.getresponse().status == 200
        c.close()
        res["hermes_ms"] = round((time.perf_counter() - t) * 1000) if ok else None
    except OSError:
        res["hermes_ms"] = None
    return res


# --- Réglages modifiés depuis l'interface ----------------------------------------

REGLAGES = DONNEES / "reglages.json"
MUSIQUE_MAX = 10 * 1024 * 1024          # 10 Mo : un morceau, pas une discothèque
EXT_MUSIQUE = (".mp3", ".m4a", ".ogg")


def enregistrer_musique(nom: str, donnees_: bytes) -> str:
    """Vérifie le fichier (extension, vrai en-tête audio, taille), l'écrit dans
    DONNEES/musique et retire le morceau précédent. Renvoie le nom gardé."""
    if len(donnees_) > MUSIQUE_MAX:
        raise ValueError("Fichier trop gros : 10 Mo au plus.")
    nom = re.sub(r"[\x00-\x1f/\\:*?\"<>|]", "", Path(nom.replace("\\", "/")).name).strip(" .")[:120]
    ext = Path(nom).suffix.lower()
    if ext not in EXT_MUSIQUE or not Path(nom).stem.strip():
        raise ValueError("Format non pris en charge : MP3, M4A ou OGG.")
    tete = donnees_[:12]
    valide = {".mp3": tete.startswith(b"ID3") or (len(tete) > 1 and tete[0] == 0xFF and tete[1] & 0xE0 == 0xE0),
              ".m4a": tete[4:8] == b"ftyp", ".ogg": tete.startswith(b"OggS")}[ext]
    if not valide:
        raise ValueError(f"Ce fichier ne ressemble pas à un {ext[1:].upper()} valide.")
    dossier = DONNEES / "musique"
    dossier.mkdir(parents=True, exist_ok=True)
    provisoire = dossier / f".envoi-{secrets.token_hex(6)}"
    provisoire.write_bytes(donnees_)
    os.chmod(provisoire, 0o640)
    os.replace(provisoire, dossier / nom)
    for f in dossier.iterdir():          # un seul morceau gardé : le précédent est remplacé
        if f.name != nom and f.suffix.lower() in EXT_MUSIQUE:
            f.unlink(missing_ok=True)
    journal(f"musique d'ouverture : {nom} ({len(donnees_) // 1024} Ko)")
    return nom


CLES_REGLAGES = {"utilisateur", "ton", "accent", "voix", "genre_voix", "accueil", "sons", "ville", "musique"}


def lire_reglages() -> dict:
    try:
        return json.loads(REGLAGES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ecrire_reglages(nouveaux: dict) -> dict:
    propres = {k: v for k, v in nouveaux.items() if k in CLES_REGLAGES}
    if len(json.dumps(propres)) > 4000:
        raise ValueError("trop gros")
    tmp = REGLAGES.with_suffix(".tmp")
    tmp.write_text(json.dumps(propres, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(REGLAGES)
    return propres


def config_fusionnee() -> dict:
    try:
        base = json.loads((STATIC / "jarvis.config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        base = {}

    def fusion(a, b):
        out = dict(a)
        for k, v in b.items():
            out[k] = fusion(a.get(k, {}), v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
        return out
    c = fusion(base, lire_reglages())
    c["voix_locale"] = VOIX_URL is not None
    return c


# --- Voix (conteneur <profil>-voix, gratuite) ---------------------------------------
# Accueil et réponses lues à voix haute : Pocket TTS, la même voix partout.
VOIX_URL = urllib.parse.urlparse(os.environ.get("VOIX_URL", "")) if os.environ.get("VOIX_URL") else None


def voix_locale(texte: str, genre: str = "homme") -> bytes:
    if not VOIX_URL:
        raise RuntimeError("voix locale non configurée")
    texte = " ".join(texte.split())[:800]       # l'interface envoie des morceaux de ~300 caractères
    if not texte:
        raise RuntimeError("texte vide")
    c = _connexion(VOIX_URL, 150)      # la première phrase peut attendre le chargement de Pocket TTS
    try:
        c.request("POST", "/parler", json.dumps({"texte": texte, "genre": "femme" if genre == "femme" else "homme"}),
                  {"Authorization": f"Bearer {MCP_TOKEN}", "Content-Type": "application/json"})
        r = c.getresponse()
        audio = r.read()
    except (OSError, http.client.HTTPException) as e:
        raise RuntimeError(f"voix locale injoignable ({type(e).__name__})") from None
    finally:
        c.close()
    if r.status != 200:
        raise RuntimeError(f"voix locale : erreur {r.status}")
    return audio


# --- En-têtes de sécurité ----------------------------------------------------------

def _csp() -> str:
    try:
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        m = re.search(r'<script type="importmap">(.*?)</script>', html, re.S)
        h = base64.b64encode(hashlib.sha256(m.group(1).encode()).digest()).decode() if m else ""
    except OSError:
        h = ""
    return ("default-src 'self'; "
            f"script-src 'self' https://cdn.jsdelivr.net 'sha256-{h}'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data:; media-src 'self' blob:; "
            "connect-src 'self' https://api.open-meteo.com https://geocoding-api.open-meteo.com https://cdn.jsdelivr.net; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


CSP = _csp()
PAGE_CONNEXION = (Path(__file__).resolve().parent / "connexion.html")
PAGE_SECURITE = (Path(__file__).resolve().parent / "securite.html")


# Sons personnels : un fichier de la personne déposé dans DONNEES/sons (jarvis.sh envoyer-son) remplace
# le son livré du même nom (sons/sphere.mp3 → sons/sphere.wav, .mp3, .ogg ou .m4a), tel quel. Il reste
# dans les données de l'instance : il n'entre jamais dans le plugin ni dans son dépôt.
SONS_REMPLACABLES = ("sphere", "element", "frappe", "tic", "complet", "fin")


def son_personnel(relatif: str) -> Path | None:
    m = re.fullmatch(r"sons/([a-z]+)\.mp3", relatif)
    if not m or m.group(1) not in SONS_REMPLACABLES:
        return None
    for ext in (".wav", ".mp3", ".ogg", ".m4a"):
        f = DONNEES / "sons" / (m.group(1) + ext)
        if f.is_file():
            return f
    return None


# Couleurs d'accent (mêmes valeurs que ACCENTS dans web/app.js)
ACCENTS = {"cyan": "#5fe1ff", "rouge": "#e63c2e", "vert": "#4ff0b0", "ambre": "#ffb547", "violet": "#a993ff"}


def favicon(demande: str = "") -> bytes:
    """Icône de l'onglet : l'hexagone et le rond du logo, sans fond, dans la couleur d'accent choisie
    (celle demandée par la page, ?c=ambre, sinon celle enregistrée). Traits plus épais que le logo
    de la page pour rester lisible à 16 pixels."""
    accent = demande if demande in ACCENTS else str(config_fusionnee().get("accent") or "")
    couleur = ACCENTS.get(accent, ACCENTS["cyan"])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="2 0.5 28 31">'
            f'<path d="M16 2.5 27.7 9.25v13.5L16 29.5 4.3 22.75V9.25Z" fill="none" stroke="{couleur}" '
            f'stroke-width="2.6" stroke-linejoin="round"/>'
            f'<circle cx="16" cy="16" r="5" fill="{couleur}"/></svg>').encode("utf-8")


def consigne_interface() -> str:
    """Tu ou vous, et la façon d'appeler la personne, d'après le réglage actuel de l'interface."""
    c = config_fusionnee()
    u = c.get("utilisateur") or {}
    a = c.get("assistant") or {}
    adresse = u.get("prenom") if u.get("adresse") == "prenom" and u.get("prenom") else (u.get("civilite") or "Monsieur")
    return consigne_adresse(bool(u.get("tutoiement")), adresse, str(a.get("nom") or "Jarvis"))


def personnaliser(html: bytes) -> bytes:
    """Remplace les repères {{…}} des pages par le nom de l'assistant et la façon de s'adresser à la personne."""
    import html as h
    c = config_fusionnee()
    a = c.get("assistant") or {}
    nom = str(a.get("affiche") or a.get("nom") or "Jarvis")      # nom affiché (J.A.R.V.I.S.)
    u = c.get("utilisateur") or {}
    adresse = u.get("prenom") if u.get("adresse") == "prenom" and u.get("prenom") else (u.get("civilite") or "Monsieur")
    tu = bool(u.get("tutoiement"))
    valeurs = {
        "{{NOM}}": nom, "{{NOM_MAJ}}": nom.upper(), "{{ADRESSE}}": adresse,
        "{{CONSIGNE}}": "Accès réservé. Saisis ton mot de passe." if tu else "Accès réservé. Saisissez votre mot de passe.",
        "{{TUTOIEMENT}}": "1" if tu else "0",
    }
    texte = html.decode("utf-8")
    for cle, val in valeurs.items():
        texte = texte.replace(cle, h.escape(val))
    return texte.encode("utf-8")


class Gestion(BaseHTTPRequestHandler):
    server_version = "jarvis"
    sys_version = ""

    def log_message(self, *args):
        pass

    # --- outils ---
    def _ip(self) -> str:
        fwd = self.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() or self.client_address[0]

    def _session(self) -> str | None:
        """Niveau de la session : « c » (complète), « i » (double authentification à activer) ou None."""
        for morceau in self.headers.get("Cookie", "").split(";"):
            nom, _, valeur = morceau.strip().partition("=")
            if nom == COOKIE:
                niveau = niveau_session(valeur)
                if niveau:
                    return niveau
        return None

    def _connecte(self) -> bool:
        return self._session() == "c"

    def _envoyer(self, code: int, corps: bytes = b"", type_: str = "application/json; charset=utf-8",
                 entetes: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", type_)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store" if type_.startswith(("application/json", "text/html")) else "private, max-age=300")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")
        for k, v in (entetes or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if corps and self.command != "HEAD":
            self.wfile.write(corps)

    def _json(self, code: int, obj) -> None:
        self._envoyer(code, json.dumps(obj, ensure_ascii=False).encode())

    def _lire_json(self, maxi: int = 200_000) -> dict:
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n > maxi:
            raise ValueError("requête trop grosse")
        return json.loads(self.rfile.read(n) or b"{}")

    def _meme_origine(self) -> bool:
        """Les requêtes qui modifient viennent de la page elle-même (défense en plus du cookie SameSite)."""
        origine = self.headers.get("Origin", "")
        hote = self.headers.get("Host", "")
        return not origine or urllib.parse.urlparse(origine).netloc == hote

    def _fichier(self, chemin: str) -> None:
        relatif = urllib.parse.unquote(chemin.lstrip("/")) or "index.html"
        perso = son_personnel(relatif)
        if perso:
            return self._envoyer(200, perso.read_bytes(), TYPES[perso.suffix.lower()])
        if relatif.startswith("musique/"):
            f = (DONNEES / relatif).resolve()
            racine = DONNEES / "musique"
        else:
            f = (STATIC / relatif).resolve()
            racine = STATIC
        if racine.resolve() not in f.parents or not f.is_file() or f.suffix.lower() not in TYPES:
            return self._envoyer(404, b"{}")
        donnees_ = f.read_bytes()
        if f.suffix.lower() == ".html":
            donnees_ = personnaliser(donnees_)
        self._envoyer(200, donnees_, TYPES[f.suffix.lower()])

    # --- routes ---
    def do_HEAD(self):  # noqa: N802
        self.do_GET()

    def do_GET(self):  # noqa: N802
        chemin = self.path.split("?")[0]
        if chemin == "/sante":
            return self._json(200, {"ok": True})
        if chemin == "/favicon.svg":                     # public : l'onglet de la page de connexion en a besoin
            c = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("c", [""])[0]
            return self._envoyer(200, favicon(c), "image/svg+xml")
        if chemin in ("/connexion.js", "/securite.js"):
            return self._envoyer(200, (PAGE_CONNEXION.parent / chemin.lstrip("/")).read_bytes(),
                                 "text/javascript; charset=utf-8")
        niveau = self._session()
        if niveau is None:
            if chemin.startswith("/api/"):
                return self._json(401, {"erreur": "connexion requise"})
            return self._envoyer(200, personnaliser(PAGE_CONNEXION.read_bytes()), "text/html; charset=utf-8")
        if chemin == "/api/2fa":
            return self._json(200, etat_deux_facteurs())
        if niveau == "i":
            # mot de passe accepté, double authentification à activer : rien d'autre n'est servi
            if chemin.startswith("/api/") or chemin.endswith(".json"):
                return self._json(403, {"erreur": "double authentification à activer", "activation": True})
            return self._envoyer(200, personnaliser(PAGE_SECURITE.read_bytes()), "text/html; charset=utf-8")
        if chemin == "/securite":
            return self._envoyer(200, personnaliser(PAGE_SECURITE.read_bytes()), "text/html; charset=utf-8")
        if chemin == "/api/vps":
            return self._json(200, stats_vps())
        if chemin == "/api/donnees":
            return self._json(200, donnees())
        if chemin == "/config.json":
            return self._json(200, {**config_fusionnee(), "deux_facteurs": etat_deux_facteurs()})
        if chemin == "/api/reglages":
            return self._json(200, lire_reglages())
        if chemin == "/musique/playlist.json":
            dossier = DONNEES / "musique"
            liste = []
            for f in sorted(dossier.glob("*")) if dossier.is_dir() else []:
                if f.suffix.lower() in (".mp3", ".m4a", ".ogg"):
                    artiste, _, titre = f.stem.partition(" - ")
                    liste.append({"titre": (titre or artiste).strip(), "artiste": artiste.strip() if titre else "",
                                  "fichier": "musique/" + urllib.parse.quote(f.name)})
            return self._json(200, liste)
        return self._fichier(chemin)

    def do_POST(self):  # noqa: N802
        chemin = self.path.split("?")[0]
        if not self._meme_origine():
            return self._json(403, {"erreur": "origine refusée"})
        if chemin == "/api/connexion":
            ip = self._ip()
            if not LIMITEUR.autorise(ip):
                return self._json(429, {"erreur": "Trop d'essais. Réessayez dans un quart d'heure."})
            try:
                d = self._lire_json(2000)
                mdp, code = str(d.get("mot_de_passe", "")), str(d.get("code", "")).strip()
            except ValueError:
                return self._json(400, {"erreur": "requête invalide"})
            if not MDP_HASH or not verifier_mdp(mdp):
                LIMITEUR.echec(ip)
                journal(f"connexion refusée ({ip})")
                return self._json(401, {"erreur": "Mot de passe incorrect."})
            if deux_facteurs_actifs():
                if not code:
                    return self._json(200, {"etape": "code"})
                if not (LIMITEUR_CODES.autorise(ip) and LIMITEUR_CODES_TOUS.autorise("tous")):
                    return self._json(429, {"erreur": "Trop d'essais. Réessayez dans un quart d'heure.", "etape": "code"})
                sorte = verifier_second_facteur(code)
                if not sorte:
                    LIMITEUR_CODES.echec(ip)
                    LIMITEUR_CODES_TOUS.echec("tous")
                    journal(f"code refusé ({ip})")
                    return self._json(401, {"erreur": "Code incorrect.", "etape": "code"})
                journal(f"connexion ({ip}, {'code de secours' if sorte == 'secours' else 'double authentification'})")
                reponse = {"ok": True}
                if sorte == "secours":
                    reponse["codes_secours_restants"] = etat_deux_facteurs()["codes_secours_restants"]
                return self._envoyer(200, json.dumps(reponse).encode(), entetes={"Set-Cookie": cookie_session("c")})
            if MODE_2FA == "maintenant":
                journal(f"connexion ({ip}), double authentification à activer")
                return self._envoyer(200, b'{"ok": true, "etape": "activation"}', entetes={"Set-Cookie": cookie_session("i")})
            journal(f"connexion ({ip})")
            return self._envoyer(200, b'{"ok": true}', entetes={"Set-Cookie": cookie_session("c")})
        if chemin == "/api/deconnexion":
            return self._envoyer(200, b'{"ok": true}', entetes={
                "Set-Cookie": f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict"})
        if chemin.startswith("/api/2fa/"):
            niveau = self._session()
            if not niveau:
                return self._json(401, {"erreur": "connexion requise"})
            return self._deux_facteurs(chemin, niveau)
        if not self._connecte():
            return self._json(401, {"erreur": "connexion requise"})
        if chemin == "/api/diag" and os.environ.get("JARVIS_DIAG") == "1":
            # relevé de diagnostic du navigateur (essais seulement, variable JARVIS_DIAG=1)
            try:
                for ligne in str(self._lire_json(20000).get("lignes", ""))[:16000].splitlines()[:200]:
                    journal("diag " + ligne[:300])
            except ValueError:
                pass
            return self._json(200, {"ok": True})
        if chemin == "/api/chat":
            return self._chat()
        if chemin == "/api/voix":
            # Pocket TTS (local et gratuit, conteneur <profil>-voix) ; l'interface envoie des morceaux courts
            try:
                d = self._lire_json(20000)
                genre = d.get("genre") or config_fusionnee().get("genre_voix", "homme")
                return self._envoyer(200, voix_locale(str(d.get("texte", "")), str(genre)), "audio/wav")
            except ValueError:
                return self._json(400, {"erreur": "requête invalide"})
            except RuntimeError as e:
                code = 503 if "configurée" in str(e) else 400 if "vide" in str(e) else 502
                return self._json(code, {"erreur": str(e)})
        if chemin == "/api/musique":
            return self._musique()
        if chemin == "/api/taches/cocher":
            try:
                d = self._lire_json(2000)
                return self._json(200, mcp("taches_cocher", {"id": str(d["id"]), "fait": bool(d.get("fait", True))}))
            except (KeyError, ValueError, RuntimeError) as e:
                return self._json(400, {"erreur": str(e)[:200]})
        return self._json(404, {})

    def _musique(self) -> None:
        """Musique d'ouverture choisie dans les réglages : gardée sur le serveur pour les
        prochaines ouvertures. Un seul morceau : le nouveau remplace l'ancien."""
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
        except ValueError:
            n = 0
        if n > MUSIQUE_MAX:
            return self._json(413, {"erreur": "Fichier trop gros : 10 Mo au plus."})
        if n < 1000:
            return self._json(400, {"erreur": "Fichier vide."})
        nom = urllib.parse.unquote(self.headers.get("X-Nom-Fichier", ""))
        try:
            nom = enregistrer_musique(nom, self.rfile.read(n))
        except ValueError as e:
            return self._json(400, {"erreur": str(e)})
        return self._json(200, {"ok": True, "fichier": nom})

    def _deux_facteurs(self, chemin: str, niveau: str) -> None:
        """Activer (début puis confirmation avec un premier code) ou désactiver la double authentification."""
        ip = self._ip()
        try:
            d = self._lire_json(2000)
        except ValueError:
            return self._json(400, {"erreur": "requête invalide"})
        mdp, code = str(d.get("mot_de_passe", "")), str(d.get("code", "")).strip()
        if chemin == "/api/2fa/debut":
            if deux_facteurs_actifs():
                return self._json(409, {"erreur": "La double authentification est déjà activée."})
            if not LIMITEUR.autorise(ip):
                return self._json(429, {"erreur": "Trop d'essais. Réessayez dans un quart d'heure."})
            if not verifier_mdp(mdp):
                LIMITEUR.echec(ip)
                return self._json(401, {"erreur": "Mot de passe incorrect."})
            return self._json(200, commencer_activation())
        if chemin == "/api/2fa/confirmer":
            if not (LIMITEUR_CODES.autorise(ip) and LIMITEUR_CODES_TOUS.autorise("tous")):
                return self._json(429, {"erreur": "Trop d'essais. Réessayez dans un quart d'heure."})
            codes = confirmer_activation(code)
            if not codes:
                LIMITEUR_CODES.echec(ip)
                LIMITEUR_CODES_TOUS.echec("tous")
                return self._json(400, {"erreur": "Code incorrect ou expiré. Vérifiez l'heure du téléphone, ou recommencez."})
            journal(f"double authentification activée ({ip})")
            return self._envoyer(200, json.dumps({"codes_secours": codes}).encode(),
                                 entetes={"Set-Cookie": cookie_session("c")})
        if chemin == "/api/2fa/desactiver":
            if niveau != "c" or not deux_facteurs_actifs():
                return self._json(409, {"erreur": "La double authentification n'est pas activée."})
            if not (LIMITEUR.autorise(ip) and LIMITEUR_CODES.autorise(ip)):
                return self._json(429, {"erreur": "Trop d'essais. Réessayez dans un quart d'heure."})
            if not verifier_mdp(mdp):
                LIMITEUR.echec(ip)
                return self._json(401, {"erreur": "Mot de passe incorrect."})
            if not verifier_second_facteur(code):
                LIMITEUR_CODES.echec(ip)
                return self._json(401, {"erreur": "Code incorrect."})
            desactiver_deux_facteurs()
            journal(f"double authentification désactivée ({ip})")
            suivant = "i" if MODE_2FA == "maintenant" else "c"
            return self._envoyer(200, json.dumps({"ok": True, "activation": suivant == "i"}).encode(),
                                 entetes={"Set-Cookie": cookie_session(suivant)})
        return self._json(404, {})

    def do_PUT(self):  # noqa: N802
        if self.path.split("?")[0] != "/api/reglages":
            return self._json(404, {})
        if not self._connecte() or not self._meme_origine():
            return self._json(401, {"erreur": "connexion requise"})
        try:
            return self._json(200, ecrire_reglages(self._lire_json(8000)))
        except ValueError as e:
            return self._json(400, {"erreur": str(e)})

    def _chat(self) -> None:
        """Relaie la discussion vers Hermes et renvoie la réponse en flux (SSE)."""
        try:
            d = self._lire_json()
        except ValueError:
            return self._json(400, {"erreur": "requête invalide"})
        messages = d.get("messages")
        if not isinstance(messages, list):
            messages = [{"role": "user", "content": str(d.get("message", ""))}]
        propres = []
        for m in messages[-24:]:
            if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
                propres.append({"role": m["role"], "content": m["content"][:8000]})
        if not propres or propres[-1]["role"] != "user":
            return self._json(400, {"erreur": "message manquant"})
        corps = json.dumps({"model": "jarvis", "stream": True, "messages": [
            {"role": "system", "content": "Cette demande vient de l'interface web : les cartes sont autorisées. "
                                          + consigne_interface()},
            *propres]})
        c = _connexion(HERMES_URL, 300)
        try:
            c.request("POST", HERMES_URL.path + "/chat/completions", corps,
                      {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json",
                       "Accept": "text/event-stream"})
            r = c.getresponse()
            if r.status != 200:
                journal(f"Hermes a répondu {r.status}")
                r.read()
                return self._json(502, {"erreur": f"Jarvis est indisponible ({r.status})."})
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("Connection", "close")
            self.end_headers()
            while True:
                bloc = r.read1(4096) if hasattr(r, "read1") else r.read(1024)
                if not bloc:
                    break
                self.wfile.write(bloc)
                self.wfile.flush()
        except (OSError, http.client.HTTPException) as e:
            journal(f"discussion interrompue : {type(e).__name__}")
            try:
                self._json(502, {"erreur": "Jarvis ne répond pas."})
            except OSError:
                pass
        finally:
            c.close()
        self.close_connection = True


def main() -> None:
    if not API_KEY or not MCP_TOKEN:
        raise SystemExit("JARVIS_API_KEY et JARVIS_MCP_TOKEN sont requis")
    if not MDP_HASH:
        journal("aucun mot de passe défini : personne ne peut se connecter (ottho-jarvis mot-de-passe PROFIL)")
    DONNEES.mkdir(parents=True, exist_ok=True)
    (DONNEES / "musique").mkdir(exist_ok=True)
    journal(f"interface Jarvis sur le port {PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Gestion).serve_forever()


if __name__ == "__main__":
    main()
