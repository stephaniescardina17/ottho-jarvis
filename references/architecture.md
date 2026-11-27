# Architecture d'une installation

```
Ordinateur de la personne                 VPS
─────────────────────────                 ───────────────────────────────────────────────────
.ottho-jarvis/                            /opt/ottho-jarvis/            (kit, root, 700)
  jarvis        lanceur                     bin/ottho-jarvis            commandes du kit
  cible         hôte SSH                    generer.py, services/, web/
  <profil>.config.json  réponses            instances/<profil>/         une installation
                                              jarvis.config.json        source unique
                                              compose.yml, .env (600)   généré, secrets générés
                                              data/                     tâches du jour (65534)
                                              data/web/                 réglages, musique (uid Hermes)
                                            sauvegardes/                archives avant chaque écriture

                                          Conteneur Hermes existant (détecté)
                                            profil <profil> : SOUL.md, config.yaml fusionné,
                                            .env (clés, Telegram), routines
                                            API /p/<profil>/v1 (clé propre au profil)

                                          <profil>-services  MCP interne : tâches, second cerveau (ro)
                                          <profil>-web       interface, derrière Traefik (option)
```

- Les conteneurs du kit sont sur le réseau du conteneur Hermes, sans aucun port publié. Seule l'interface passe par Traefik, en HTTPS.
- `<profil>-web` lit en lecture seule les dossiers `cron`, `memories`, `pending` et `skills` du profil, jamais son `.env`.
- L'interface parle à Hermes par son API interne ; si elle est active, l'API d'Hermes écoute sur le réseau Docker (`API_SERVER_HOST=0.0.0.0` dans le profil `default`), toujours fermée à Internet. Chaque profil a sa clé : celle de l'assistant n'ouvre que son profil.
- Le modèle et le fournisseur viennent du profil `default` copié à la création ; le kit n'y touche jamais.
