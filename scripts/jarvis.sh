#!/usr/bin/env bash
# Lanceur local ottho-jarvis : relie l'ordinateur de la personne au kit sur son VPS.
#
#   jarvis.sh link                  crée le lanceur .ottho-jarvis/jarvis dans le dossier de travail
#   jarvis.sh apercu FICHIER        génère en local (personnalité, compose…) sans toucher au VPS
#   jarvis.sh cible HOTE            mémorise la cible SSH (alias de ~/.ssh/config ou user@ip)
#   jarvis.sh envoyer-kit           copie le kit dans /opt/ottho-jarvis sur le VPS
#   jarvis.sh envoyer-config FICHIER PROFIL
#                                   dépose jarvis.config.json pour ce profil
#   jarvis.sh envoyer-musique FICHIER PROFIL
#                                   copie le MP3 de la personne (musique d'ouverture de
#                                   l'interface) dans data/web/musique/ de ce profil
#   jarvis.sh envoyer-son NOM FICHIER PROFIL
#                                   son personnel joué tel quel à la place du son livré
#                                   (sphere, element, frappe, tic, complet, fin), dans data/web/sons/
#   jarvis.sh run COMMANDE…         lance « ottho-jarvis COMMANDE… » sur le VPS (sudo)
#   jarvis.sh cmd COMMANDE…         affiche la commande à lancer soi-même (saisie de secrets)
#
# La cible est lue dans .ottho-jarvis/cible, sinon reprise de .ottho-hermes/state.json
# (parcours ottho-hermes-vps) quand il existe.
set -euo pipefail
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT="$ICI/../kit"
ETAT=".ottho-jarvis"

# sous Windows, « python3 » peut être un raccourci vide du Microsoft Store : on teste pour de vrai
trouver_python() {
  local p
  for p in python3 python py; do "$p" -c "" >/dev/null 2>&1 && { echo "$p"; return; }; done
  return 1
}

cible() {
  if [[ -f "$ETAT/cible" ]]; then cat "$ETAT/cible"; return; fi
  if [[ -f .ottho-hermes/state.json ]]; then
    local py
    py="$(trouver_python)" && "$py" -c 'import json;print(json.load(open(".ottho-hermes/state.json", encoding="utf-8"))["target"]["host"])' 2>/dev/null | tr -d '\r' && return
  fi
  echo "Aucune cible : lance d'abord « jarvis.sh cible HOTE »." >&2
  exit 2
}

ssh_opts=(-o ConnectTimeout=15 -o ServerAliveInterval=20)

