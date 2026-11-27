"""Double authentification de l'interface : TOTP (RFC 6238), QR code, activation obligatoire,
codes de secours, rejeu refusé, sessions fermées à chaque changement. Sans Docker.
python -m unittest discover -s tests"""
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
KIT = RACINE / "kit"
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(KIT / "services"))
import generer  # noqa: E402
import qr  # noqa: E402
from test_services import attendre, port_libre, requete  # noqa: E402

os.environ.setdefault("WEB_DATA_DIR", tempfile.gettempdir())
import web  # noqa: E402  (fonctions seulement : aucun serveur lancé à l'import)

MDP = "mot-de-passe-essai"


def code_pour(cle: str, decalage: int = 0) -> str:
    return web.code_totp(cle.replace(" ", ""), int(time.time() // 30) + decalage)


def cookie_de(r) -> str:
    return r.getheader("Set-Cookie").split(";")[0]


class TestBriques(unittest.TestCase):
    def test_totp_vecteur_rfc6238(self):
        # RFC 6238, annexe B : secret ASCII « 12345678901234567890 », T = 59 s -> 94287082 (8 chiffres)
        secret = base64.b32encode(b"12345678901234567890").decode()
        self.assertEqual(web.code_totp(secret, 59 // 30), "287082")
        self.assertEqual(web.code_totp(secret, 1111111109 // 30), "081804")

    def test_qr_svg(self):
        m = qr.matrice("otpauth://totp/J.A.R.V.I.S.:Stephanie?secret=" + "A" * 32 + "&issuer=J.A.R.V.I.S.")
        self.assertEqual(len(m), len(m[0]))
        self.assertEqual((len(m) - 17) % 4, 0)
        self.assertTrue(m[0][0] and m[6][6] and not m[1][1])      # repère de position en haut à gauche
        s = qr.svg("bonjour")
        self.assertTrue(s.startswith("<svg") and s.endswith("</svg>"))
        with self.assertRaises(ValueError):
            qr.matrice("x" * 400)

    def test_codes_de_secours(self):
        codes = web.nouveaux_codes_secours()
        self.assertEqual(len(set(codes)), 10)
        self.assertTrue(all(re.fullmatch(r"[a-z2-9]{4}-[a-z2-9]{4}", c) for c in codes))
        self.assertEqual(web._empreinte_secours("ABCD-EFGH"), web._empreinte_secours("abcd efgh"))


class TestParcours(unittest.TestCase):
    """Interface en mode « maintenant » : l'activation est obligatoire à la première connexion."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        for d in ("hermes/cron", "hermes/memories", "hermes/skills"):
            (t / d).mkdir(parents=True)
        sortie = t / "gen"
        generer.generer(json.loads((KIT / "exemples/config-minimale.json").read_text(encoding="utf-8")), sortie)
        shutil.copytree(KIT / "web", t / "web")
        (t / "web/jarvis.config.json").write_bytes((sortie / "web/jarvis.config.json").read_bytes())
        sel = os.urandom(16)
        h = hashlib.scrypt(MDP.encode(), salt=sel, n=16384, r=8, p=1, dklen=32)
        cls.donnees = t / "webdata"
        cls.port = port_libre()
        cls.proc = subprocess.Popen([sys.executable, "-I", str(KIT / "services/web.py")], env={
            **os.environ, "PYTHONIOENCODING": "utf-8", "WEB_PORT": str(cls.port), "STATIC_DIR": str(t / "web"),
            "WEB_DATA_DIR": str(cls.donnees), "HERMES_DIR": str(t / "hermes"), "HERMES_URL": "http://127.0.0.1:9/p/alfred/v1",
            "MCP_URL": "http://127.0.0.1:9/mcp", "JARVIS_API_KEY": "cle", "JARVIS_MCP_TOKEN": "jeton", "JARVIS_2FA": "maintenant",
            "JARVIS_PASSWORD_HASH": f"scrypt:16384:8:1:{base64.b64encode(sel).decode()}:{base64.b64encode(h).decode()}"},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        attendre(cls.port)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(5)
        cls.tmp.cleanup()

    def req(self, methode, chemin, corps=None, cookie=None):
        return requete(self.port, methode, chemin, corps, {"Cookie": cookie} if cookie else None)

    def test_parcours_complet(self):
        p = self.port
        # 1. mot de passe seul : session limitée à l'activation
        s, data, r = self.req("POST", "/api/connexion", {"mot_de_passe": MDP})
        self.assertEqual((s, json.loads(data)["etape"]), (200, "activation"))
        limitee = cookie_de(r)
        s, page, _ = self.req("GET", "/", cookie=limitee)
        self.assertIn("Double <em>authentification</em>", page.decode())        # page d'activation, pas l'interface
        self.assertNotIn('id="orb"', page.decode())
        self.assertNotIn("{{", page.decode())
        s, _, _ = self.req("GET", "/api/donnees", cookie=limitee)
        self.assertEqual(s, 403)
        s, _, _ = self.req("GET", "/config.json", cookie=limitee)
        self.assertEqual(s, 403)
        s, data, _ = self.req("GET", "/api/2fa", cookie=limitee)
        self.assertEqual(json.loads(data)["actif"], False)

        # 2. début : mot de passe redemandé, puis clé et QR code
        s, _, _ = self.req("POST", "/api/2fa/debut", {"mot_de_passe": "faux"}, limitee)
        self.assertEqual(s, 401)
        s, data, _ = self.req("POST", "/api/2fa/debut", {"mot_de_passe": MDP}, limitee)
        self.assertEqual(s, 200)
        d = json.loads(data)
        cle = d["cle"]
        self.assertRegex(cle.replace(" ", ""), r"^[A-Z2-7]{32}$")
        self.assertIn("<svg", d["qr"])
        s, _, _ = self.req("POST", "/api/2fa/confirmer", {"code": "000000" if code_pour(cle) != "000000" else "111111"}, limitee)
        self.assertEqual(s, 400)

        # 3. confirmation : 10 codes de secours, session complète ; l'ancienne session est fermée
        s, data, r = self.req("POST", "/api/2fa/confirmer", {"code": code_pour(cle)}, limitee)
        self.assertEqual(s, 200)
        secours = json.loads(data)["codes_secours"]
        self.assertEqual(len(secours), 10)
        complete = cookie_de(r)
        s, _, _ = self.req("GET", "/api/2fa", cookie=limitee)
        self.assertEqual(s, 401)
        s, data, _ = self.req("GET", "/config.json", cookie=complete)
        self.assertEqual(json.loads(data)["deux_facteurs"]["actif"], True)
        stocke = json.loads((self.donnees / "securite.json").read_text(encoding="utf-8"))
        self.assertNotIn(secours[0], json.dumps(stocke))                       # codes gardés en empreinte seulement
        if os.name == "posix":
            self.assertEqual((self.donnees / "securite.json").stat().st_mode & 0o777, 0o600)

        # 4. connexion : le code est demandé ; le code déjà utilisé est refusé (rejeu)
        s, data, _ = self.req("POST", "/api/connexion", {"mot_de_passe": MDP})
        self.assertEqual((s, json.loads(data)), (200, {"etape": "code"}))
        s, _, r = self.req("POST", "/api/connexion", {"mot_de_passe": MDP, "code": code_pour(cle)})
        self.assertEqual(s, 401)
        self.assertIsNone(r.getheader("Set-Cookie"))
        s, _, _ = self.req("POST", "/api/connexion", {"mot_de_passe": "faux", "code": secours[0]})
        self.assertEqual(s, 401)
        # code de secours : une seule fois
        s, data, r = self.req("POST", "/api/connexion", {"mot_de_passe": MDP, "code": secours[0].upper()})
        self.assertEqual(s, 200)
        self.assertEqual(json.loads(data)["codes_secours_restants"], 9)
        s, _, _ = self.req("POST", "/api/connexion", {"mot_de_passe": MDP, "code": secours[0]})
        self.assertEqual(s, 401)
        complete = cookie_de(r)
        s, page, _ = self.req("GET", "/", cookie=complete)
        self.assertIn('id="orb"', page.decode())

        # 5. désactivation : mot de passe + code ; en mode « maintenant », retour à l'activation
        s, _, _ = self.req("POST", "/api/2fa/desactiver", {"mot_de_passe": MDP, "code": "123"}, complete)
        self.assertEqual(s, 401)
        s, data, r = self.req("POST", "/api/2fa/desactiver", {"mot_de_passe": MDP, "code": secours[1]}, complete)
        self.assertEqual((s, json.loads(data)["activation"]), (200, True))
        s, _, _ = self.req("GET", "/api/donnees", cookie=complete)
        self.assertEqual(s, 401)                                               # sessions fermées
        s, _, _ = self.req("GET", "/api/donnees", cookie=cookie_de(r))
        self.assertEqual(s, 403)                                               # activation à refaire


if __name__ == "__main__":
    unittest.main()
