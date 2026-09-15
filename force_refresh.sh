#!/bin/bash
# force_refresh.sh
#
# Force maestrogateway à republier IMMÉDIATEMENT toutes les valeurs du
# poêle, sans attendre qu'une valeur change réellement (le script ne
# republie que les valeurs différentes de son cache interne, donc après
# suppression/recréation du device dans HA, les entités restent
# "unavailable" ou "unknown" tant que rien n'a changé côté poêle).
#
# Cela publie :
#  - Maestro/Command/Refresh  -> vide le cache interne du script
#  - Maestro/Command/GetInfo  -> déclenche une lecture immédiate du poêle
#
# (voir le README de maestrogateway, section "Sending commands")
#
# Prérequis : mosquitto-clients (sudo apt install -y mosquitto-clients)
#
# Utilisation :
#   ./force_refresh.sh <broker_ip> [port] [user] [password]

set -euo pipefail

BROKER="${1:?Usage: $0 <broker_ip> [port] [user] [password]}"
PORT="${2:-1883}"
MQTT_USER="${3:-}"
MQTT_PASS="${4:-}"

AUTH_ARGS=()
if [[ -n "$MQTT_USER" ]]; then
  AUTH_ARGS=(-u "$MQTT_USER" -P "$MQTT_PASS")
fi

echo "Vidage du cache interne de maestrogateway..."
mosquitto_pub -h "$BROKER" -p "$PORT" "${AUTH_ARGS[@]}" -t "Maestro/Command/Refresh" -n

echo "Demande de lecture immédiate du poêle..."
mosquitto_pub -h "$BROKER" -p "$PORT" "${AUTH_ARGS[@]}" -t "Maestro/Command/GetInfo" -n

echo "Fait. Les entités dans Home Assistant devraient se peupler en quelques secondes."