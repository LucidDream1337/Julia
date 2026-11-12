#!/usr/bin/env bash
# Setup für Julia (Ollama mit GPU, Open WebUI, Qdrant, Wissens-Service).
#
# Prüft Voraussetzungen, legt Verzeichnisse und .env an, baut das Service-Image auf dem Host
# und validiert die Compose-Datei. Fremde Container (Jellyfin, Valheim, Dockhand, ...) werden
# nicht angefasst.
#
# Aufruf:  ./setup.sh [--no-build] [--up] [--help]
#   --no-build  Service-Image nicht neu bauen
#   --up        Stack nach erfolgreichem Setup direkt per "docker compose up -d" starten
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="julia-service:1.0"
ENV_FILE="$PROJECT_DIR/.env"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yaml"
OUR_CONTAINERS=(julia-ollama julia-init julia-qdrant julia-service julia-webui)

DO_BUILD=1
DO_UP=0
for arg in "$@"; do
  case "$arg" in
    --no-build) DO_BUILD=0 ;;
    --up) DO_UP=1 ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "Unbekannte Option: $arg" >&2; exit 2 ;;
  esac
done

if [ -t 1 ]; then G=$'\e[32m'; Y=$'\e[33m'; R=$'\e[31m'; N=$'\e[0m'; else G=""; Y=""; R=""; N=""; fi
ok()   { echo "${G}[ OK ]${N} $*"; }
warn() { echo "${Y}[WARN]${N} $*"; }
fail() { echo "${R}[FEHL]${N} $*" >&2; exit 1; }
step() { echo; echo "== $* =="; }

# ---------------------------------------------------------------- 1. Voraussetzungen
step "1/5 Voraussetzungen prüfen"
command -v docker >/dev/null 2>&1 || fail "Docker ist nicht installiert."
docker info >/dev/null 2>&1 || fail "Docker-Daemon nicht erreichbar (läuft er? sudo verwenden oder Benutzer zur Gruppe 'docker' hinzufügen)."
ok "Docker erreichbar"

if docker compose version >/dev/null 2>&1; then COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then COMPOSE=(docker-compose)
else fail "Weder 'docker compose' (Plugin) noch 'docker-compose' gefunden."; fi
ok "Compose gefunden: ${COMPOSE[*]}"

[ -f "$COMPOSE_FILE" ] || fail "docker-compose.yaml fehlt in $PROJECT_DIR"
[ -f "$PROJECT_DIR/service/Dockerfile" ] || fail "service/Dockerfile fehlt in $PROJECT_DIR"

if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
  ok "NVIDIA-GPU erkannt: $(nvidia-smi -L | head -n1)"
else
  warn "nvidia-smi nicht verfügbar bzw. keine GPU erkannt (NVIDIA-Treiber installiert?)."
fi
if docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q nvidia; then
  ok "Docker-NVIDIA-Runtime vorhanden"
else
  warn "Docker kennt keine NVIDIA-Runtime. Ohne NVIDIA Container Toolkit startet 'julia-ollama' nicht."
  warn "Installation: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html"
  warn "danach: sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker"
fi

# Kollision mit gleichnamigen, nicht zu diesem Stack gehörenden Containern erkennen.
for c in "${OUR_CONTAINERS[@]}"; do
  if docker container inspect "$c" >/dev/null 2>&1; then
    project="$(docker container inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$c" 2>/dev/null || true)"
    if [ "$project" = "julia" ]; then
      ok "Container '$c' gehört bereits zu diesem Stack (wird beim Deploy aktualisiert)"
    else
      fail "Ein Container namens '$c' existiert bereits (Projekt: '${project:-unbekannt}'). Entfernen oder umbenennen: docker rm -f $c"
    fi
  fi
done

LISTENING="$(ss -ltn 2>/dev/null | awk '{print $4}' || true)"

# ---------------------------------------------------------------- 2. Verzeichnisse
step "2/5 Verzeichnisse anlegen"
for d in data/ollama data/qdrant data/open-webui data/service; do mkdir -p "$PROJECT_DIR/$d"; done
ok "Verzeichnisse vorhanden (data/...)"

