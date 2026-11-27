"""Tests du générateur : python -m unittest discover -s tests"""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "kit"))
import generer  # noqa: E402

EXEMPLES = RACINE / "kit" / "exemples"


def config(nom: str) -> dict:
    return json.loads((EXEMPLES / nom).read_text(encoding="utf-8"))


class TestValidation(unittest.TestCase):
    def test_exemples_valides(self):
        for f in EXEMPLES.glob("*.json"):
            with self.subTest(f.name):
                generer.charger(config(f.name))

    def test_prenom_obligatoire_si_adresse_par_prenom(self):
        c = config("config-minimale.json")
        c["utilisateur"]["prenom"] = ""
        with self.assertRaises(generer.ConfigInvalide):
            generer.charger(c)

    def test_rubrique_libre_sans_consigne(self):
        c = config("config-minimale.json")
        c["brief"]["rubriques"].append({"id": "sport", "titre": "Sport", "actif": True})
        with self.assertRaisesRegex(generer.ConfigInvalide, "Sport"):
            generer.charger(c)

    def test_domaine_obligatoire_si_interface(self):
        c = config("config-minimale.json")
        c["interface"] = {"active": True, "domaine": "pas un domaine"}
        with self.assertRaisesRegex(generer.ConfigInvalide, "domaine"):
            generer.charger(c)

    def test_chemins_et_noms_docker_controles(self):
        for cle, val in [("donnees", "relatif/data"), ("conteneur", "nom avec espace"), ("profil", "Majuscules")]:
            c = config("config-stephanie.json")
            c["hermes"][cle] = val
            with self.subTest(cle), self.assertRaises(generer.ConfigInvalide):
                generer.charger(c)

    def test_injection_dans_compose_refusee(self):
        c = config("config-stephanie.json")
        c["second_cerveau"]["chemin"] = "/a:/etc:rw\n  privileged: true"
        with self.assertRaises(generer.ConfigInvalide):
            generer.charger(c)


class TestPersonnalite(unittest.TestCase):
    def test_vouvoiement_madame(self):
        s = generer.soul(generer.charger(config("config-stephanie.json")))
        self.assertIn("**vouvoies** Stéphanie", s)
        self.assertIn("« Madame »", s)
        self.assertIn("Bonjour Madame.", s)
        self.assertIn("« Vous préférez… »", s)
        self.assertIn("### Second cerveau", s)
        self.assertIn("## Cartes pour l'interface web", s)
        self.assertIn("Il vous reste 2 tâches.", s)
        self.assertIn("7 h 30", s)
        self.assertIn("« merci Jarvis »", s)                 # fin de conversation : formule de politesse
        self.assertIn("« Je vous en prie, Madame. »", s)
        self.assertIn("« C'est moi qui vous remercie. »", s)
        self.assertNotIn("t'en prie", s)                     # aucune formule du tutoiement

    def test_tutoiement_prenom_sans_second_cerveau(self):
        s = generer.soul(generer.charger(config("config-minimale.json")))
        self.assertIn("**tutoies** Camille", s)
        self.assertIn("Bonjour Camille.", s)
        self.assertIn("« Tu préfères… »", s)
        self.assertIn("« Je t'en prie, Camille. »", s)
        self.assertIn("« Y'a pas de quoi. »", s)
        self.assertIn("« C'est moi qui te remercie. »", s)
        self.assertNotIn("vous en prie", s)                  # aucune formule du vouvoiement
        self.assertNotIn("À votre service", s)
        self.assertNotIn("Second cerveau", s)
        self.assertNotIn("second cerveau se lit", s)
        self.assertNotIn("## Le point du soir", s)
        self.assertNotIn("Cartes pour l'interface", s)
        self.assertIn("**Bourse** : le cours de clôture du CAC 40", s)
        self.assertIn("Ne jamais contacter mes clients directement.", s)
        self.assertIn("8 h", s)

    def test_madame(self):
        c = config("config-minimale.json")
        c["utilisateur"] = {"prenom": "", "adresse": "civilite", "civilite": "Madame", "tutoiement": False}
        s = generer.soul(generer.charger(c))
        self.assertIn("« Madame »", s)
        self.assertIn("Bonjour Madame.", s)


