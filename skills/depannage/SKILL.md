---
name: depannage
description: Diagnostic et correction des pannes d'un assistant installé par ottho-jarvis - bot Telegram muet, brief qui n'arrive pas, interface en erreur (404, 502, trop d'essais), outils absents, second cerveau inaccessible. Déclencheurs - mon assistant ne répond pas, Jarvis est en panne, l'interface ne marche pas.
argument-hint: "[symptôme]"
---

# Dépannage

Applique **[les règles permanentes](../../references/regles.md)**. Lanceur : `bash .ottho-jarvis/jarvis`.

1. Constat en lecture seule : `bash .ottho-jarvis/jarvis run statut <profil>` et `… run verifier <profil>`. Note chaque contrôle en échec.
2. Cherche la cause dans **[le tableau de dépannage](../../references/depannage.md)**. Si besoin, lis les journaux sans afficher de secret : `ssh HOTE "sudo docker logs --tail 60 <profil>-web"`, `… <profil>-services`, et la fin de `<dossier Hermes>/profiles/<profil>/logs/gateway.log` filtrée sur `ERROR|Telegram|mcp` (masque toute valeur qui ressemble à un jeton).
3. Propose **une** correction à la fois : ce qui change, ce qui peut couper, comment revenir en arrière. Accord, puis applique (le plus souvent : relancer `installer`, saisir un secret, `redemarrer-hermes`).
4. Revérifie (`verifier` et un vrai message). Si deux corrections n'ont rien changé, arrête-toi, résume ce qui a été observé et essayé, et demande comment continuer.
