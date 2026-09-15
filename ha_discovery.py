#!/usr/bin/python3
# coding: utf-8
"""
ha_discovery.py

Publie automatiquement les entités MQTT Discovery pour Home Assistant
à partir de maestrogateway (https://github.com/Chibald/maestrogateway).

Compatible uniquement avec MQTT_PAYLOAD_TYPE = 'TOPIC' (un topic par
valeur), qui est le mode utilisé dans le tuto communautaire.

Principe :
- Chaque entité est décrite une seule fois ci-dessous (topic d'état,
  éventuel topic de commande, type d'entité HA).
- publish_discovery(client) publie un message JSON retained sur
  homeassistant/<component>/mcz_maestro/<object_id>/config pour
  chacune d'elles.
- Home Assistant (intégration MQTT, activée par défaut) les détecte
  et crée les entités tout seul, regroupées sous un seul appareil
  "Poêle à granulés MCZ".

Utilisation dans maestro.py (voir PATCH.md) :

    from ha_discovery import publish_discovery
    ...
    def on_connect_mqtt(client, userdata, flags, rc):
        ...
        if _MQTT_PAYLOAD_TYPE == 'TOPIC':
            client.subscribe(_MQTT_TOPIC_SUB + '#', qos=1)
            publish_availabletopics()
            publish_discovery(client)          # <-- ajout
        ...
"""

import json

# ---------------------------------------------------------------------------
# Configuration générale
# ---------------------------------------------------------------------------

DISCOVERY_PREFIX = "homeassistant"     # préfixe standard HA
NODE_ID = "mcz_maestro"                # identifiant unique de l'appareil

# Adaptez si vous changez MQTT_TOPIC_PUB / MQTT_TOPIC_SUB dans _config_.py
PUB_PREFIX = "Maestro/"                # _MQTT_TOPIC_PUB
CMD_PREFIX = "Maestro/Command/"        # _MQTT_TOPIC_SUB
AVAILABILITY_TOPIC = PUB_PREFIX + "Status"

DEVICE = {
    "identifiers": [NODE_ID],
    "name": "Poêle à granulés MCZ",
    "manufacturer": "MCZ",
    "model": "Maestro",
}

# Bloc "origin", recommandé par le schéma MQTT Discovery actuel : il
# identifie le logiciel source dans la fiche de l'appareil côté HA.
ORIGIN = {
    "name": "maestrogateway",
    "sw_version": "1.0",
    "support_url": "https://github.com/Chibald/maestrogateway",
}

AVAILABILITY = [{
    "topic": AVAILABILITY_TOPIC,
    "payload_available": "connected",
    "payload_not_available": "disconnected",
}]


# ---------------------------------------------------------------------------
# Tables de correspondance (value_template Jinja / options des select)
# ---------------------------------------------------------------------------

STOVE_STATE_MAP = {
    "0": "Éteint", "1": "Contrôle du poêle", "2": "Nettoyage froid",
    "3": "Chargement froid", "4": "Démarrage 1 froid", "5": "Démarrage 2 froid",
    "6": "Nettoyage chaud", "7": "Chargement chaud", "8": "Démarrage 1 chaud",
    "9": "Démarrage 2 chaud", "10": "Stabilisation", "11": "Puissance 1",
    "12": "Puissance 2", "13": "Puissance 3", "14": "Puissance 4",
    "15": "Puissance 5", "30": "Mode diagnostic", "31": "Marche",
    "40": "Extinction", "41": "Refroidissement en cours",
    "42": "Nettoyage basse puissance", "43": "Nettoyage haute puissance",
    "44": "Déblocage vis sans fin", "45": "Auto ECO", "46": "Veille",
    "48": "Diagnostic", "49": "Chargement vis sans fin",
    "50": "Erreur A01 - Allumage raté", "51": "Erreur A02 - Extinction anormale",
    "52": "Erreur A03 - Surchauffe réservoir pellets",
    "53": "Erreur A04 - Température fumées trop haute",
    "54": "Erreur A05 - Obstruction conduit / vent",
    "55": "Erreur A06 - Mauvais tirage",
    "56": "Erreur A09 - Sonde fumées défaillante",
    "57": "Erreur A11 - Défaut alimentation pellet",
    "58": "Erreur A13 - Température carte mère élevée",
    "59": "Erreur A14 - Défaut capteur porte air",
    "60": "Erreur A18 - Température eau trop haute",
    "61": "Erreur A19 - Défaut sonde température eau",
    "62": "Erreur A20 - Défaut sonde auxiliaire",
    "63": "Erreur A21 - Alarme pressostat",
    "64": "Erreur A22 - Défaut sonde ambiante",
    "65": "Erreur A23 - Défaut fermeture brasero",
    "66": "Erreur A12 - Panne motoréducteur",
    "67": "Erreur A17 - Bourrage vis sans fin",
    "69": "Attente alarme sécurité",
}

