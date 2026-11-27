# Voix de Jarvis : origines et licences

Une seule voix pour l'accueil et les réponses, gratuite et utilisable dans un produit commercial, à condition de garder les mentions ci-dessous.

## Kyutai Pocket TTS

- Programme : [Pocket TTS](https://github.com/kyutai-labs/pocket-tts) de Kyutai, binaire officiel (version 4.0.1, binaire 3.3.0), licence MIT. Téléchargé et vérifié par empreinte SHA-256 à la construction de l'image.
- Modèle : `kyutai/pocket-tts-without-voice-cloning`, langue `french` ou `french_24l`, licence CC-BY 4.0 (Kyutai). Révisions figées par le binaire.

## Voix

- Homme : « peter_yearsley », voix intégrée au modèle, issue de [Voice-Zero](https://github.com/OwenTyme/voice-zero) (sélection d'enregistrements LibriVox), licence CC0.
- Femme : `femme-french.safetensors` et `femme-french_24l.safetensors`, états de voix exportés avec Pocket TTS à partir de l'enregistrement `cml-tts/fr/579_2548_000015-0001_enhanced.wav` du dépôt [kyutai/tts-voices](https://huggingface.co/kyutai/tts-voices), tiré du jeu de données [CML-TTS](https://www.openslr.org/146/) (lectures LibriVox), licence **CC-BY 4.0**. Attribution : CML-TTS, Oliveira et al., 2023 ; voix préparée par Kyutai.
  - Empreintes SHA-256 : `femme-french.safetensors` 5a9ddda8f87e9a77c64a7803536e97a520a6635b0acc3daf6acf95b962b0b272 ; `femme-french_24l.safetensors` 985d8bbf0bf5ee92ab4261ccd25df9ed82f00a348f5584626b76a86b812d4946.

## Règle

Aucune de ces voix n'imite une personne connue. Ne pas ajouter de voix clonée d'une personne réelle sans son accord écrit.
