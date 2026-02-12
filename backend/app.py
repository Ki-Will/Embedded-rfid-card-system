from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO
import paho.mqtt.client as mqtt
import json
import os
import psycopg2

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

TEAM_ID = 'Abanshonji'
TOPIC_STATUS = f'rfid/{TEAM_ID}/card/status'
TOPIC_TOPUP = f'rfid/{TEAM_ID}/card/topup'
TOPIC_BALANCE = f'rfid/{TEAM_ID}/card/balance'
BROKER = 'broker.benax.rw'

print('Starting server...')
print('TEAM_ID:', TEAM_ID)
print('Topics:', { 'status': TOPIC_STATUS, 'topup': TOPIC_TOPUP, 'balance': TOPIC_BALANCE })
print('Broker:', BROKER)

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    # Create tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            uid VARCHAR(255) PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            uid VARCHAR(255),
            amount INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    print('Database connected and tables ready')
else:
    print('DATABASE_URL not set, running without database')

client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print('MQTT connected successfully')
        client.subscribe(TOPIC_STATUS)
        print('Subscribed to', TOPIC_STATUS)
        client.subscribe(TOPIC_BALANCE)
        print('Subscribed to', TOPIC_BALANCE)
    else:
        print('MQTT connection failed, rc:', rc)

def on_error(client, userdata, rc):
    print('MQTT connection error:', rc)

def on_offline(client, userdata):
    print('MQTT offline')

def on_reconnect(client, userdata, flags, rc):
    print('MQTT reconnecting...')

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()
    print('MQTT message received on', topic, 'payload:', payload)
    try:
        data = json.loads(payload)
        if topic == TOPIC_STATUS:
            socketio.emit('card_status', data)
            print('Emitted card_status to WebSocket:', data)
            if DATABASE_URL:
                cur.execute("""
                    INSERT INTO cards (uid, balance, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (uid) DO UPDATE SET balance = EXCLUDED.balance, updated_at = CURRENT_TIMESTAMP
                """, (data['uid'], data['balance']))
                conn.commit()
                print('Card upserted:', data['uid'], data['balance'])
        elif topic == TOPIC_BALANCE:
            socketio.emit('balance_update', data)
            print('Emitted balance_update to WebSocket:', data)
            if DATABASE_URL:
                cur.execute("SELECT balance FROM cards WHERE uid = %s", (data['uid'],))
                old_balance = cur.fetchone()[0] if cur.rowcount > 0 else 0
                amount = data['new_balance'] - old_balance
                cur.execute("""
                    UPDATE cards SET balance = %s, updated_at = CURRENT_TIMESTAMP WHERE uid = %s
                """, (data['new_balance'], data['uid']))
                cur.execute("""
                    INSERT INTO transactions (uid, amount) VALUES (%s, %s)
                """, (data['uid'], amount))
                conn.commit()
                print('Balance updated:', data['uid'], data['new_balance'], 'Transaction:', amount)
    except Exception as e:
        print('Error parsing MQTT message:', e)

client.on_connect = on_connect
client.on_error = on_error
client.on_offline = on_offline
client.on_reconnect = on_reconnect
client.on_message = on_message

client.connect(BROKER, 1883, 60)
client.loop_start()

@app.route('/topup', methods=['POST'])
def topup():
    print('HTTP POST /topup received from frontend')
    print('Request body:', request.get_json())
    try:
        data = request.get_json()
        uid = data.get('uid')
        amount = data.get('amount')
        if not uid or not amount:
            print('Invalid request: missing uid or amount')
            return jsonify({'error': 'Invalid request'}), 400
        print('Processing topup for uid:', uid, 'amount:', amount)
        payload = json.dumps({'uid': uid, 'amount': amount})
        client.publish(TOPIC_TOPUP, payload)
        print('Successfully published to MQTT:', TOPIC_TOPUP, payload)
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

@app.route('/')
def index():
    return send_from_directory(os.path.join(os.getcwd(), '..', 'web'), 'index.html')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
