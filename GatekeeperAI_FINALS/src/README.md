# GATEKEEPER AI  
### An Agentic AI-Driven Detection and Response System

**Manalo, Guian Jaundell R.**  
Computer Engineering Student  
University of Batangas – Lipa Campus

Gatekeeper AI is a smart door notification system that uses an ESP32, sensors, and a local AI server to detect visitors and display the user’s availability on an LCD screen. It can show messages such as attending online classes, studying, or being available, while also sending Telegram notifications to the owner. The project helps reduce interruptions and improve focus, privacy, and communication through automation and artificial intelligence.

---

## Features

- PIR motion detection using ESP32
- AI-generated LCD messages based on schedule availability
- Telegram notifications
- Local AI processing with LM Studio
- Flask-based Python server
- Automatic LCD text scrolling
- Optional buzzer alerts

---

## Hardware Components

- ESP32
- PIR Motion Sensor
- 16×2 I2C LCD
- Breadboard
- Jumper Wires
- Buzzer (optional)
- 5V–12V Power Supply

---

## Software Requirements

### ESP32 Libraries

Install the following libraries:

- `WiFi.h`
- `HTTPClient.h`
- `ArduinoJson`
- `LiquidCrystal_I2C`

### Python Packages

Install the required Python packages:

```bash
pip install flask openai requests
```

### Additional Software

- Arduino IDE / Visual Studio Code with Platform IO extension
- LM Studio with a local AI model installed
- Telegram Bot API

---

## Pin Configuration

| Component | ESP32 Pin |
|---|---|
| PIR Sensor | GPIO 13 |
| Buzzer | GPIO 14 |
| LCD SDA | GPIO 21 |
| LCD SCL | GPIO 22 |

---

## System Workflow

1. PIR sensor detects movement near the door.
2. ESP32 sends an HTTP request to the Flask server.
3. The Flask server communicates with the AI model in LM Studio.
4. The AI checks the current schedule and availability.
5. A short response is generated for the LCD display.
6. The message is shown on the LCD screen.
7. A Telegram notification is sent to the owner.

---

## Running the Project

### 1. Upload ESP32 Code

Upload the Arduino sketch to the ESP32 using Arduino IDE.

### 2. Start LM Studio

Open LM Studio and load your preferred local AI model.

### 3. Run the Python Server

```bash
python gatekeeper_agent.py
```