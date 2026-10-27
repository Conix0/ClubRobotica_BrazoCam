import cv2
import urllib.request
import numpy as np
import mediapipe as mp
import serial
import time

# 1. Configuración de Hardware
ESP32_STREAM_URL = "http://192.168.100.232/stream"  # Tu IP del ESP32-CAM
ARDUINO_PORT = "COM3"                             # Puerto de tu Arduino Nano
BAUD_RATE = 115200

# Conexión Serial con Arduino Nano (Opcional si aún no lo enchufas)
arduino = None
try:
    arduino = serial.Serial(ARDUINO_PORT, BAUD_RATE, timeout=0.1)
    time.sleep(2)  # Esperar reinicio automático
    print(f"[OK] Conectado a Arduino en {ARDUINO_PORT}")
except Exception as e:
    print(f"[AVISO] Arduino no detectado ({e}). Modo simulación activado.")

# 2. Configuración de MediaPipe Hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6
)

def is_hand_open(hand_landmarks):
    # Puntas de los dedos (índice, medio, anular, meñique) vs articulaciones PIP
    finger_tips = [8, 12, 16, 20]
    finger_pips = [6, 10, 14, 18]
    
    open_fingers = 0
    for tip, pip in zip(finger_tips, finger_pips):
        # Si la punta está más arriba en 'y' que el nudillo, el dedo está levantado
        if hand_landmarks.landmark[tip].y < hand_landmarks.landmark[pip].y:
            open_fingers += 1

    return open_fingers >= 3

# 3. Lectura de Stream HTTP
print("Conectando con la ESP32-CAM...")
stream = urllib.request.urlopen(ESP32_STREAM_URL)
bytes_data = b""
last_state = None
status_msg = "Esperando deteccion de mano..."

print("\n--- SISTEMA LISTO ---")
print("Abre la mano frente a la camara para abrir la pinza.")
print("Cierra el puno para cerrar la pinza.\n")

try:
    while True:
        bytes_data += stream.read(1024)
        a = bytes_data.find(b'\xff\xd8')
        b = bytes_data.find(b'\xff\xd9')

        if a != -1 and b != -1:
            jpg = bytes_data[a:b+2]
            bytes_data = bytes_data[b+2:]

            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                continue

            frame = cv2.flip(frame, -1)
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(image_rgb)

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS
                    )

                    hand_open = is_hand_open(hand_landmarks)

                    # Si abres la mano
                    if hand_open and last_state != "OPEN":
                        status_msg = "PINZA ABIERTA (Mano Abierta)"
                        print("\n>>> [ACCION] ¡LA PINZA SE ABRIO! <<<")
                        if arduino:
                            arduino.write(b"GRIPPER OPEN\n")
                            # Leer respuesta del Arduino si está conectado
                            time.sleep(0.05)
                            resp = arduino.readline().decode('utf-8', errors='ignore').strip()
                            if resp:
                                print(f"    Respuesta de Arduino: {resp}")
                        last_state = "OPEN"

                    # Si cierras la mano
                    elif not hand_open and last_state != "CLOSE":
                        status_msg = "PINZA CERRADA (Mano Cerrada)"
                        print("\n>>> [ACCION] ¡LA PINZA SE CERRO! <<<")
                        if arduino:
                            arduino.write(b"GRIPPER CLOSE\n")
                            time.sleep(0.05)
                            resp = arduino.readline().decode('utf-8', errors='ignore').strip()
                            if resp:
                                print(f"    Respuesta de Arduino: {resp}")
                        last_state = "CLOSE"

            # Dibujar mensaje en la ventana de video
            # Fondo del texto para que se lea fácil
            cv2.rectangle(frame, (10, 10), (450, 60), (0, 0, 0), -1)
            color_texto = (0, 255, 0) if last_state == "OPEN" else (0, 0, 255) if last_state == "CLOSE" else (255, 255, 255)
            cv2.putText(frame, status_msg, (20, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_texto, 2)

            cv2.imshow("Prueba Pinza ESP32-CAM", frame)

            if cv2.waitKey(1) & 0xFF == 27:  # Salir con ESC
                break

except Exception as e:
    print(f"Error durante la ejecucion: {e}")

finally:
    if arduino and arduino.is_open:
        arduino.close()
    cv2.destroyAllWindows()
    hands.close()