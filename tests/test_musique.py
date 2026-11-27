"""Musique d'ouverture envoyée depuis Réglages > Musique : un seul morceau gardé sur le serveur,
10 Mo au plus, vrai fichier audio. Sans Docker. python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "kit" / "services"))
os.environ.setdefault("WEB_DATA_DIR", tempfile.gettempdir())
import web  # noqa: E402

MP3 = b"ID3" + b"\x00" * 2000


class TestMusique(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.avant = web.DONNEES
        web.DONNEES = Path(self.dossier.name)

    def tearDown(self):
        web.DONNEES = self.avant
        self.dossier.cleanup()

    def morceaux(self):
        return sorted(f.name for f in (web.DONNEES / "musique").iterdir())

    def test_le_nouveau_remplace_l_ancien(self):
        self.assertEqual(web.enregistrer_musique("AC-DC - Thunderstruck.mp3", MP3), "AC-DC - Thunderstruck.mp3")
        self.assertEqual(self.morceaux(), ["AC-DC - Thunderstruck.mp3"])
        web.enregistrer_musique("Autre - Titre.ogg", b"OggS" + b"\x00" * 2000)
        self.assertEqual(self.morceaux(), ["Autre - Titre.ogg"])

    def test_refus(self):
        with self.assertRaisesRegex(ValueError, "10 Mo"):
            web.enregistrer_musique("gros.mp3", b"ID3" + b"\x00" * web.MUSIQUE_MAX)
        with self.assertRaisesRegex(ValueError, "Format"):
            web.enregistrer_musique("video.mp4", MP3)
        with self.assertRaisesRegex(ValueError, "valide"):
            web.enregistrer_musique("faux.mp3", b"<html>" + b"\x00" * 2000)
        self.assertFalse((web.DONNEES / "musique").exists() and self.morceaux())

    def test_nom_nettoye(self):
        # pas de sortie du dossier musique/
        self.assertEqual(web.enregistrer_musique("../../etc/x.mp3", MP3), "x.mp3")
        self.assertEqual(web.enregistrer_musique(r"..\..\a:b.mp3", MP3), "ab.mp3")
        self.assertEqual(self.morceaux(), ["ab.mp3"])


class TestSonPersonnel(unittest.TestCase):
    """Un son de la personne déposé dans DONNEES/sons remplace le son livré du même nom, tel quel."""
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.avant = web.DONNEES
        web.DONNEES = Path(self.dossier.name)

    def tearDown(self):
        web.DONNEES = self.avant
        self.dossier.cleanup()

    def test_remplacement(self):
        self.assertIsNone(web.son_personnel("sons/sphere.mp3"))
        (web.DONNEES / "sons").mkdir()
        (web.DONNEES / "sons" / "sphere.wav").write_bytes(b"RIFF....WAVE")
        self.assertEqual(web.son_personnel("sons/sphere.mp3").name, "sphere.wav")
        self.assertEqual(web.TYPES[".wav"], "audio/wav")
        self.assertIsNone(web.son_personnel("sons/element.mp3"))
        self.assertIsNone(web.son_personnel("sons/../sons/sphere.mp3"))
        self.assertIsNone(web.son_personnel("sons/inconnu.mp3"))
        (web.DONNEES / "sons" / "fin.wav").write_bytes(b"RIFF....WAVE")
        self.assertEqual(web.son_personnel("sons/fin.mp3").name, "fin.wav")


if __name__ == "__main__":
    unittest.main()
