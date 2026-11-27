"""Tu ou vous : la consigne envoyée à Hermes suit le réglage actuel de l'interface,
même s'il a changé depuis l'installation (SOUL.md garde le choix de l'installation).
Sans Docker. python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "kit" / "services"))
os.environ.setdefault("WEB_DATA_DIR", tempfile.gettempdir())
import web  # noqa: E402
from politesse import formules_merci  # noqa: E402


class TestFormules(unittest.TestCase):
    def test_vous(self):
        liste, retour = formules_merci(False, "Madame")
        self.assertIn("« Je vous en prie, Madame. »", liste)
        self.assertIn("« À votre service. »", liste)
        self.assertNotIn("t'en prie", liste)
        self.assertNotIn("Y'a pas", liste)            # familier : pas au vouvoiement
        self.assertEqual(retour, "« C'est moi qui vous remercie. »")

    def test_tu(self):
        liste, retour = formules_merci(True, "Camille")
        self.assertIn("« Je t'en prie, Camille. »", liste)
        self.assertIn("« Quand tu veux. »", liste)
        self.assertNotIn("vous", liste)
        self.assertNotIn("votre", liste)
        self.assertEqual(retour, "« C'est moi qui te remercie. »")


class TestConsigneInterface(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        d = Path(self.dossier.name)
        self.avant = (web.STATIC, web.REGLAGES)
        web.STATIC, web.REGLAGES = d, d / "reglages.json"
        (d / "jarvis.config.json").write_text(json.dumps({
            "assistant": {"nom": "Jarvis"},
            "utilisateur": {"prenom": "Stéphanie", "adresse": "civilite", "civilite": "Madame", "tutoiement": False}}),
            encoding="utf-8")

    def tearDown(self):
        web.STATIC, web.REGLAGES = self.avant
        self.dossier.cleanup()

    def test_vouvoiement_de_l_installation(self):
        s = web.consigne_interface()
        self.assertIn("**vouvoies**", s)
        self.assertIn("« Madame »", s)
        self.assertIn("« Je vous en prie, Madame. »", s)
        self.assertNotIn("t'en prie", s)

    def test_tutoiement_choisi_dans_les_reglages(self):
        web.REGLAGES.write_text(json.dumps({"utilisateur": {"adresse": "prenom", "tutoiement": True}}), encoding="utf-8")
        s = web.consigne_interface()
        self.assertIn("**tutoies**", s)
        self.assertIn("« Stéphanie »", s)
        self.assertIn("« Je t'en prie, Stéphanie. »", s)
        self.assertIn("« C'est moi qui te remercie. »", s)
        self.assertNotIn("vous en prie", s)


if __name__ == "__main__":
    unittest.main()
