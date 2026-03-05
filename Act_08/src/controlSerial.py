import serial
import time
import sys

def run_servo_controller(port, baud_rate=9600):
    try:
        ser = serial.Serial(port, baud_rate, timeout=1)
        print(f"Connecting to Arduino on {port}...")
        time.sleep(2)
        
        print("--- Servo Serial Controller ---")
        while True:
            user_input = input("\nEnter angle (0-180): ").strip().lower()
            if user_input == 'exit': break

            try:
                angle = int(user_input)
                if 0 <= angle <= 180:
                    ser.write(f"{angle}\n".encode('utf-8'))
                    time.sleep(0.1) 
                    if ser.in_waiting > 0:
                        response = ser.readline().decode('utf-8').strip()
                        print(f"Arduino Status: {response}")
                else:
                    print(f"Local Error: {angle} out of range.")
            except ValueError:
                print("Local Error: Invalid input.")
        ser.close()
    except serial.SerialException as e:
        print(f"Serial Error: {e}")

if __name__ == "__main__":
    target_port = 'COM6' 
    if len(sys.argv) > 1:
        target_port = sys.argv[1]
    run_servo_controller(target_port)