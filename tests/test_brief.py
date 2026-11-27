"""Brief du jour lu dans cron/output du profil, découpé par rubrique pour le panneau « Brief du matin ».
Sans Docker. python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "kit" / "services"))
os.environ.setdefault("WEB_DATA_DIR", tempfile.gettempdir())
import web  # noqa: E402

# format réel d'une sortie de la routine (2026-11-26)
SORTIE = """# Cron Job: brief-du-matin

**Job ID:** 381283301362
**Run Time:** 2026-11-26 07:30:32

## Prompt

[IMPORTANT: You are running as a scheduled cron job.]
Prépare et envoie le brief du matin de Monsieur : **Actualité de l'IA** comprise.

## Response

Bonjour Monsieur. Nous sommes jeudi 26 novembre.

**Météo à Nice** : ciel couvert, environ 8 °C au minimum et 13 °C au maximum.

**Rappels du jour** : rien de notable.

**Actualité de l'IA**
- OpenAI lance un nouveau modèle, à des prix en forte baisse (AIBriefs).
- Anthropic publie une nouvelle version de Claude (AIBriefs).
- **Nvidia** : changement à la tête de l'entreprise (CBS News).
"""


class TestBriefDuJour(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.avant = web.HERMES
        web.HERMES = Path(self.dossier.name)
        (web.HERMES / "cron" / "output" / "381283301362").mkdir(parents=True)
        (web.HERMES / "cron" / "jobs.json").write_text(json.dumps(
            {"jobs": [{"id": "381283301362", "name": "brief-du-matin"}]}), encoding="utf-8")

    def tearDown(self):
        web.HERMES = self.avant
        self.dossier.cleanup()

    def sortie(self, jour, texte=SORTIE):
        (web.HERMES / "cron" / "output" / "381283301362" / f"{jour}_07-30-34.md").write_text(texte, encoding="utf-8")

    def test_brief_d_aujourd_hui(self):
        self.sortie("2020-01-01")
        self.sortie(datetime.now(web.TZ).date().isoformat())
        b = web.brief_du_jour()
        self.assertEqual(b["heure"], "07:30")
        ia = b["rubriques"][web._cle_titre("Actualité de l’IA")]   # apostrophe typographique de l'interface
        self.assertEqual(len(ia), 3)
        self.assertTrue(ia[0].startswith("OpenAI lance"))
        self.assertEqual(ia[2], "Nvidia : changement à la tête de l'entreprise (CBS News).")
        self.assertEqual(b["rubriques"]["meteo a nice"], ["ciel couvert, environ 8 °C au minimum et 13 °C au maximum."])
        self.assertNotIn("prepare et envoie", " ".join(b["rubriques"]))   # le prompt n'est pas lu

    def test_pas_encore_envoye(self):
        self.sortie("2020-01-01")
        self.assertIsNone(web.brief_du_jour())

    def test_sans_routine(self):
        (web.HERMES / "cron" / "jobs.json").write_text('{"jobs": []}', encoding="utf-8")
        self.assertIsNone(web.brief_du_jour())


if __name__ == "__main__":
    unittest.main()
