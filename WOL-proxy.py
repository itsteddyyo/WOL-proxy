#!/usr/bin/python
import os
import re
import ssl
import json
import ipaddress
import paho.mqtt.client as mqtt
from wakeonlan import send_magic_packet

# read in needed env variables
MQTT_BROKER_HOST   = os.getenv('MQTT_BROKER_HOST',"127.0.0.1")
MQTT_BROKER_PORT   = int(os.getenv('MQTT_BROKER_PORT',1883))
MQTT_CLIENT_ID     = os.getenv('MQTT_CLIENT_ID',"WOL-proxy")
MQTT_USERNAME      = os.getenv('MQTT_USERNAME',"")
MQTT_PASSWORD      = os.getenv('MQTT_PASSWORD',"")
MQTT_TOPIC_PREFIX  = os.getenv('MQTT_TOPIC_PREFIX',"WOL-proxy")
MQTT_QOS           = int(os.getenv('MQTT_QOS',1))
#print("All env vars read.")

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc, properties):
    print(f"Connected to broker at {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT} with result code {rc}: "+mqtt.connack_string(rc))

    client.publish(MQTT_TOPIC_PREFIX+"/status",payload="Online",qos=1,retain=True)

    # subscribe to command topic
    client.subscribe(MQTT_TOPIC_PREFIX+"/command", MQTT_QOS)

def on_subscribe(client, userdata, mid, granted_qos, properties):
    print(f"Subscribed to commands on topic \"{MQTT_TOPIC_PREFIX}/command\" with QOS {granted_qos[0]}.")
    print(f"Wake-On-LAN proxy service started.")  

def on_disconnect(client, userdata, rc, properties):
    if rc != 0:
        print(f"Unexpected disconnection from broker (RC={rc}). Attempting to reconnect...")

# callback for when the client receives a message on the subscribed topic
def on_message(client, userdata, message):
    try:
        payload_text = message.payload.decode()
        print(f"Message received with payload {payload_text}")
        payload = json.loads(payload_text)
        mac_address = payload["mac_address"]
        broadcast_address = payload["broadcast_address"]
        if not isinstance(mac_address, str) or not re.fullmatch(
            r"[0-9a-f]{2}([-:\.]?)[0-9a-f]{2}(\1[0-9a-f]{2}){4}", mac_address.lower()
        ):
            raise ValueError("invalid MAC address")
        if not isinstance(broadcast_address, str):
            raise ValueError("invalid broadcast address")
        broadcast_address = ipaddress.IPv4Address(broadcast_address)
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        print("Message payload must contain a valid mac_address and IPv4 broadcast_address.")
        return

    send_magic_packet(mac_address, ip_address=str(broadcast_address))
    print(f"Magic packet sent to {mac_address} via {broadcast_address}.")

# set up mqtt client
client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)
if MQTT_USERNAME and MQTT_PASSWORD:
    client.username_pw_set(MQTT_USERNAME,MQTT_PASSWORD)
    print("Username and password set.")
client.tls_set(certfile=None,
               keyfile=None,
               cert_reqs=ssl.CERT_REQUIRED)
client.tls_insecure_set(False)
client.will_set(MQTT_TOPIC_PREFIX+"/status", payload="Offline", qos=1, retain=True)
client.on_connect = on_connect # on connect callback
client.on_message = on_message # on message callback
client.on_disconnect = on_disconnect # on disconnect callback
client.on_subscribe = on_subscribe # on subscribe callback

# connect to broker
client.connect(MQTT_BROKER_HOST, port=MQTT_BROKER_PORT)

# start loop
client.loop_forever()
