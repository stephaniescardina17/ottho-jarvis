# Sons de l'interface : origines et licences

Sons discrets, coupés par le réglage « Sons de l'interface ».

| Fichier | Rôle | Origine | Licence |
| --- | --- | --- | --- |
| `sphere.mp3` | Allumage de la sphère (crête -20 dBFS) | Son original synthétisé de zéro par `fabrication.py` (« sphere_1b_balayage_lisse » : glissando montant, voile de bruit filtré, note cristalline lisse en fin, petit écho), converti en MP3 96 kb/s | Créé pour ottho-jarvis, aucun échantillon tiers |
| `element.mp3` | Apparition de chaque panneau au chargement (météo, rappels, tâches, brief), un cran plus haut à chaque panneau (crête -30 dBFS) | Son original synthétisé par `fabrication_hud.py` (bégaiement de données FM puis glissando descendant) | Créé pour ottho-jarvis, aucun échantillon tiers |
| `tic.mp3` | Barre de chargement : un tic toutes les 95 ms jusqu'à 100 % (crête -36 dBFS), joué par `preload.js` | Son original synthétisé par `fabrication_hud.py` | Créé pour ottho-jarvis, aucun échantillon tiers |
| `complet.mp3` | Barre de chargement à 100 % (crête -33 dBFS) | Son original synthétisé par `fabrication_hud.py` (deux glissandos croisés) | Créé pour ottho-jarvis, aucun échantillon tiers |
| `frappe.mp3` | Chaque lettre de la salutation écrite au clavier (crête -33 dBFS) | Son original synthétisé par `fabrication_hud.py` (clic de touche numérique) | Créé pour ottho-jarvis, aucun échantillon tiers |

`fabrication.py` régénère les sons candidats de la sphère (`python fabrication.py DOSSIER`), `fabrication_hud.py` les sons HUD (`python fabrication_hud.py DOSSIER [SPHERE.wav]`, écoute en situation si la sphère est donnée). Les deux demandent numpy et soundfile.

Aucun son n'est extrait d'un film, d'une bande-annonce ou d'une vidéo, ni n'imite un son de film reconnaissable.

Les sons HUD reprennent seulement le style d'une vidéo de référence (« Futuristic interface / HUD sound effects », GMCFiles) : rien n'en est extrait, tout est synthétisé.

## Sons personnels

Une personne peut remplacer un son livré par son propre fichier, joué tel quel : `jarvis.sh envoyer-son sphere|element|frappe|tic|complet|fin FICHIER PROFIL` (`fin` : joué quand tout est chargé ; aucun son livré pour ce moment) (WAV, MP3, M4A ou OGG, 5 Mo au plus). Le fichier est déposé dans les données de l'instance (`data/web/sons/`) et servi à la place du son livré. Il n'entre jamais dans le plugin ni dans son dépôt. Un son tiré d'une vidéo ou d'un film reste un usage personnel, sous la responsabilité de la personne : il n'est ni redistribué ni publié.

`fabrication_sphere2.py` : variantes synthétisées d'un allumage de sphère (2a, 2b) d'après l'analyse au spectrogramme d'une vidéo de référence, rien n'en est extrait. Non retenues le 2026-11-26 (un son personnel a été choisi).