class TestFichiers(unittest.TestCase):
    def test_generation_complete(self):
        with tempfile.TemporaryDirectory() as d:
            resume = generer.generer(config("config-stephanie.json"), d)
            p = Path(d)
            for f in ["profil/SOUL.md", "profil/reglages.json", "services/compose.yml", "routines.json",
                      "web/jarvis.config.json", "resume.json"]:
                self.assertTrue((p / f).is_file(), f)
            self.assertEqual(resume["interface"], "https://jarvis.srv1234567.hstgr.cloud")
            publique = (p / "web/jarvis.config.json").read_text(encoding="utf-8")
            self.assertNotIn("/docker", publique)          # aucun chemin du serveur côté navigateur
            self.assertNotIn("hermes", json.loads(publique))

    def test_compose_avec_et_sans_interface(self):
        avec = generer.compose(generer.charger(config("config-stephanie.json")))
        self.assertIn("container_name: jarvis-web", avec)
        self.assertIn("Host(`jarvis.srv1234567.hstgr.cloud`)", avec)
        self.assertIn("/srv/second-cerveau/savoir:/savoir:ro", avec)
        self.assertIn("/docker/hermes-agent-abcd/data/profiles/jarvis/cron:/hermes/cron:ro", avec)
        self.assertNotIn(".env:/", avec)                   # le .env du profil n'est jamais monté
        sans = generer.compose(generer.charger(config("config-minimale.json")))
        self.assertNotIn("web:", sans)
        self.assertNotIn("traefik", sans)
        self.assertNotIn("/savoir:ro", sans)
        self.assertIn("name: ottho-equipes", sans)

    def test_voix_homme_femme_et_options(self):
        c = config("config-stephanie.json")
        homme = generer.compose(generer.charger(c))
        self.assertIn("POCKET_VOIX=peter_yearsley", homme)
        self.assertIn("POCKET_LANGUE=french", homme)
        self.assertIn("VOIX_URL=http://jarvis-voix:8730", homme)
        self.assertIn("mem_limit: 768m", homme)
        for absent in ("ELEVENLABS", "PIPER"):
            self.assertNotIn(absent, homme)
        c["interface"].update(genre_voix="femme", modele_voix="french_24l")
        femme = generer.compose(generer.charger(c))
        self.assertIn("POCKET_VOIX=peter_yearsley", femme)          # Pocket démarre toujours en voix d'homme
        self.assertEqual(generer.config_publique(generer.charger(c))["genre_voix"], "femme")   # voix par défaut de l'interface
        self.assertIn("mem_limit: 1280m", femme)
        c["interface"]["voix_locale"] = False
        sans = generer.compose(generer.charger(c))
        self.assertNotIn("jarvis-voix", sans)
        # double authentification : « maintenant » par défaut, transmise à l'interface
        self.assertIn("JARVIS_2FA=maintenant", homme)
        c["interface"]["deux_facteurs"] = "plus_tard"
        self.assertIn("JARVIS_2FA=plus_tard", generer.compose(generer.charger(c)))
        for cle, val in (("genre_voix", "robot"), ("modele_voix", "english"), ("deux_facteurs", "jamais")):
            mauvais = copy.deepcopy(c)
            mauvais["interface"][cle] = val
            with self.assertRaisesRegex(generer.ConfigInvalide, cle):
                generer.charger(mauvais)
        # chaque voix référencée est livrée avec le kit
        for modele in ("french", "french_24l"):
            self.assertTrue((RACINE / "kit/services/voix-pocket" / f"femme-{modele}.safetensors").is_file())

    def test_nombres_en_lettres(self):
        sys.path.insert(0, str(RACINE / "kit" / "services"))
        import voix
        # voix de femme : un champ voice_url vers l'état livré ; voix d'homme : voix par défaut de Pocket
        voix.VOIX_DIR = str(RACINE / "kit" / "services" / "voix-pocket")
        self.assertIsNone(voix.url_voix("homme"))
        self.assertTrue(voix.url_voix("femme").endswith(f"/etats/femme-{voix.POCKET_LANGUE}.safetensors"))
        corps, _ = voix.multipart("Bonjour.", voix.url_voix("femme"))
        self.assertIn(b'name="voice_url"', corps)
        self.assertNotIn(b"voice_url", voix.multipart("Bonjour.")[0])
        # conteneur : HOME=/nonexistent en lecture seule → le cache des voix de Pocket va dans /tmp
        ancien = os.environ.get("HOME")
        try:
            os.environ["HOME"] = "/nonexistent"
            env = voix.env_pocket()
            self.assertTrue(os.access(env["HOME"], os.W_OK))
            self.assertTrue(env["XDG_CACHE_HOME"].startswith(env["HOME"]) or "XDG_CACHE_HOME" in os.environ)
        finally:
            if ancien is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = ancien
        # Pocket TTS lit les chiffres en charabia : tout passe en lettres
        attendus = {0: "zéro", 21: "vingt et un", 71: "soixante et onze", 80: "quatre-vingts", 81: "quatre-vingt-un",
                    99: "quatre-vingt-dix-neuf", 200: "deux cents", 201: "deux cent un", 1000: "mille",
                    80000: "quatre-vingt mille", 2500000: "deux millions cinq cent mille"}
        for n, mots in attendus.items():
            self.assertEqual(voix.nombre_en_lettres(n), mots)
        self.assertEqual(voix.texte_lisible("Il est 21 heures 5. Il fait -3 degrés. 1 tâche, 12,5 km/h, 85 %."),
                         "Il est vingt et une heures cinq. Il fait moins trois degrés. une tâche, "
                         "douze virgule cinq kilomètres heure, quatre-vingt-cinq pour cent.")
        self.assertNotRegex(voix.texte_lisible("À Nice, il est 14 h 25, 22°C."), r"\d")
        # « h » des heures lu « heure(s) », jamais comme une lettre
        heures = {"Rendez-vous de 14 h avec John.": "Rendez-vous de quatorze heures avec John.",
                  "Réveil à 9h.": "Réveil à neuf heures.", "Retour 18h05.": "Retour dix-huit heures cinq.",
                  "À 1 h du matin": "À une heure du matin", "Point à 14:30.": "Point à quatorze heures trente.",
                  "À 12h00": "À douze heures", "4 hommes": "quatre hommes"}
        for brut, lu in heures.items():
            self.assertEqual(voix.texte_lisible(brut), lu)

    def test_routines(self):
        r = generer.routines(generer.charger(config("config-stephanie.json")))
        self.assertEqual([x["nom"] for x in r], ["brief-du-matin", "point-du-soir"])
        self.assertEqual(r[0]["horaire"], "30 7 * * *")
        self.assertEqual(r[1]["horaire"], "0 20 * * *")
        r2 = generer.routines(generer.charger(config("config-minimale.json")))
        self.assertEqual(len(r2), 1)
        self.assertIn("Bourse", r2[0]["consigne"])

    def test_reglages_ne_touchent_pas_au_modele(self):
        r = generer.reglages_profil(generer.charger(config("config-stephanie.json")))
        self.assertNotIn("model", r)
        self.assertIn("terminal", r["agent"]["disabled_toolsets"])
        self.assertEqual(r["approvals"]["cron_mode"], "deny")
        self.assertEqual(r["mcp_servers"]["jarvis"]["url"], "http://jarvis-services:8710/mcp")


if __name__ == "__main__":
    unittest.main()
