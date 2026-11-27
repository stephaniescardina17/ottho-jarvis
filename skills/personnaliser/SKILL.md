---
name: personnaliser
description: Modifie un assistant installé par ottho-jarvis déjà installé - son nom, sa façon de s'adresser à la personne (Monsieur, Madame, prénom, tutoiement), son ton, sa ville, les rubriques et l'heure du brief, le point du soir, les garde-fous, le second cerveau, les personnes autorisées sur Telegram. Déclencheurs - changer mon assistant, ajouter une rubrique au brief, tutoie-moi, changer de ville.
argument-hint: "[profil]"
---

# Personnaliser l'assistant

Applique **[les règles permanentes](../../references/regles.md)**. Lanceur : `bash .ottho-jarvis/jarvis` (sinon étape 0 du skill `installer`).

1. Repère le profil (`.ottho-jarvis/<profil>.config.json`). Absent en local : `bash .ottho-jarvis/jarvis run statut <profil>` et, avec l'accord de la personne, récupère `/opt/ottho-jarvis/instances/<profil>/jarvis.config.json` par SSH.
2. Demande ce qui doit changer ; une question à la fois, en suivant **[le questionnaire](../../references/questionnaire.md)** pour les valeurs possibles. Modifie le fichier local.
3. `bash .ottho-jarvis/jarvis apercu .ottho-jarvis/<profil>.config.json` et montre ce qui change dans la personnalité (`.ottho-jarvis/apercu/profil/SOUL.md`).
4. Plan en une phrase (ce qui change, coupure éventuelle, retour arrière par la sauvegarde automatique), accord, puis :
   ```bash
   bash .ottho-jarvis/jarvis envoyer-config .ottho-jarvis/<profil>.config.json <profil>
   bash .ottho-jarvis/jarvis run installer /opt/ottho-jarvis/instances/<profil>/jarvis.config.json
   ```
5. Les changements de personnalité s'appliquent à la prochaine conversation, sans redémarrage. Un redémarrage d'Hermes est nécessaire seulement si `installer` le signale (`redemarrage_requis`) : annonce la coupure et attends l'accord.
6. Horaire d'une routine changé : `installer` garde la routine existante. Avec l'accord de la personne, supprime-la dans Hermes (`hermes -p <profil> cron remove <id>`, via le skill `depannage`) puis relance `installer`.
7. `bash .ottho-jarvis/jarvis run verifier <profil>` et un message réel pour constater le changement.
