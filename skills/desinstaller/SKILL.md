---
name: desinstaller
description: Arrête un assistant installé par ottho-jarvis en gardant ses données (tâches, réglages, sauvegardes), et sur demande explicite supprime aussi son profil Hermes. Déclencheurs - désinstaller Jarvis, arrêter mon assistant, supprimer ottho-jarvis.
argument-hint: "[profil]"
---

# Désinstaller

Applique **[les règles permanentes](../../references/regles.md)**. Lanceur : `bash .ottho-jarvis/jarvis`.

1. `bash .ottho-jarvis/jarvis run statut <profil>` pour montrer ce qui est installé.
2. Demande ce que la personne veut :
   - **Arrêter** (par défaut) : les conteneurs `<profil>-services` et `<profil>-web` s'arrêtent, la route HTTPS disparaît. Le profil Hermes, son bot et ses routines restent (le bot répond toujours, sans les outils de tâches ni le second cerveau). Les données restent dans `/opt/ottho-jarvis/instances/<profil>`.
   - **Supprimer aussi le profil Hermes** : le bot, les routines, la mémoire et les skills de l'assistant disparaissent. Seulement sur demande explicite ; la configuration est archivée avant.
3. Plan (ce qui s'arrête, ce qui reste, comment réinstaller : skill `installer` avec le même fichier de configuration), accord explicite, puis :
   ```bash
   bash .ottho-jarvis/jarvis run desinstaller <profil>
   # ou, sur demande explicite :
   bash .ottho-jarvis/jarvis run desinstaller <profil> --profil-hermes
   ```
4. Constat : `run statut <profil>` (conteneurs arrêtés) ; la personne vérifie que ses autres bots Hermes répondent toujours. Le dossier du kit et les sauvegardes restent sur le serveur ; ne les efface pas.
