# Notes formateur

## Diffuser

Dépôt public `stephaniescardina17/ottho-jarvis` : l'installation ne demande aucun jeton.

```bash
claude plugin marketplace add stephaniescardina17/ottho-jarvis && claude plugin install ottho-jarvis@ottho
codex plugin marketplace add stephaniescardina17/ottho-jarvis && codex plugin add ottho-jarvis@ottho
```

## Publier une nouvelle version

- Monter `version` dans `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json` et `VERSION_KIT` dans `kit/generer.py` (le nom d'image `ottho-jarvis:<version>` en dépend).
- Les skills n'utilisent `${CLAUDE_PLUGIN_ROOT}` qu'à l'étape 0 du skill `installer` ; ensuite tout passe par le lanceur `.ottho-jarvis/jarvis`.
- Contrôles avant publication :
  ```bash
  python -m unittest discover -s tests
  claude plugin validate . --strict
  bash -n scripts/jarvis.sh
  ```
- Essai de bout en bout sur une machine jetable avec Hermes, puis sur un VPS réel : `verifier` au vert et un message réel au bot.

## Versions épinglées à surveiller

| Élément | Où | Valeur |
|---|---|---|
| Image de base des services | `kit/services/Dockerfile` | `python:3.12-slim` |
| three.js (orbe) | `kit/web/index.html` (importmap) | `0.170.0` sur cdn.jsdelivr.net |
| Polices | `kit/web/index.html` | Google Fonts (Instrument Serif, JetBrains Mono, Space Grotesk) |
