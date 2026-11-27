"""Tests d'intégration des services (MCP et interface) avec un faux Hermes, sans Docker.
python -m unittest discover -s tests"""
import base64
import hashlib
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
KIT = RACINE / "kit"
sys.path.insert(0, str(KIT))
import generer  # noqa: E402

JETON = "0123456789abcdef0123456789abcdef"
CLE = "cle-essai-0123456789abcdef0123456789"
MDP = "mot-de-passe-essai"


def port_libre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class FauxHermes(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200 if self.path == "/health" else 404)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        if self.headers.get("Authorization") != f"Bearer {CLE}":
            self.send_response(401); self.send_header("Content-Length", "0"); self.end_headers(); return
        corps = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        n = len([m for m in corps["messages"] if m["role"] == "user"])
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for mot in f"Message {n} reçu .".split():
            self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': mot + ' '}}]})}\n\n".encode())
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")


def attendre(port: int):
    for _ in range(50):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"port {port} injoignable")


def requete(port, methode, chemin, corps=None, entetes=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request(methode, chemin, json.dumps(corps) if corps is not None else None,
              {"Content-Type": "application/json", **(entetes or {})})
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, data, r


class TestServices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        (t / "savoir/methodes").mkdir(parents=True)
        (t / "savoir/methodes/offre.md").write_text("---\ntitle: Offre irrésistible\ntidr: Méthode Hormozi\n---\nLes leviers.\n", encoding="utf-8")
        (t / "vide").mkdir()
        (t / "hermes/cron").mkdir(parents=True)
        (t / "hermes/memories").mkdir()
        (t / "hermes/skills").mkdir()
        (t / "hermes/cron/jobs.json").write_text(json.dumps({"jobs": [
            {"name": "brief-du-matin", "schedule": {"kind": "cron", "expr": "30 7 * * *"}, "repeat": {}, "enabled": True,
             "next_run_at": "2030-01-02T07:30:00+01:00", "deliver": "telegram"}]}), encoding="utf-8")
        # configuration publique générée pour Alfred (tutoiement, prénom)
        sortie = t / "gen"
        generer.generer(json.loads((KIT / "exemples/config-minimale.json").read_text(encoding="utf-8")), sortie)
        web = t / "web"
        web.mkdir()
        for f in (KIT / "web").iterdir():
            if f.is_dir():                                  # sons/
                shutil.copytree(f, web / f.name)
            else:
                (web / f.name).write_bytes(f.read_bytes())
        (web / "jarvis.config.json").write_bytes((sortie / "web/jarvis.config.json").read_bytes())

        cls.p_hermes, cls.p_mcp, cls.p_vide, cls.p_web = (port_libre() for _ in range(4))
        cls.hermes = ThreadingHTTPServer(("127.0.0.1", cls.p_hermes), FauxHermes)
        threading.Thread(target=cls.hermes.serve_forever, daemon=True).start()
        sel = os.urandom(16)
        h = hashlib.scrypt(MDP.encode(), salt=sel, n=16384, r=8, p=1, dklen=32)
        empreinte = f"scrypt:16384:8:1:{base64.b64encode(sel).decode()}:{base64.b64encode(h).decode()}"
        base = {**os.environ, "JARVIS_MCP_TOKEN": JETON, "PYTHONIOENCODING": "utf-8"}
        cls.procs = [
            subprocess.Popen([sys.executable, "-I", str(KIT / "services/serveur.py")], env={
                **base, "JARVIS_PORT": str(cls.p_mcp), "SAVOIR_DIR": str(t / "savoir"), "DATA_DIR": str(t / "data")},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
            subprocess.Popen([sys.executable, "-I", str(KIT / "services/serveur.py")], env={
                **base, "JARVIS_PORT": str(cls.p_vide), "SAVOIR_DIR": str(t / "vide"), "DATA_DIR": str(t / "data2")},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
            subprocess.Popen([sys.executable, "-I", str(KIT / "services/web.py")], env={
                **base, "WEB_PORT": str(cls.p_web), "STATIC_DIR": str(web), "WEB_DATA_DIR": str(t / "webdata"),
                "HERMES_DIR": str(t / "hermes"), "HERMES_URL": f"http://127.0.0.1:{cls.p_hermes}/p/alfred/v1",
                "MCP_URL": f"http://127.0.0.1:{cls.p_mcp}/mcp", "JARVIS_API_KEY": CLE, "JARVIS_PASSWORD_HASH": empreinte},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL),
        ]
        for p in (cls.p_mcp, cls.p_vide, cls.p_web):
            attendre(p)

    @classmethod
    def tearDownClass(cls):
        for p in cls.procs:
            p.terminate()
            p.wait(5)
        cls.hermes.shutdown()
        cls.tmp.cleanup()

    def mcp(self, port, methode, params=None):
        s, data, _ = requete(port, "POST", "/mcp", {"jsonrpc": "2.0", "id": 1, "method": methode, "params": params or {}},
                             {"Authorization": f"Bearer {JETON}"})
        self.assertEqual(s, 200)
        return json.loads(data)["result"]

    def test_mcp_avec_second_cerveau(self):
        noms = {o["name"] for o in self.mcp(self.p_mcp, "tools/list")["tools"]}
        self.assertTrue({"savoir_chercher", "taches_lister"} <= noms)
        r = self.mcp(self.p_mcp, "tools/call", {"name": "savoir_chercher", "arguments": {"requete": "offre hormozi"}})
        self.assertIn("Offre irrésistible", r["content"][0]["text"])
        r = self.mcp(self.p_mcp, "tools/call", {"name": "savoir_lire", "arguments": {"chemin": "../vide"}})
        self.assertTrue(r.get("isError"))

    def test_mcp_sans_second_cerveau(self):
        noms = {o["name"] for o in self.mcp(self.p_vide, "tools/list")["tools"]}
        self.assertNotIn("savoir_chercher", noms)
        self.assertIn("taches_ajouter", noms)

    def test_mcp_refuse_sans_jeton(self):
        s, _, _ = requete(self.p_mcp, "POST", "/mcp", {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(s, 401)

    def test_connexion_personnalisee_et_protegee(self):
        s, page, _ = requete(self.p_web, "GET", "/")
        self.assertEqual(s, 200)
        page = page.decode()
        self.assertIn("<title>Alfred</title>", page)
        # page visible sans connexion : salutation neutre, rien sur la personne
        self.assertIn("<em>Bonjour.</em>", page)
        self.assertNotIn("Camille", page)
        self.assertNotIn("{{", page)
        s, _, _ = requete(self.p_web, "GET", "/api/donnees")
        self.assertEqual(s, 401)
        s, _, _ = requete(self.p_web, "POST", "/api/connexion", {"mot_de_passe": "faux"})
        self.assertEqual(s, 401)

    def test_parcours_connecte(self):
        s, _, r = requete(self.p_web, "POST", "/api/connexion", {"mot_de_passe": MDP})
        self.assertEqual(s, 200)
        cookie = r.getheader("Set-Cookie").split(";")[0]
        s, page, _ = requete(self.p_web, "GET", "/", entetes={"Cookie": cookie})
        self.assertIn("ALFRED", page.decode())
        self.assertNotIn("{{", page.decode())
        self.assertIn("Camille.", page.decode())      # une fois connecté : la préférence s'applique
        s, data, _ = requete(self.p_web, "GET", "/api/donnees", entetes={"Cookie": cookie})
        d = json.loads(data)
        self.assertEqual(d["routines"][0]["heure"], "07:30")
        self.assertTrue(d["hermes"])
        self.assertIn(d["telegram"], ("ok", "coupe", "inconnu"))
        s, data, _ = requete(self.p_web, "GET", "/api/vps", entetes={"Cookie": cookie})
        v = json.loads(data)
        self.assertEqual(set(v), {"cpu", "memoire", "disque", "hermes_ms"})
        self.assertIsNotNone(v["hermes_ms"])
        s, _, _ = requete(self.p_web, "GET", "/api/vps")
        self.assertEqual(s, 401)
        # icône de l'onglet : publique (page de connexion), couleur d'accent, sans fond
        s, ico, r = requete(self.p_web, "GET", "/favicon.svg")
        self.assertEqual(s, 200)
        self.assertEqual(r.getheader("Content-Type"), "image/svg+xml")
        self.assertIn(b"<circle", ico)
        self.assertNotIn(b"<rect", ico)
        s, ico, _ = requete(self.p_web, "GET", "/favicon.svg?c=ambre")
        self.assertIn(b"#ffb547", ico)
        s, ico, _ = requete(self.p_web, "GET", "/favicon.svg?c=%3Cscript%3E")
        self.assertNotIn(b"script", ico)
        s, data, _ = requete(self.p_web, "POST", "/api/chat", {"messages": [
            {"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}, {"role": "user", "content": "c"}]},
            {"Cookie": cookie})
        self.assertEqual(s, 200)
        self.assertIn("Message", data.decode())
        self.assertIn("2", data.decode())   # l'historique est bien transmis
        s, _, _ = requete(self.p_web, "GET", "/..%2Fweb.py", entetes={"Cookie": cookie})
        self.assertEqual(s, 404)


if __name__ == "__main__":
    unittest.main()
