# RFID Card Top-Up System

This project implements a complete RFID card top-up system using ESP8266, a cloud backend, and a web dashboard, following the specified architecture and MQTT topic isolation.

## System Architecture

- **ESP8266 (Edge Controller)**: Reads and writes RFID card data, publishes card status via MQTT, subscribes to top-up commands.
- **Backend API Service (VPS)**: Receives HTTP commands, communicates with ESP8266 via MQTT, pushes real-time updates via WebSocket.
- **Web Dashboard**: Sends top-up requests via HTTP, receives balance updates via WebSocket.

## Team ID

`Abanshonji`

## MQTT Topics

All topics are prefixed with `rfid/Abanshonji/` for isolation.

- `rfid/Abanshonji/card/status`: ESP8266 publishes card UID and balance.
- `rfid/Abanshonji/card/topup`: Backend publishes top-up commands.
- `rfid/Abanshonji/card/balance`: ESP8266 publishes updated balance after top-up.

## Components

### ESP8266 (MicroPython)

Located in `esp8266/main.py`.

- Connects to WiFi and MQTT broker at `broker.benax.rw:1883`.
- Uses MFRC522 for RFID.
- Assumes balance stored in block 8 of the card.
- Publishes card status when card is detected.
- Subscribes to top-up commands and updates card balance accordingly.

**Note**: Update WiFi credentials in `main.py`.

### Backend (Python Flask)

Located in `backend/app.py`.

- Exposes `POST /topup` endpoint.
- Uses Paho MQTT for communication.
- Uses Flask-SocketIO for WebSocket.

**Requirements**: `pip install -r backend/requirements.txt`

Run: `python backend/app.py`

### Web Dashboard

Located in `web/index.html`.

- Simple HTML/JS interface.
- Uses Socket.IO for WebSocket connection.
- Fetches to backend for top-up requests.

## Setup Instructions

1. **ESP8266**:
   - Flash MicroPython firmware.
   - Upload `mfrc522.py` (library for MFRC522) and `main.py` to ESP8266.
   - Update WiFi SSID and password in `main.py`.

2. **Backend**:
   - Ensure Python 3 installed.
   - `cd backend`
   - `pip install -r requirements.txt`
   - `python app.py` (runs on port 5000)

3. **Web Dashboard**:
   - Serve `web/index.html` using a web server (e.g., Apache, Nginx, or Python's `http.server`).
   - For production, host on the VPS.

## Deployment

- Deploy backend to VPS (IP: 157.173.101.159).
- Host web dashboard on the same VPS or another hosting platform.
- Ensure firewall allows ports 5000 (backend), 80/443 (web), and 1883 (MQTT if needed).

## Testing

- Without hardware: Use MQTT client tools (e.g., MQTT.fx) to simulate ESP8266 and test backend.
- With hardware: Flash ESP8266, run backend, access web dashboard.
- Test end-to-end: Scan card, check status in dashboard, top-up, verify update.

## Repository

Push this code to a public GitHub repository.

Submit the repository link and live dashboard URL via the Google Form.

## Notes

- MQTT broker is shared; ensure unique team_id.
- Devices speak MQTT, users speak HTTP/WebSocket.
- No direct communication between dashboard and MQTT or ESP8266.