PROFILE_MAP = {
    "0": "Manuel", "1": "Dynamique", "2": "Nuit",
    "3": "Confort", "4": "Power 110%", "10": "Adaptatif",
}

FAN_LEVEL_MAP = {
    "0": "Désactivé", "1": "Niveau 1", "2": "Niveau 2",
    "3": "Niveau 3", "4": "Niveau 4", "5": "Niveau 5", "6": "Automatique",
}

POWER_LEVEL_MAP = {
    "11": "Puissance 1", "12": "Puissance 2", "13": "Puissance 3",
    "14": "Puissance 4", "15": "Puissance 5",
}

BRAZIER_MAP = {"0": "OK", "100": "Fermeture en cours", "101": "Ouverture en cours"}
CANDLE_MAP = {"0": "OK", "1": "Usée"}
ONOFF_MAP = {"0": "Off", "1": "On"}


def _jinja_lookup(mapping, default_expr="'Inconnu (' ~ value ~ ')'"):
    """Construit un value_template Jinja de type dictionnaire, comme
    dans le tuto communautaire, à partir d'un dict Python."""
    py_dict = json.dumps(mapping, ensure_ascii=False)
    return (
        "{% set mapper = " + py_dict + " %}"
        "{% set state = (value | string) %}"
        "{{ mapper[state] if state in mapper else " + default_expr + " }}"
    )


# ---------------------------------------------------------------------------
# Définition des entités
#
# Chaque entrée : (object_id, component, config_dict_sans_device_ni_avail)
# component ∈ climate | sensor | select | switch | binary_sensor
# Les topics sont complétés automatiquement avec PUB_PREFIX / CMD_PREFIX.
# ---------------------------------------------------------------------------

def _sensor(name, state_key, unit=None, device_class=None, value_template=None,
            icon=None, diagnostic=False, state_class=None):
    cfg = {
        "name": name,
        "state_topic": PUB_PREFIX + state_key,
    }
    if unit:
        cfg["unit_of_measurement"] = unit
    if device_class:
        cfg["device_class"] = device_class
    if state_class:
        cfg["state_class"] = state_class
    if value_template:
        cfg["value_template"] = value_template
    if icon:
        cfg["icon"] = icon
    if diagnostic:
        cfg["entity_category"] = "diagnostic"
    return cfg


def _select(name, state_key, cmd_key, options_map, icon=None):
    return {
        "name": name,
        "state_topic": PUB_PREFIX + state_key,
        "command_topic": CMD_PREFIX + cmd_key,
        "value_template": _jinja_lookup(options_map, default_expr="value"),
        "options": list(options_map.values()),
        # traduit le libellé choisi dans HA vers le code numérique attendu
        "command_template": _jinja_lookup(
            {v: k for k, v in options_map.items()}, default_expr="value"
        ),
        "icon": icon or "mdi:fan",
    }


def _switch(name, state_key, cmd_key, icon=None, diagnostic=True):
    cfg = {
        "name": name,
        "state_topic": PUB_PREFIX + state_key,
        "command_topic": CMD_PREFIX + cmd_key,
        "payload_on": "1",
        "payload_off": "0",
        "state_on": "1",
        "state_off": "0",
        "icon": icon or "mdi:toggle-switch",
    }
    if diagnostic:
        cfg["entity_category"] = "config"
    return cfg


