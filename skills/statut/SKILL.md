---
name: statut
description: État d'un assistant installé par ottho-jarvis sans rien modifier - conteneurs, profil Hermes, routines, bot Telegram, interface, secrets présents (oui/non), dernières sauvegardes, contrôles réels. Déclencheurs - où en est mon assistant, est-ce que Jarvis marche, statut ottho-jarvis.
argument-hint: "[profil]"
---

# Statut

Lecture seule : aucune commande de ce skill ne modifie le serveur. Applique **[les règles permanentes](../../references/regles.md)**.

1. Lanceur `bash .ottho-jarvis/jarvis` (sinon étape 0 du skill `installer`). Profil : celui de `.ottho-jarvis/*.config.json`, ou demande-le.
2. `bash .ottho-jarvis/jarvis run statut <profil>` puis `bash .ottho-jarvis/jarvis run verifier <profil>`.
3. Résume en clair : ce qui marche, ce qui manque (jeton, mot de passe, redémarrage), avec la preuve de chaque point. Pour toute correction, passe au skill `depannage` ; ne modifie rien ici.