case "${1:-}" in
  link)
    # lanceur stable dans le dossier de travail : suit les mises à jour du plugin
    mkdir -p "$ETAT"
    {
      printf '#!/usr/bin/env bash\n'
      printf '# Lanceur ottho-jarvis, régénéré à chaque démarrage. Ne pas modifier.\n'
      printf 'exec bash %q "$@"\n' "$ICI/jarvis.sh"
    } > "$ETAT/jarvis"
    chmod +x "$ETAT/jarvis"
    echo "Lanceur prêt : bash $ETAT/jarvis"
    ;;
  apercu)
    # calcule les fichiers en local, sans toucher au serveur
    [[ -f "${2:-}" ]] || { echo "usage : jarvis.sh apercu FICHIER" >&2; exit 2; }
    PY="$(trouver_python)" || { echo "Python 3 introuvable sur cet ordinateur." >&2; exit 2; }
    OUT="$ETAT/apercu"
    mkdir -p "$OUT"
    PYTHONIOENCODING=utf-8 "$PY" -B "$KIT/generer.py" "$2" "$OUT" && echo "Aperçu dans $OUT (personnalité : $OUT/profil/SOUL.md)"
    ;;
  cible)
    [[ -n "${2:-}" ]] || { echo "usage : jarvis.sh cible HOTE" >&2; exit 2; }
    mkdir -p "$ETAT"
    printf '%s\n' "$2" > "$ETAT/cible"
    ssh "${ssh_opts[@]}" "$2" 'sudo -n true' && echo "Cible $2 : connexion et sudo sans mot de passe OK."
    ;;
  envoyer-kit)
    H="$(cible)"
    # extraction directe (pas de copie temporaire) ; instances/ et sauvegardes/ ne sont jamais touchés
    tar -C "$KIT" --exclude='__pycache__' --exclude='exemples' -czf - bin services web generer.py | ssh "${ssh_opts[@]}" "$H" '
      set -e
      sudo mkdir -p /opt/ottho-jarvis
      sudo chmod 700 /opt/ottho-jarvis
      sudo tar -xzf - -C /opt/ottho-jarvis --no-same-owner
      # fins de ligne Linux, même si le kit a été copié ou modifié sous Windows (sinon « python3 » suivi d un retour chariot est introuvable)
      sudo find /opt/ottho-jarvis/bin /opt/ottho-jarvis/services /opt/ottho-jarvis/web /opt/ottho-jarvis/generer.py -type f ! -name "*.mp3" ! -name "*.safetensors" ! -name "*.png" -exec sed -i "s/\r$//" {} +
      sudo chmod 755 /opt/ottho-jarvis/bin/ottho-jarvis
      echo "Kit installé dans /opt/ottho-jarvis."'
    ;;
  envoyer-config)
    [[ -f "${2:-}" && -n "${3:-}" ]] || { echo "usage : jarvis.sh envoyer-config FICHIER PROFIL" >&2; exit 2; }
    [[ "$3" =~ ^[a-z][a-z0-9-]{1,30}$ ]] || { echo "Nom de profil invalide." >&2; exit 2; }
    H="$(cible)"
    ssh "${ssh_opts[@]}" "$H" "sudo mkdir -p /opt/ottho-jarvis/instances/$3 && sudo tee /opt/ottho-jarvis/instances/$3/jarvis.config.json >/dev/null" < "$2"
    echo "Configuration déposée : /opt/ottho-jarvis/instances/$3/jarvis.config.json"
    ;;
  envoyer-musique)
    # musique d'ouverture : le fichier de la personne (acheté, ou extrait de ses CD), jamais
    # une musique tirée d'une vidéo en ligne. Lue par l'interface à l'ouverture (musique.auto).
    F="${2:-}"; P="${3:-}"
    [[ -f "$F" && -n "$P" ]] || { echo "usage : jarvis.sh envoyer-musique FICHIER PROFIL" >&2; exit 2; }
    [[ "$P" =~ ^[a-z][a-z0-9-]{1,30}$ ]] || { echo "Nom de profil invalide." >&2; exit 2; }
    NOM="$(basename "$F")"
    EXT="$(printf '%s' "${NOM##*.}" | tr '[:upper:]' '[:lower:]')"
    [[ "$EXT" == "mp3" || "$EXT" == "m4a" || "$EXT" == "ogg" ]] || { echo "Format non pris en charge : MP3, M4A ou OGG." >&2; exit 2; }
    TAILLE=$(wc -c < "$F" | tr -d ' ')
    (( TAILLE > 1000 && TAILLE <= 10485760 )) || { echo "Fichier vide ou trop gros (10 Mo au plus)." >&2; exit 2; }
    # vrai fichier audio ? (en-tête ID3 ou trame MP3, « ftyp » pour M4A, « OggS » pour OGG)
    TETE=$(head -c 12 "$F" | od -An -tx1 | tr -d ' \n')
    case "$EXT:$TETE" in
      mp3:494433*|mp3:fff*|mp3:ffe*) ;;
      m4a:????????66747970*) ;;
      ogg:4f676753*) ;;
      *) echo "Ce fichier ne ressemble pas à un $EXT valide." >&2; exit 2 ;;
    esac
    # nom propre : « Artiste - Titre.ext » conseillé ; caractères de contrôle et « / » retirés
    NOM="$(printf '%s' "$NOM" | tr -d '\000-\037/\\' | cut -c1-120)"
    H="$(cible)"
    DOSSIER="/opt/ottho-jarvis/instances/$P/data/web/musique"
    DEST="$(printf '%q' "$DOSSIER/$NOM")"
    ssh "${ssh_opts[@]}" "$H" "sudo test -d $DOSSIER" < /dev/null || { echo "Interface du profil $P absente : installe-la d'abord." >&2; exit 2; }
    # un seul morceau gardé, comme depuis Réglages > Musique : le nouveau remplace le précédent
    ssh "${ssh_opts[@]}" "$H" "sudo tee $DEST >/dev/null && sudo chown --reference=$DOSSIER $DEST && sudo chmod 640 $DEST && sudo find $DOSSIER -maxdepth 1 -type f \( -iname '*.mp3' -o -iname '*.m4a' -o -iname '*.ogg' \) ! -name $(printf '%q' "$NOM") -delete" < "$F"
    echo "Musique déposée : $NOM ($(( TAILLE / 1024 )) Ko). Elle se lance à l'ouverture de l'interface (option « Lancer la musique à l'ouverture »)."
    ;;
  envoyer-son)
    # son personnel qui remplace un son livré (sphere, element, frappe, tic, complet, fin), joué tel quel.
    # Le fichier reste dans les données de l'instance : jamais dans le plugin ni dans son dépôt.
    # Un son tiré d'une vidéo ou d'un film n'est que pour un usage personnel, sous la responsabilité de la personne.
    NOMSON="${2:-}"; F="${3:-}"; P="${4:-}"
    [[ "$NOMSON" =~ ^(sphere|element|frappe|tic|complet|fin)$ && -f "$F" && -n "$P" ]] || { echo "usage : jarvis.sh envoyer-son sphere|element|frappe|tic|complet|fin FICHIER PROFIL" >&2; exit 2; }
    [[ "$P" =~ ^[a-z][a-z0-9-]{1,30}$ ]] || { echo "Nom de profil invalide." >&2; exit 2; }
    EXT="$(printf '%s' "${F##*.}" | tr '[:upper:]' '[:lower:]')"
    TAILLE=$(wc -c < "$F" | tr -d ' ')
    (( TAILLE > 1000 && TAILLE <= 5242880 )) || { echo "Fichier vide ou trop gros (5 Mo au plus)." >&2; exit 2; }
    TETE=$(head -c 12 "$F" | od -An -tx1 | tr -d ' \n')
    case "$EXT:$TETE" in
      wav:52494646????????57415645*) ;;
      mp3:494433*|mp3:fff*|mp3:ffe*) ;;
      m4a:????????66747970*) ;;
      ogg:4f676753*) ;;
      *) echo "Format non pris en charge ou fichier invalide : WAV, MP3, M4A ou OGG." >&2; exit 2 ;;
    esac
    H="$(cible)"
    BASE="/opt/ottho-jarvis/instances/$P/data/web"
    ssh "${ssh_opts[@]}" "$H" "sudo test -d $BASE" < /dev/null || { echo "Interface du profil $P absente : installe-la d'abord." >&2; exit 2; }
    ssh "${ssh_opts[@]}" "$H" "sudo install -d -m 700 -o \$(sudo stat -c %u $BASE) -g \$(sudo stat -c %g $BASE) $BASE/sons && sudo find $BASE/sons -maxdepth 1 -type f -name '$NOMSON.*' ! -name '$NOMSON.$EXT' -delete && sudo tee $BASE/sons/$NOMSON.$EXT >/dev/null && sudo chown --reference=$BASE $BASE/sons/$NOMSON.$EXT && sudo chmod 640 $BASE/sons/$NOMSON.$EXT" < "$F"
    echo "Son personnel déposé : $NOMSON.$EXT ($(( TAILLE / 1024 )) Ko). Il remplace le son livré au prochain chargement de l'interface."
    ;;
  run)
    shift; H="$(cible)"
    args=$(printf '%q ' "$@")
    ssh "${ssh_opts[@]}" "$H" "sudo /opt/ottho-jarvis/bin/ottho-jarvis $args"
    ;;
  cmd)
    shift; H="$(cible)"
    printf 'ssh -t %s sudo /opt/ottho-jarvis/bin/ottho-jarvis %s\n' "$H" "$*"
    ;;
  *)
    sed -n '2,15p' "$0"; exit 2 ;;
esac