# ---------------------------------------------------------------- 3. .env
step "3/5 .env erzeugen/ergänzen"
random_hex() {
  if command -v openssl >/dev/null 2>&1; then openssl rand -hex 32
  else head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'; fi
}

if [ ! -f "$ENV_FILE" ]; then
  if [ -f "$PROJECT_DIR/.env.example" ]; then cp "$PROJECT_DIR/.env.example" "$ENV_FILE"; else : > "$ENV_FILE"; fi
  ok ".env neu angelegt"
else
  ok ".env existiert bereits - bestehende Werte bleiben unverändert"
fi

env_value() { grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true; }

# Setzt KEY nur, wenn er fehlt oder leer ist.
ensure_env() {
  local key="$1" value="$2" current
  current="$(env_value "$key")"
  if [ -z "$current" ]; then
    if grep -qE "^${key}=" "$ENV_FILE"; then
      local esc="${value//\\/\\\\}"; esc="${esc//|/\\|}"; esc="${esc//&/\\&}"
      sed -i "s|^${key}=.*|${key}=${esc}|" "$ENV_FILE"
    else
      printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
    fi
    echo "  gesetzt: $key"
  fi
}
ensure_env PROJECT_DIR "$PROJECT_DIR"
ensure_env WEBUI_SECRET_KEY "$(random_hex)"

if [ -z "$(env_value CRAWLER_CONTACT)" ]; then
  contact=""
  if [ -t 0 ]; then
    read -r -p "Kontakt für den Crawler (E-Mail oder URL, Enter = später): " contact || contact=""
  fi
  if [ -n "$contact" ]; then
    ensure_env CRAWLER_CONTACT "$contact"
  else
    warn "CRAWLER_CONTACT ist leer. Ohne Kontakt funktioniert Wikipedia nicht. Eintrag in .env nachholen."
  fi
fi
chmod 600 "$ENV_FILE"
ok ".env vollständig (Rechte 600)"

# ---------------------------------------------------------------- 4. Image bauen
step "4/5 Service-Image auf dem Host bauen"
if [ "$DO_BUILD" -eq 1 ]; then
  docker build -t "$IMAGE" "$PROJECT_DIR/service"
  ok "Image gebaut: $IMAGE"
else
  if docker image inspect "$IMAGE" >/dev/null 2>&1; then ok "Build übersprungen, Image '$IMAGE' vorhanden"
  else warn "Build übersprungen und Image '$IMAGE' existiert noch nicht!"; fi
fi

# ---------------------------------------------------------------- 5. Compose validieren
step "5/5 Compose-Datei validieren"
"${COMPOSE[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config -q \
  || fail "docker-compose.yaml ist ungültig (siehe Meldung oben)."
ok "docker-compose.yaml ist gültig"

WEBUI_PORT_VALUE="$(env_value WEBUI_PORT)"; WEBUI_PORT_VALUE="${WEBUI_PORT_VALUE:-3001}"
if echo "$LISTENING" | grep -qE "[:.]${WEBUI_PORT_VALUE}\$"; then
  warn "Port ${WEBUI_PORT_VALUE} ist auf dem Host bereits belegt. Anderen Port in .env setzen (WEBUI_PORT)."
fi

if [ "$DO_UP" -eq 1 ]; then
  step "Stack starten"
  "${COMPOSE[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
  ok "Stack gestartet. Die Modelle werden im Hintergrund geladen:  docker logs -f julia-init"
fi

cat <<MSG

Fertig. Nächste Schritte:

  1) Stack starten (falls nicht schon mit --up geschehen)
       A) Dockhand: neuen Stack anlegen, Inhalt von
            $COMPOSE_FILE
          einfügen, Inhalt von
            $ENV_FILE
          als Umgebungsvariablen eintragen, deployen.
       B) Kommandozeile:
            cd $PROJECT_DIR
            ${COMPOSE[*]} --env-file .env up -d

  2) Warten, bis die Modelle geladen sind (Container 'julia-init' endet mit Exit 0):
       docker logs -f julia-init

  3) Open WebUI öffnen und einrichten (siehe README.md, Abschnitt "Open WebUI einrichten"):
       http://<server-ip>:${WEBUI_PORT_VALUE}
MSG
