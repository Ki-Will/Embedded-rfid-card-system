import serial

# Change 'COM3' to your ESP8266 port
ser = serial.Serial('COM3', 115200, timeout=1)

print("Monitoring ESP8266 serial output. Press Ctrl+C to stop.")

try:
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            print(line)
except KeyboardInterrupt:
    print("Stopped.")
finally:
    ser.close()
