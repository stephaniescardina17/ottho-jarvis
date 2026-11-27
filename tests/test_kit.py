"""Tests du kit serveur sans Docker : fichiers .env, détection simulée, fusion YAML.
python -m unittest discover -s tests"""
import importlib.machinery
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[1]
chargeur = importlib.machinery.SourceFileLoader("kit_cli", str(RACINE / "kit" / "bin" / "ottho-jarvis"))
spec = importlib.util.spec_from_loader("kit_cli", chargeur)
kit = importlib.util.module_from_spec(spec)
chargeur.exec_module(kit)


class TestEnv(unittest.TestCase):
    def test_mise_a_jour_garde_les_autres_lignes(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / ".env"
            f.write_text("# commentaire\nA=1\nB=2\n", encoding="utf-8")
            kit.ecrire_env(f, {"B": "3", "C": "4"})
            self.assertEqual(f.read_text(encoding="utf-8"), "# commentaire\nA=1\nB=3\nC=4\n")
            self.assertEqual(kit.lire_env(f), {"A": "1", "B": "3", "C": "4"})

    def test_fichier_absent(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / ".env"
            kit.ecrire_env(f, {"X": "y"})
            self.assertEqual(kit.lire_env(f), {"X": "y"})


class TestDetection(unittest.TestCase):
    def test_detection_simulee(self):
        with tempfile.TemporaryDirectory() as d:
            data = Path(d) / "data"
            (data / "profiles" / "clips").mkdir(parents=True)
            (data / "config.yaml").write_text("model:\n  provider: openrouter\nmultiplex_profiles: true\n", encoding="utf-8")
            (data / ".env").write_text("API_SERVER_KEY=secret\n", encoding="utf-8")
            ps = "hermes-x\tghcr.io/nousresearch/hermes-agent:1\ntraefik-1\ttraefik:v3\nautre\tnginx\n"
            inspections = {
                "hermes-x": {"Mounts": [{"Source": str(data), "Destination": "/opt/data"}],
                             "NetworkSettings": {"Networks": {"reseau-h": {}}}, "Config": {"Labels": {}}},
                "traefik-1": {"Config": {"Cmd": ["--certificatesresolvers.le.acme.email=x", "--entrypoints.https.address=:443"],
                                         "Labels": {}}, "Args": []},
                "autre": {"Config": {"Labels": {"traefik.http.routers.a.rule": "Host(`a.exemple.fr`)"}}},
            }
            with mock.patch.object(kit, "sh", return_value=mock.Mock(stdout=ps)), \
                    mock.patch.object(kit, "docker_inspect", side_effect=lambda n: inspections[n]):
                r = kit.detecter()
            h = r["hermes"][0]
            self.assertEqual(h["conteneur"], "hermes-x")
            self.assertEqual(h["reseaux"], ["reseau-h"])
            self.assertEqual(h["profils"], ["default", "clips"])
            self.assertTrue(h["multiplex"])
            self.assertEqual(h["fournisseur"], "openrouter")
            self.assertTrue(h["api_cle_presente"])
            self.assertFalse(h["api_ouverte_reseau"])
            self.assertNotIn("secret", json.dumps(r))          # aucune valeur secrète dans la sortie
            self.assertEqual(r["traefik"]["certresolvers"], ["le"])
            self.assertEqual(r["traefik"]["entrypoints_https"], ["https"])
            self.assertIn("a.exemple.fr", r["traefik"]["domaines_vus"])


class TestFusionYaml(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("ruamel"), "ruamel.yaml absent (présent dans Hermes)")
    def test_fusion_garde_le_modele_et_refuse_approbations_off(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "config.yaml"
            f.write_text("model:\n  provider: claude\n  default: sonnet\napprovals:\n  mode: off\nagent:\n  max_turns: 90\n", encoding="utf-8")
            r = subprocess.run([sys.executable, "-c", kit.FUSION_YAML,
                                json.dumps({"agent": {"max_turns": 30}, "memory": {"write_approval": True}}), str(f)],
                               capture_output=True, text=True)
            self.assertEqual(r.stdout.strip(), "ok", r.stderr)
            t = f.read_text(encoding="utf-8")
            self.assertIn("provider: claude", t)
            self.assertIn("max_turns: 30", t)
            self.assertIn("write_approval: true", t)
            self.assertIn("mode: smart", t)
            self.assertTrue((Path(d) / "config.yaml.bak-ottho-jarvis").exists())


class TestFinsDeLigne(unittest.TestCase):
    def test_kit_en_lf(self):
        """Le kit tourne sous Linux : un « \r » dans un script casse son lancement (python3\r)."""
        binaires = {".mp3", ".safetensors", ".png", ".pyc", ".wav"}
        fautifs = [str(f.relative_to(RACINE)) for d in ("kit", "scripts") for f in (RACINE / d).rglob("*")
                   if f.is_file() and f.suffix.lower() not in binaires and "__pycache__" not in f.parts and b"\r" in f.read_bytes()]
        self.assertEqual(fautifs, [])


if __name__ == "__main__":
    unittest.main()
