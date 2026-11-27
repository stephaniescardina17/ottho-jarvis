# Le fichier `jarvis.config.json`

Source unique de l'installation d'un Jarvis. Le questionnaire du skill `installer` l'écrit ; `kit/generer.py` en tire tout le reste : la personnalité (`SOUL.md`), les réglages du profil Hermes, le `compose.yml` des services, les routines et la configuration publique de l'interface. Aucun secret n'y figure.

| Clé | Type | Défaut | Rôle |
|---|---|---|---|
| `version` | entier | `1` | Version du schéma. |
| `assistant.nom` | texte | `Jarvis` | Nom de l'assistant (personnalité, messages, voix). |
| `assistant.affiche` | texte | `J.A.R.V.I.S.` pour Jarvis, sinon le nom | Nom affiché dans l'interface et sur la page de connexion. La voix dit toujours `nom`. |
| `utilisateur.prenom` | texte | — | Prénom de la personne. |
| `utilisateur.adresse` | `civilite` \| `prenom` | `civilite` | Comment l'assistant s'adresse à elle. |
| `utilisateur.civilite` | `Monsieur` \| `Madame` | `Monsieur` | Utilisé si `adresse` vaut `civilite`. |
| `utilisateur.tutoiement` | booléen | `false` | Tutoiement ou vouvoiement. |
| `ton` | `concis` \| `equilibre` \| `bavard` | `equilibre` | Longueur des réponses. |
| `accent` | `cyan` \| `rouge` \| `vert` \| `ambre` \| `violet` | `cyan` | Couleur de l'interface (`bleu`, retiré, devient `cyan`). |
| `musique.auto` | booléen | `true` | Lance la musique d'ouverture de l'interface (si le navigateur l'autorise ; sinon au premier clic). Aucune musique n'est livrée : c'est le fichier de la personne, envoyé avec `jarvis.sh envoyer-musique`. |
| `voix` | booléen | `false` | Lecture des réponses à voix haute dans l'interface. |
| `interface.voix_locale` | booléen | `true` | Voix locale Kyutai Pocket TTS (conteneur `<profil>-voix`, ~300 Mo de mémoire) pour l'accueil et les réponses lues, gratuite et illimitée. Coupée : voix du navigateur. |
| `interface.genre_voix` | `homme` \| `femme` | `homme` | Voix par défaut de l'assistant : « Peter Yearsley » ou voix française de femme (CML-TTS). Modifiable à tout moment dans Réglages > Voix (la nouvelle voix se présente aussitôt) ; les deux voix sont dans l'image. |
| `interface.deux_facteurs` | `maintenant` \| `plus_tard` | `maintenant` | Double authentification de l'interface (code à 6 chiffres d'une application d'authentification, 10 codes de secours). `maintenant` : activation obligatoire à la première connexion. `plus_tard` : rappel dans l'interface jusqu'à l'activation. Une fois activée, chaque connexion demande le code. |
| `interface.modele_voix` | `french` \| `french_24l` | `french` | Modèle de la voix : léger (pic ~530 Mo) ou plus riche (pic ~1,1 Go, deux fois plus lent). |
| `accueil` | booléen | `true` | Accueil parlé à la connexion : heure, météo de la ville, nombre de tâches du jour. |
| `ville` | objet `{nom, lat, lon, fuseau}` | Paris | Météo et fuseau horaire. |
| `second_cerveau.actif` | booléen | `false` | Branche un dossier de notes en lecture seule. |
| `second_cerveau.chemin` | chemin sur le VPS | — | Dossier monté en lecture seule (ex. `/srv/second-cerveau/savoir`). Rien d'autre n'est lisible. |
| `brief.heure` | `HH:MM` | `07:30` | Heure du brief du matin. |
| `brief.rubriques` | liste `{id, titre, actif, consigne?}` | météo, rappels, tâches, actu IA | Rubriques du brief ; une rubrique ajoutée par la personne porte sa `consigne` (ce que l'assistant doit chercher). |
| `point_du_soir.actif` | booléen | `true` | Routine du soir : bilan des tâches et tâches de demain. |
| `point_du_soir.heure` | `HH:MM` | `20:00` | Heure du point du soir. |
| `garde_fous` | liste de textes | 5 règles de base | Règles ajoutées par la personne ; les règles de base restent toujours. |
| `telegram.actif` | booléen | `true` | Bot Telegram propre à l'assistant (jeton saisi par la personne). |
| `telegram.utilisateurs` | liste d'identifiants numériques | — | Seules ces personnes peuvent parler au bot (obtenir son identifiant : @userinfobot). Le premier reçoit les routines. |
| `interface.active` | booléen | `false` | Interface web derrière Traefik. |
| `interface.domaine` | nom (domaine ou sous-nom) | — | Ex. `jarvis.srvNNNNNNN.hstgr.cloud` (sous-nom du nom Hostinger du VPS, sans achat) ou `jarvis.mon-domaine.fr` ; doit pointer vers le VPS. |
| `interface.certresolver` | texte | `letsencrypt` | Résolveur de certificats de Traefik. |
| `interface.entrypoint` | texte | `websecure` | Point d'entrée HTTPS de Traefik. |
| `hermes.conteneur` | texte | détecté | Conteneur Hermes qui accueille le profil. |
| `hermes.reseau` | texte | détecté | Réseau Docker de ce conteneur. |
| `hermes.donnees` | chemin sur le VPS | détecté | Dossier monté sur `/opt/data` dans le conteneur. |
| `hermes.profil` | texte | `jarvis` | Nom du profil Hermes (minuscules, sans espace). |
| `hermes.port_api` | entier | `8642` | Port de l'API Hermes dans le conteneur. |
