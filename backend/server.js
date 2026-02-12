const express = require('express');
const app = express();
const server = require('http').createServer(app);
const io = require('socket.io')(server, { cors: { origin: "*" } });
const mqtt = require('mqtt');
const cors = require('cors');
const { Client } = require('pg');

require('dotenv').config();

const dbClient = new Client({ connectionString: process.env.DATABASE_URL });

dbClient.connect((err) => {
    if (err) {
        console.error('Database connection error:', err);
    } else {
        console.log('Database connected');
        // Create tables if not exist
        dbClient.query(`
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
        `, (err) => {
            if (err) console.error('Table creation error:', err);
            else console.log('Tables ready');
        });
    }
});

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
            // Upsert card
            dbClient.query(`
                INSERT INTO cards (uid, balance, updated_at) VALUES ($1, $2, CURRENT_TIMESTAMP)
                ON CONFLICT (uid) DO UPDATE SET balance = EXCLUDED.balance, updated_at = CURRENT_TIMESTAMP
            `, [data.uid, data.balance], (err) => {
                if (err) console.error('DB upsert card error:', err);
                else console.log('Card upserted:', data.uid, data.balance);
            });
        } else if (topic === TOPIC_BALANCE) {
            io.emit('balance_update', data);
            console.log('Emitted balance_update to WebSocket:', data);
            // Update balance and insert transaction
            dbClient.query('SELECT balance FROM cards WHERE uid = $1', [data.uid], (err, res) => {
                if (err) console.error('DB select old balance error:', err);
                else {
                    const old_balance = res.rows[0]?.balance || 0;
                    const amount = data.new_balance - old_balance;
                    dbClient.query(`
                        UPDATE cards SET balance = $1, updated_at = CURRENT_TIMESTAMP WHERE uid = $2
                    `, [data.new_balance, data.uid], (err) => {
                        if (err) console.error('DB update balance error:', err);
                        else console.log('Balance updated:', data.uid, data.new_balance);
                    });
                    dbClient.query(`
                        INSERT INTO transactions (uid, amount) VALUES ($1, $2)
                    `, [data.uid, amount], (err) => {
                        if (err) console.error('DB insert transaction error:', err);
                        else console.log('Transaction inserted for', data.uid, 'amount:', amount);
                    });
                }
            });
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

server.listen(process.env.PORT || 5000, () => {
    console.log('HTTP/WebSocket server running on port', process.env.PORT || 5000);
});
