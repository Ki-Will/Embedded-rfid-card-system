from flask import Flask, request, jsonify
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
import json

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

TEAM_ID = 'Abanshonji'
TOPIC_STATUS = f'rfid/{TEAM_ID}/card/status'
TOPIC_TOPUP = f'rfid/{TEAM_ID}/card/topup'
TOPIC_BALANCE = f'rfid/{TEAM_ID}/card/balance'
BROKER_IP = 'broker.benax.rw'
BROKER_PORT = 1883

print('Starting Flask server...')
print('TEAM_ID:', TEAM_ID)
print('Topics:', { 'status': TOPIC_STATUS, 'topup': TOPIC_TOPUP, 'balance': TOPIC_BALANCE })
print('Broker:', BROKER_IP, BROKER_PORT)
# R9@!Z7Kq
def on_connect(client, userdata, flags, reasonCode, properties):
    if reasonCode == 0:
        print('MQTT connected successfully')
        client.subscribe(TOPIC_STATUS)
        client.subscribe(TOPIC_BALANCE)
    else:
        print('MQTT connection failed, reasonCode:', reasonCode)

def on_disconnect(client, userdata, rc):
    print('MQTT disconnected, rc:', rc)

def on_message(client, userdata, msg):
    topic = msg.topic
    try:
        data = json.loads(msg.payload.decode())
        print('MQTT message received on', topic, 'payload:', data)
        if topic == TOPIC_STATUS:
            socketio.emit('card_status', data)
            print('Emitted card_status to WebSocket:', data)
        elif topic == TOPIC_BALANCE:
            socketio.emit('balance_update', data)
            print('Emitted balance_update to WebSocket:', data)
    except Exception as e:
        print('Error parsing MQTT message:', e)

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message
mqtt_client.connect(BROKER_IP, BROKER_PORT, 60)
mqtt_client.loop_start()

@app.route('/topup', methods=['POST'])
def topup():
    print('HTTP POST /topup received from frontend')
    try:
        data = request.json
        uid = data.get('uid')
        amount = data.get('amount')
        if not uid or not amount:
            print('Invalid request: missing uid or amount')
            return jsonify({'error': 'Invalid request'}), 400
        print('Processing topup for uid:', uid, 'amount:', amount)
        payload = json.dumps({'uid': uid, 'amount': amount})
        mqtt_client.publish(TOPIC_TOPUP, payload)
        print('Published to MQTT:', TOPIC_TOPUP, payload)
        return jsonify({'status': 'topup requested'})
    except Exception as e:
        print('Error in /topup:', e)
        return jsonify({'error': 'Internal server error'}), 500

@socketio.on('connect')
def handle_connect():
    print('WebSocket client connected:', request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    print('WebSocket client disconnected:', request.sid)

if __name__ == '__main__':
    print('HTTP/WebSocket server running on port 5000')
    socketio.run(app, host='0.0.0.0', port=5000)
