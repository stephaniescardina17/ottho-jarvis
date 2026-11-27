"""Voyant Telegram de l'interface : lu dans le journal gateway.log du profil.
Sans Docker. python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "kit" / "services"))
os.environ.setdefault("WEB_DATA_DIR", tempfile.gettempdir())
import web  # noqa: E402

A = "WARNING hermes_plugins.platforms__telegram__home.adapter: [Telegram] "
I = "INFO hermes_plugins.platforms__telegram__home.adapter: [Telegram] "


class TestEtatTelegram(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.avant = web.HERMES
        web.HERMES = Path(self.dossier.name)
        (web.HERMES / "logs").mkdir()

    def tearDown(self):
        web.HERMES = self.avant
        self.dossier.cleanup()

    def etat(self, *lignes):
        (web.HERMES / "logs" / "gateway.log").write_text("\n".join(lignes) + "\n", encoding="utf-8")
        return web.etat_telegram()

    def test_sans_journal(self):
        self.assertEqual(web.etat_telegram(), "inconnu")

    def test_connecte(self):
        self.assertEqual(self.etat(I + "Connected to Telegram (polling mode)"), "ok")

    def test_coupure_passagere_puis_reprise(self):
        # séquence réelle du 2026-11-26 : Bad Gateway, Timed out, puis reprise seule
        self.assertEqual(self.etat(
            I + "Connected to Telegram (polling mode)",
            A + "Telegram network error, scheduling reconnect: Bad Gateway",
            A + "Telegram polling reconnect failed: Timed out",
            I + "Telegram polling restarted after network error (attempt 2); health pending getUpdates progress",
            I + "Telegram polling recovered: getUpdates progressing (generation 3)",
            I + "Sending response (216 chars) to 123",
        ), "ok")

    def test_coupure_en_cours(self):
        self.assertEqual(self.etat(
            I + "Connected to Telegram (polling mode)",
            A + "Telegram network error (attempt 1/10), reconnecting in 5s. Error: Bad Gateway",
        ), "coupe")


if __name__ == "__main__":
    unittest.main()
