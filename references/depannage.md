# Dépannage

Commence toujours par `bash .ottho-jarvis/jarvis run statut PROFIL` puis `… run verifier PROFIL` (lecture seule). Corrige seulement ce qui est en échec, avec l'accord de la personne pour toute écriture.

| Symptôme | Cause probable | Que faire |
|---|---|---|
| Le bot ne répond pas | Jeton absent, Hermes pas redémarré, identifiant Telegram non autorisé, la personne n'a jamais appuyé sur **Démarrer** | `statut` (jeton présent ?) ; `cmd jeton-telegram` ; `run redemarrer-hermes` après accord ; vérifier `telegram.utilisateurs` ; demander d'ouvrir le bot et d'appuyer sur Démarrer. |
| « Chat not found » dans le journal | La personne n'a pas encore ouvert le bot | Normal avant le premier `/start`. |
| `verifier` : outils MCP à 0 | `<profil>-services` arrêté, jeton différent entre le profil et le service | `statut` ; relancer `installer` (il réécrit le jeton aux deux endroits). |
| Interface : 404 | Conteneur web pas encore sain (Traefik ignore un conteneur « starting »), domaine qui ne pointe pas vers le VPS | Attendre 30 s ; vérifier la résolution DNS du domaine. |
| Interface : « Jarvis est indisponible (502) » | API Hermes pas ouverte au réseau Docker, Hermes pas redémarré après l'installation | `verifier` (API joignable ?) ; `run redemarrer-hermes` après accord. |
| Interface : trop d'essais | 5 mots de passe faux en 15 minutes | Attendre un quart d'heure, ou `cmd mot-de-passe` (redémarre l'interface et lève le blocage). |
| Interface : « Code incorrect » à chaque essai | Heure du téléphone décalée (le code change toutes les 30 s), mauvais compte dans l'application | Régler le téléphone sur l'heure automatique ; vérifier le compte « <assistant> » dans l'application ; sinon un code de secours. |
| Interface : téléphone perdu, plus de code de secours | — | `cmd deux-facteurs-couper PROFIL` lancée par la personne (root sur le VPS), puis reconnexion et nouvelle activation. |
| Interface : la voix d'accueil n'est pas celle choisie | Le conteneur `<profil>-voix` répond 500 ou ne répond pas, l'interface repasse sur la voix du navigateur | `docker logs <profil>-voix` (« synthèse impossible : Pocket TTS a répondu 500 ») ; kit antérieur au 2026-11-26 : `envoyer-kit` puis `run installer` (cache de Pocket dans `/tmp`). |
| Interface : accueil et musique muets à la réouverture | Le navigateur bloque le son tant que la personne n'a rien touché (page rouverte déjà connectée) | Normal : ils partent au premier clic. Réglage par site pour l'éviter (skill `interface`, Musique). |
| Interface : MP3 refusé | Plus de 10 Mo, format autre que MP3/M4A/OGG, ou fichier qui n'est pas un vrai fichier audio | Le message dit lequel ; proposer un fichier plus léger (MP3 en 192 kbit/s : 10 Mo ≈ 7 min). |
| Interface : `/memory approve` sans effet | Les commandes `/` ne passent pas par l'API d'Hermes | Les envoyer sur Telegram. |
| `installer` : « Conflict. The container name … is already in use » | Une ancienne installation faite à la main utilise les mêmes noms (`<profil>-web`, `<profil>-services`) | Bascule : skill `installer`, « Un assistant existe déjà » (arrêter l'ancienne après plan et accord). |
| `cd /opt/ottho-jarvis/instances/<profil>` : Permission denied | Dossier en 700 (root) | `sudo docker compose --project-directory /opt/ottho-jarvis/instances/<profil> -f /opt/ottho-jarvis/instances/<profil>/compose.yml …` |
| Le brief n'arrive pas | Routine absente, jeton absent, fuseau | `verifier` (routines) ; `hermes -p PROFIL cron run <id>` pour tester tout de suite. |
| L'assistant refuse de lire une note | Note hors du dossier du second cerveau | Normal : seul ce dossier est lisible. Pour en changer, skill `personnaliser`. |
| Réponses en un bloc après quelques secondes | Le fournisseur du modèle (abonnement Claude par exemple) ne renvoie pas mot à mot | Normal ; l'orbe reste en « réflexion » pendant l'attente. |

Retour arrière : chaque `installer` laisse une archive dans `/opt/ottho-jarvis/sauvegardes/` (configuration du profil, `.env`, routines, compose). La restaurer se fait avec l'accord de la personne.
