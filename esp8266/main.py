import machine
import time
from machine import Pin, SPI
from mfrc522 import MFRC522
import network
import ujson
from umqtt.simple import MQTTClient

# WiFi credentials
WIFI_SSID = 'RCA'
WIFI_PASS = '@RcaNyabihu2023'

# MQTT
BROKER_IP = 'broker.benax.rw'
BROKER_PORT = 1883
TEAM_ID = 'Abanshonji'
TOPIC_STATUS = f'rfid/{TEAM_ID}/card/status'
TOPIC_TOPUP = f'rfid/{TEAM_ID}/card/topup'
TOPIC_BALANCE = f'rfid/{TEAM_ID}/card/balance'
CLIENT_ID = f'esp8266_{TEAM_ID}'

# RFID pins (ESP8266 hardware SPI fixed pins)
SCLK = 14   # GPIO14
MOSI = 13   # GPIO13
MISO = 12   # GPIO12
CS = 4      # GPIO4
RST = 5     # GPIO5

BALANCE_BLOCK = 8

# Global balances dict for memory persistence
balances = {}

# Load balances from file
def load_balances():
    try:
        with open('balances.json', 'r') as f:
            data = ujson.load(f)
            print('Loaded balances:', data)
            return data
    except:
        print('No balances file, starting empty')
        return {}

# Save balances to file
def save_balances():
    try:
        with open('balances.json', 'w') as f:
            ujson.dump(balances, f)
            print('Saved balances:', balances)
    except Exception as e:
        print('Error saving balances:', e)

# Load balances on boot
balances = load_balances()

# Last scan time for rate limiting
last_scan_time = 0

# ---------------- WIFI ----------------
def connect_wifi():
    print('Connecting to WiFi...')
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)

    while not wlan.isconnected():
        time.sleep(1)

    print('WiFi connected')
    print(wlan.ifconfig())


# ---------------- MQTT CALLBACK ----------------
def on_message(topic, msg):
    topic = topic.decode()
    msg = ujson.loads(msg.decode())
    print(f'Received message on {topic}: {ujson.dumps(msg)}')

    if topic == TOPIC_TOPUP:
        uid = msg['uid']
        amount = msg['amount']

        global current_uid, current_balance

        if current_uid == uid:
            new_balance = current_balance + amount
            write_balance(current_uid, new_balance)

            payload = ujson.dumps({'uid': uid, 'new_balance': new_balance})
            client.publish(TOPIC_BALANCE, payload)

            print(f'Published balance: {payload}')
            print(f'Topped up {uid} by {amount}, new balance {new_balance}')


# ---------------- RFID WRITE ----------------
def write_balance(uid, balance):
    print(f'Writing balance {balance} for {uid}')

    key = [0xFF] * 6
    uid_list = list(bytes.fromhex(uid))

    rdr.auth(rdr.AUTHENT1A, BALANCE_BLOCK, key, uid_list)

    data = balance.to_bytes(4, 'little') + b'\x00' * 12
    rdr.write(BALANCE_BLOCK, data)

    rdr.stop_crypto1()
    print(f'Balance written for {uid}')
    # Store in memory for persistence
    balances[uid] = balance
    save_balances()


# ---------------- RFID READ ----------------
def read_balance(uid):
    print(f'Reading balance for {uid}')

    key = [0xFF] * 6
    uid_list = list(bytes.fromhex(uid))

    try:
        rdr.auth(rdr.AUTHENT1A, BALANCE_BLOCK, key, uid_list)

        data = rdr.read(BALANCE_BLOCK)
        if data is None:
            print('Read failed, using memory balance')
            return balances.get(uid, 0)
        balance = int.from_bytes(data[:4], 'little')

        rdr.stop_crypto1()
        print(f'Balance read for {uid}: {balance}')
        # Update memory
        balances[uid] = balance
        return balance
    except Exception as e:
        print(f'Error reading balance: {e}, using memory')
        return balances.get(uid, 0)


# ---------------- MAIN ----------------
connect_wifi()

client = MQTTClient(CLIENT_ID, BROKER_IP, BROKER_PORT)
client.set_callback(on_message)
client.connect()
print('MQTT connected')
client.subscribe(TOPIC_TOPUP)


# 🔥 FIXED SPI FOR ESP8266
spi = SPI(1, baudrate=1000000, polarity=0, phase=0)

# 🔥 FIXED MFRC522 INIT FOR ESP8266 HARDWARE SPI
# rdr = MFRC522(spi, Pin(CS), Pin(RST))
rdr = MFRC522(sck=Pin(SCLK), mosi=Pin(MOSI), miso=Pin(MISO), rst=Pin(RST), cs=Pin(CS))
# (sck: Any, mosi: Any, miso: Any, rst: Any, cs: Any) -> MFRC522



current_uid = None
current_balance = 0


while True:
    if time.time() - last_scan_time < 7:
        time.sleep(0.1)
        continue

    (stat, tag_type) = rdr.request(rdr.REQIDL)

    if stat == rdr.OK:
        (stat, uid) = rdr.anticoll()

        if stat == rdr.OK:
            uid_str = ''.join('%02X' % x for x in uid)

            current_uid = uid_str
            try:
                current_balance = read_balance(uid_str)
                payload = ujson.dumps({
                    'uid': uid_str,
                    'balance': current_balance
                })
                client.publish(TOPIC_STATUS, payload)
                print(f'Published status: {payload}')
                print(f'Card detected: {uid_str}, balance: {current_balance}')
                last_scan_time = time.time()
            except Exception as e:
                print(f'Error processing card {uid_str}: {e}')

    client.check_msg()
    time.sleep(0.1)