def build_entities():
    entities = {}

    # --- Climate : contrôle principal du poêle -----------------------------
    entities[("climate", "poele_mcz")] = {
        "name": "Poêle MCZ",
        "modes": ["off", "heat"],
        "mode_state_topic": PUB_PREFIX + "Power",
        "mode_state_template": "{{ 'off' if value == '0' else 'heat' }}",
        "mode_command_topic": CMD_PREFIX + "Power",
        "mode_command_template": "{{ '0' if value == 'off' else '1' }}",
        "current_temperature_topic": PUB_PREFIX + "Ambient_Temperature",
        "temperature_command_topic": CMD_PREFIX + "Temperature_Setpoint",
        "temperature_state_topic": PUB_PREFIX + "Temperature_Setpoint",
        "min_temp": 6,
        "max_temp": 30,
        "temp_step": 0.5,
        "temperature_unit": "C",
        "icon": "mdi:radiator",
    }

    # --- Sensors principaux ---------------------------------------------
    entities[("sensor", "etat_du_poele")] = _sensor(
        "État du poêle", "Stove_State",
        value_template=_jinja_lookup(STOVE_STATE_MAP), icon="mdi:radiator"
    )
    entities[("sensor", "profil_actif")] = _sensor(
        "Profil actif", "Profile",
        value_template=_jinja_lookup(PROFILE_MAP), icon="mdi:tune"
    )
    entities[("sensor", "temperature_ambiante")] = _sensor(
        "Température ambiante", "Ambient_Temperature",
        unit="°C", device_class="temperature", state_class="measurement"
    )
    entities[("sensor", "temperature_fumees")] = _sensor(
        "Température fumées", "Fume_Temperature",
        unit="°C", device_class="temperature", state_class="measurement",
        diagnostic=True
    )
    entities[("sensor", "puissance_active")] = _sensor(
        "Puissance active", "Power_Level",
        value_template=_jinja_lookup(POWER_LEVEL_MAP), icon="mdi:fire"
    )

    # --- Ventilation : remplace les switches par niveau par des select -----
    entities[("select", "ventilation_ambiance")] = _select(
        "Ventilation ambiance", "Fan_State", "Fan_State", FAN_LEVEL_MAP,
        icon="mdi:fan"
    )
    entities[("select", "canalisation_1")] = _select(
        "Canalisation 1", "DuctedFan1", "DuctedFan1", FAN_LEVEL_MAP,
        icon="mdi:fan"
    )
    entities[("select", "canalisation_2")] = _select(
        "Canalisation 2", "DuctedFan2", "DuctedFan2", FAN_LEVEL_MAP,
        icon="mdi:fan"
    )
    entities[("select", "profil_de_fonctionnement")] = _select(
        "Profil de fonctionnement", "Profile", "Profile", PROFILE_MAP,
        icon="mdi:tune-variant"
    )
    entities[("select", "reglage_puissance")] = _select(
        "Réglage puissance", "Power_Level", "Power_Level", POWER_LEVEL_MAP,
        icon="mdi:fire-alert"
    )

    # --- Switches (réglages) -----------------------------------------------
    entities[("switch", "mode_silencieux")] = _switch(
        "Mode silencieux", "Silent_Mode", "Silent_Mode", icon="mdi:fan-off"
    )
    entities[("switch", "mode_eco")] = _switch(
        "Mode ECO", "Eco_Mode", "Eco_Mode", icon="mdi:leaf"
    )
    entities[("switch", "effets_sonores")] = _switch(
        "Effets sonores", "Sound_Effects", "Sound_Effects", icon="mdi:volume-high"
    )
    entities[("switch", "chronothermostat")] = _switch(
        "Chronothermostat", "Chronostat", "Chronostat", icon="mdi:clock-outline"
    )

    # --- Diagnostic / technique ---------------------------------------------
    entities[("sensor", "temperature_chaudiere")] = _sensor(
        "Température chaudière", "Boiler_Temperature",
        unit="°C", device_class="temperature", state_class="measurement",
        diagnostic=True
    )
    entities[("sensor", "temperature_carte_mere")] = _sensor(
        "Température carte mère", "Temperature_Motherboard",
        unit="°C", device_class="temperature", state_class="measurement",
        diagnostic=True
    )
    entities[("sensor", "etat_bougie_d_allumage")] = _sensor(
        "État bougie d'allumage", "Candle_Condition",
        value_template=_jinja_lookup(CANDLE_MAP), diagnostic=True,
        icon="mdi:fire-alert"
    )
    entities[("sensor", "brasero")] = _sensor(
        "Brasero", "Brazier",
        value_template=_jinja_lookup(BRAZIER_MAP), diagnostic=True
    )
    entities[("sensor", "heures_avant_entretien")] = _sensor(
        "Heures avant entretien", "Hours_To_Service",
        unit="h", diagnostic=True, icon="mdi:wrench-clock"
    )
    entities[("sensor", "nombre_d_allumages")] = _sensor(
        "Nombre d'allumages", "Number_Of_Ignitions",
        diagnostic=True, icon="mdi:counter"
    )
    entities[("sensor", "heures_de_fonctionnement_totales")] = _sensor(
        "Heures de fonctionnement totales", "Total_Operating_Hours",
        diagnostic=True, icon="mdi:clock-outline"
    )

    # --- Disponibilité de la passerelle -------------------------------------
    entities[("binary_sensor", "passerelle_maestro_connectee")] = {
        "name": "Passerelle Maestro connectée",
        "state_topic": AVAILABILITY_TOPIC,
        "payload_on": "connected",
        "payload_off": "disconnected",
        "device_class": "connectivity",
        "entity_category": "diagnostic",
    }

    return entities


