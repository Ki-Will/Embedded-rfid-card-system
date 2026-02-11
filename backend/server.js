const express = require('express');
const app = express();
const server = require('http').createServer(app);
const io = require('socket.io')(server, { cors: { origin: "*" } });
const mqtt = require('mqtt');
const cors = require('cors');

const TEAM_ID = 'Abanshonji';
const TOPIC_STATUS = `rfid/${TEAM_ID}/card/status`;
const TOPIC_TOPUP = `rfid/${TEAM_ID}/card/topup`;
const TOPIC_BALANCE = `rfid/${TEAM_ID}/card/balance`;
const BROKER = 'mqtt://broker.benax.rw:1883';

console.log('Starting server...');
console.log('TEAM_ID:', TEAM_ID);
console.log('Topics:', { TOPIC_STATUS, TOPIC_TOPUP, TOPIC_BALANCE });
console.log('Broker:', BROKER);

const client = mqtt.connect(BROKER);

client.on('connect', () => {
    console.log('MQTT connected successfully');
    client.subscribe(TOPIC_STATUS, (err) => {
        if (err) console.log('Subscribe error for status:', err);
        else console.log('Subscribed to', TOPIC_STATUS);
    });
    client.subscribe(TOPIC_BALANCE, (err) => {
        if (err) console.log('Subscribe error for balance:', err);
        else console.log('Subscribed to', TOPIC_BALANCE);
    });
});

client.on('error', (err) => {
    console.log('MQTT connection error:', err);
});

client.on('offline', () => {
    console.log('MQTT offline');
});

client.on('reconnect', () => {
    console.log('MQTT reconnecting...');
});

client.on('message', (topic, message) => {
    console.log('MQTT message received on', topic, 'payload:', message.toString());
    try {
        const data = JSON.parse(message.toString());
        if (topic === TOPIC_STATUS) {
            io.emit('card_status', data);
            console.log('Emitted card_status to WebSocket:', data);
        } else if (topic === TOPIC_BALANCE) {
            io.emit('balance_update', data);
            console.log('Emitted balance_update to WebSocket:', data);
        }
    } catch (e) {
        console.log('Error parsing MQTT message:', e);
    }
});

app.use(cors({ origin: "*" }));
app.use(express.json());

app.post('/topup', (req, res) => {
    console.log('HTTP POST /topup received from frontend');
    console.log('Request body:', req.body);
    try {
        const { uid, amount } = req.body;
        if (!uid || !amount) {
            console.log('Invalid request: missing uid or amount');
            return res.status(400).json({ error: 'Invalid request' });
        }
        console.log('Processing topup for uid:', uid, 'amount:', amount);
        const payload = JSON.stringify({ uid, amount });
        client.publish(TOPIC_TOPUP, payload, (err) => {
            if (err) {
                console.log('MQTT publish error:', err);
                return res.status(500).json({ error: 'Publish failed' });
            }
            console.log('Successfully published to MQTT:', TOPIC_TOPUP, payload);
        });
        res.json({ status: 'topup requested' });
    } catch (e) {
        console.log('Error in /topup:', e);
        res.status(500).json({ error: 'Internal server error' });
    }
});

io.on('connection', (socket) => {
    console.log('WebSocket client connected:', socket.id);
    socket.on('disconnect', () => {
        console.log('WebSocket client disconnected:', socket.id);
    });
});

server.listen(5000, () => {
    console.log('HTTP/WebSocket server running on port 5000');
});
