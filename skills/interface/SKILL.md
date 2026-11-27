---
name: interface
description: Ajoute, déplace ou retire l'interface web d'un assistant installé par ottho-jarvis (orbe animée, discussion, tâches, rappels, mémoire, réglages), derrière Traefik en HTTPS et protégée par mot de passe et double authentification ; change le mot de passe ; coupe la double authentification (téléphone perdu) ; choisit la voix (homme ou femme) ; ajoute de la musique. Déclencheurs - interface web de mon assistant, changer le mot de passe de Jarvis, changer la voix de Jarvis, mettre de la musique.
argument-hint: "[ajouter | retirer | mot-de-passe | voix | musique]"
---

# Interface web

Applique **[les règles permanentes](../../references/regles.md)**. Lanceur : `bash .ottho-jarvis/jarvis`.

## Ajouter ou changer de domaine

1. `bash .ottho-jarvis/jarvis run detecter` : Traefik doit être présent (résolveur de certificats et point d'entrée HTTPS). Sans Traefik, l'interface n'est pas possible avec ce kit : propose le parcours ottho-hermes-vps (phase sécurité) et arrête-toi.
2. Adresse : un nom qui pointe vers le VPS, pas forcément un domaine acheté (Traefik aiguille par ce nom et lui obtient le certificat HTTPS ; une IP seule ne suffit pas). Propose `<assistant>.<nom déjà servi par Traefik>` ; vérifie qu'il pointe vers l'IP du VPS (résolution DNS). **Chez Hostinger, aucun domaine à acheter** : le VPS a déjà un nom, `srvNNNNNNN.hstgr.cloud` (nom d’hôte affiché dans hPanel, sur la page du VPS), et tout sous-nom comme `jarvis.srvNNNNNNN.hstgr.cloud` pointe déjà vers le VPS, sans aucun réglage DNS (constaté le 2026-11-26) ; vérifie-le quand même par une résolution DNS. Mets `interface.active: true`, `domaine`, `certresolver`, `entrypoint` dans `.ottho-jarvis/<profil>.config.json`.
3. Plan : nouveau conteneur `<profil>-web` sans port publié, route HTTPS sur le domaine, API d'Hermes ouverte au seul réseau Docker (redémarrage d'Hermes de 15 à 30 s si elle ne l'était pas). Accord, puis `envoyer-config` et `run installer` (voir skill `installer`, étape 5).
4. Mot de passe (étape suivante), redémarrage d'Hermes si `redemarrage_requis`, puis `run verifier <profil>` et connexion réelle dans un navigateur.

## Mot de passe

La personne lance dans **son** terminal la commande affichée par `bash .ottho-jarvis/jarvis cmd mot-de-passe <profil>` (12 caractères ou plus, saisie masquée). L'interface redémarre en quelques secondes ; toutes les connexions ouvertes sont fermées.

## Double authentification

Code à 6 chiffres d'une application d'authentification (Google Authenticator, 2FAS, Aegis, 1Password, Microsoft Authenticator…), demandé après le mot de passe, et 10 codes de secours à usage unique. Option `interface.deux_facteurs` : `maintenant` (défaut : activation obligatoire à la première connexion) ou `plus_tard` (rappel dans l'interface jusqu'à l'activation).

- **Activer** : la personne le fait elle-même dans son navigateur (page `/securite`, ou Réglages > Sécurité > Gérer) : mot de passe, QR code à scanner, premier code, puis codes de secours à garder. Tu ne vois jamais le secret ni les codes, et tu ne les demandes jamais.
- **Changer de téléphone** : page `/securite`, désactiver (mot de passe et code), puis réactiver.
- **Téléphone perdu** : se connecter avec un code de secours, puis désactiver et réactiver. Sans code de secours : la personne lance dans **son** terminal la commande affichée par `bash .ottho-jarvis/jarvis cmd deux-facteurs-couper <profil>` (accès root au VPS requis) ; elle se reconnecte avec le mot de passe et réactive.
- Chaque activation, désactivation ou changement de mot de passe ferme toutes les sessions ouvertes.
- `run statut <profil>` indique « activée » ou « à activer », jamais le secret.

## Voix

Une seule voix, la même pour l'accueil à la connexion et pour les réponses lues à voix haute : Kyutai Pocket TTS, locale et gratuite (aucun compte ni clé), dans le conteneur `<profil>-voix` (réseau interne seulement).

- **Accueil parlé** (case « M'accueillir à voix haute ») : préparé pendant le chargement de la page, il démarre avec l'apparition de la sphère.
- **Réponses lues à voix haute** (case « Lire les réponses à voix haute », ou bouton haut-parleur de la saisie) : l'interface découpe la réponse en morceaux de quelques phrases, prépare le suivant pendant que le précédent se lit.
- Les nombres sont écrits en lettres avant la synthèse (Pocket TTS lit les chiffres en charabia), et les heures aussi : « 14 h », « 9h », « 14 h 30 », « 18h05 », « 14:30 » deviennent « quatorze heures », « neuf heures »… (sinon Pocket lit « h » comme une lettre).
- Si le conteneur ne répond pas, l'interface repasse sur la voix du navigateur : une voix d'accueil qui ne ressemble pas à celle choisie est le signe d'une panne du conteneur (voir le dépannage).
- Pocket TTS garde chaque voix lue en cache dans `$HOME/.cache` ; dans le conteneur (utilisateur sans dossier personnel, disque en lecture seule), `voix.py` le place dans `/tmp`. Sans cela, la voix de femme échouait en 500.

Options (`.ottho-jarvis/<profil>.config.json`) : `interface.genre_voix` (voix par défaut : `homme`, « Peter Yearsley » ; `femme`, voix française de CML-TTS ; la personne en change elle-même dans Réglages > Voix, sans réinstaller), `interface.modele_voix` (`french`, léger ; `french_24l`, plus riche mais deux fois plus lent et gourmand), `interface.voix_locale` (vrai par défaut ; faux = voix du navigateur seulement). Mémoire du conteneur : ~300 Mo, pic ~530 Mo avec `french` (limite 768 Mo) ; ~565 Mo, pic ~1,1 Go avec `french_24l` (limite 1,28 Go). Changer de voix : modifier l'option, `envoyer-config`, `run installer` (reconstruit l'image si le modèle change).

**Parler à l'assistant (mode conversation).** Un clic sur le micro ouvre une conversation : la personne parle, l'assistant répond à voix haute, puis le micro se rouvre seul pour la suite. La conversation se ferme après 8 s sans parole, sur « merci <nom> » (l'assistant répond d'une seule formule de politesse, consigne de sa personnalité, avec parfois une pointe d'humour quand il connaît bien la personne) ou sur un nouveau clic. Tu ou vous : la personnalité (`SOUL.md`) garde le choix de l'installation, mais chaque demande de l'interface rappelle à l'assistant le réglage actuel (Réglages > « Tutoiement », formules de `kit/services/politesse.py`) ; sur Telegram, le choix de l'installation reste valable : pour le changer, `utilisateur.tutoiement` dans la configuration, `envoyer-config` puis `run installer`. La musique s'efface pendant l'écoute. La reconnaissance vocale est celle du navigateur (Web Speech) : Chrome, Edge et Safari l'ont ; Firefox et Zen ne l'ont pas, et le bouton micro y est masqué. Dans Chrome, la parole est transcrite par les serveurs de Google. Pas de mot d'éveil (« Hey Jarvis ») : il faudrait un micro ouvert en permanence, envoyé à Google dans Chrome, ou un détecteur local à licence ou compte (Porcupine, openWakeWord).

Ne clone jamais la voix d'une personne réelle (acteur, comédien de doublage, proche) : les voix livrées viennent de jeux de données libres (voir `kit/services/voix-pocket/LICENCES.md`).

## Musique

Aucune musique n'est livrée avec le plugin (droits d'auteur). La musique d'ouverture est le fichier de la personne (MP3 acheté ou extrait de ses CD ; jamais une musique tirée d'une vidéo en ligne ; tu n'en cherches ni n'en télécharges jamais). Demande le chemin du fichier sur son ordinateur, puis :

```bash
bash .ottho-jarvis/jarvis envoyer-musique "<chemin>/Artiste - Titre.mp3" <profil>
```

Le lanceur vérifie le format (MP3, M4A, OGG), la taille (10 Mo au plus) et l'en-tête du fichier, le copie dans `data/web/musique/` et le rend lisible par l'interface. Un seul morceau est gardé : le nouveau remplace le précédent (le serveur ne se remplit pas). La musique se lance à l'ouverture tant que l'option « Lancer la musique à l'ouverture » est cochée (`musique.auto`, vrai par défaut). La personne peut aussi changer de morceau elle-même dans Réglages > Musique > « Choisir un MP3 » : le fichier est envoyé au serveur (`POST /api/musique`, mêmes contrôles, 10 Mo au plus), gardé pour les prochaines ouvertures et remplace le précédent.

La musique part dès la fin du chargement, en même temps que l'accueil parlé, et s'efface sous la voix (puis remonte). **Limite des navigateurs** : aucun son n'est permis tant que la personne n'a rien touché sur la page. Après la saisie du mot de passe, tout part seul ; quand elle rouvre l'interface déjà connectée, accueil et musique attendent son premier clic ou sa première touche. Pour l'éviter : Firefox ou Zen, cadenas > Lecture automatique > « Autoriser l'audio et la vidéo » ; Safari, Réglages pour ce site > Lecture automatique ; Chrome n'a pas ce réglage (il l'accorde de lui-même à un site souvent utilisé).

## Sons personnels

Les sons livrés sont synthétisés pour le plugin (`kit/web/sons/LICENCES.md`). Tu n'extrais jamais toi-même un son d'une vidéo, d'un film ou d'un site. Si la personne veut un autre son pour un moment de l'interface (`sphere` : allumage de la sphère ; `element` : apparition des panneaux ; `frappe` : lettres de la salutation ; `tic` et `complet` : barre de chargement ; `fin` : quand tout est chargé, aucun son livré, joué seulement si la personne en dépose un), elle fournit son fichier, qui est joué tel quel :

```bash
bash .ottho-jarvis/jarvis envoyer-son sphere "<chemin>/son.wav" <profil>
```

Le lanceur accepte WAV, MP3, M4A et OGG (5 Mo au plus, en-tête vérifié). Il dépose le fichier dans `data/web/sons/` de l'instance, où il remplace l'ancien son personnel du même nom. Le serveur le sert à la place du son livré. Le fichier ne passe jamais dans le plugin ni dans son dépôt. Si c'est un extrait d'une vidéo ou d'un film, dis en une phrase qu'il reste un usage personnel : ni redistribué ni publié. Préviens aussi si son niveau est bien plus fort que les sons livrés : la sphère livrée a une crête à -20 dBFS. Pour revenir au son livré, retirer le fichier de `data/web/sons/` (en le mettant de côté, pas en le supprimant).

## Limites connues d'Hermes (constatées le 2026-11-26)

- **Telegram et l'interface sont deux fils séparés** : même agent, même mémoire durable, mêmes outils, mais chaque canal a sa conversation. L'API d'Hermes refuse d'écrire dans une session ouverte par Telegram (`X-Hermes-Session-Id` → 409 `permission_denied`) ; elle permet seulement de la lire.
- **`/memory approve`, `/memory pending` ne passent pas par l'interface** : Hermes ne traite les commandes `/` que dans les messageries (`memory_write_api: false` dans ses capacités). Les souvenirs en attente se valident sur Telegram.

## Retirer

Mets `interface.active: false`, plan (le conteneur `<profil>-web` s'arrête, la route disparaît ; l'API d'Hermes reste ouverte au seul réseau Docker, sans effet extérieur), accord, puis `envoyer-config` et `run installer`.