# ---------------------------------------------------------------------------
# Publication
# ---------------------------------------------------------------------------

def publish_discovery(client, logger=None):
    """Publie (retained) la configuration MQTT Discovery de toutes les
    entités sur le broker connecté via `client` (paho-mqtt)."""
    entities = build_entities()
    for (component, object_id), cfg in entities.items():
        cfg = dict(cfg)  # ne pas modifier le dict source
        cfg["unique_id"] = f"{NODE_ID}_{object_id}"
        # Depuis Home Assistant 2026.4, la clé "object_id" n'est plus lue
        # pour fixer l'entity_id (dépréciée en 2025.10, supprimée en 2026.4).
        # Il faut désormais utiliser "default_entity_id" avec l'ID complet
        # "domaine.object_id".
        cfg["default_entity_id"] = f"{component}.{object_id}"
        cfg["device"] = DEVICE
        cfg["origin"] = ORIGIN
        # le binary_sensor de disponibilité n'a pas besoin de son propre
        # bloc "availability" (il EN est la source)
        if object_id != "passerelle_maestro_connectee":
            cfg["availability"] = AVAILABILITY

        topic = f"{DISCOVERY_PREFIX}/{component}/{NODE_ID}/{object_id}/config"
        payload = json.dumps(cfg, ensure_ascii=False)
        client.publish(topic, payload, qos=1, retain=True)
        if logger:
            logger.info(f"HA Discovery: publish {topic}")


def remove_discovery(client, logger=None):
    """Retire toutes les entités de Home Assistant (utile en cas de
    reconfiguration : publie un payload vide, retained, sur chaque topic)."""
    entities = build_entities()
    for (component, object_id) in entities:
        topic = f"{DISCOVERY_PREFIX}/{component}/{NODE_ID}/{object_id}/config"
        client.publish(topic, "", qos=1, retain=True)
        if logger:
            logger.info(f"HA Discovery: remove {topic}")


if __name__ == "__main__":
    # Aperçu local des payloads générés, sans connexion MQTT
    for key, cfg in build_entities().items():
        cfg = dict(cfg)
        cfg["unique_id"] = f"{NODE_ID}_{key[1]}"
        cfg["device"] = DEVICE
        print(f"{DISCOVERY_PREFIX}/{key[0]}/{NODE_ID}/{key[1]}/config")
        print(json.dumps(cfg, indent=2, ensure_ascii=False))
        print()
