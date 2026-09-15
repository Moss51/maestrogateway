#!/bin/bash
# purge_discovery.sh
#
# Purge TOUTES les entités MQTT Discovery publiées sous le node_id
# "mcz_maestro" (anciennes ET nouvelles versions de ha_discovery.py),
# en publiant un payload vide retained sur chaque topic de config
# trouvé sur le broker. C'est la seule façon de vraiment faire
# disparaître une entité : supprimer le device dans l'UI de Home
# Assistant ne touche PAS aux messages retained sur le broker, donc
# HA les redécouvre au prochain redémarrage / reload de l'intégration
# MQTT — c'est ce qui vous est arrivé.
#
# Prérequis : mosquitto-clients (mosquitto_sub / mosquitto_pub)
#   sudo apt install -y mosquitto-clients
#
# Utilisation :
#   chmod +x purge_discovery.sh
#   ./purge_discovery.sh <broker_ip> [port] [user] [password]
#
# Exemple :
#   ./purge_discovery.sh 192.168.1.10 1883 mon_user mon_mdp
#   ./purge_discovery.sh 192.168.1.10          # sans authentification

set -euo pipefail

BROKER="${1:?Usage: $0 <broker_ip> [port] [user] [password]}"
PORT="${2:-1883}"
MQTT_USER="${3:-}"
MQTT_PASS="${4:-}"

AUTH_ARGS=()
if [[ -n "$MQTT_USER" ]]; then
  AUTH_ARGS=(-u "$MQTT_USER" -P "$MQTT_PASS")
fi

echo "Recherche des topics de découverte retained pour 'mcz_maestro' sur $BROKER:$PORT ..."

# Liste tous les topics de config retained qui existent réellement sur
# le broker pour ce node_id (couvre les anciens ET nouveaux noms
# d'entités, peu importe les versions successives du script).
TOPICS=$(mosquitto_sub -h "$BROKER" -p "$PORT" "${AUTH_ARGS[@]}" \
  -t 'homeassistant/+/mcz_maestro/+/config' -v \
  -W 3 --retained-only 2>/dev/null | awk '{print $1}' | sort -u || true)

if [[ -z "$TOPICS" ]]; then
  echo "Aucun topic de découverte trouvé (rien à purger, ou pas de message retained)."
  exit 0
fi

echo "Topics trouvés :"
echo "$TOPICS"
echo

read -r -p "Purger ces $(echo "$TOPICS" | wc -l) topic(s) ? [o/N] " CONFIRM
if [[ "$CONFIRM" != "o" && "$CONFIRM" != "O" ]]; then
  echo "Annulé."
  exit 0
fi

while IFS= read -r topic; do
  echo "Purge: $topic"
  mosquitto_pub -h "$BROKER" -p "$PORT" "${AUTH_ARGS[@]}" -t "$topic" -r -n
done <<< "$TOPICS"

echo
echo "Terminé. Dans Home Assistant : Paramètres > Appareils et services > MQTT,"
echo "l'appareil 'Poêle à granulés MCZ' doit maintenant avoir disparu."
echo "Redémarrez ensuite maestrogateway (ou rechargez l'intégration MQTT) pour"
echo "qu'il republie une configuration propre avec les entités actuelles."