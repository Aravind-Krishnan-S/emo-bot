<p align="center">
  <h1 align="center">🤖 Emo Bot — AI-Powered Emotion-Aware Robot</h1>
  <p align="center">
    An ESP32-based robot that responds with expressive OLED facial animations, voice synthesis, and AI-driven conversations powered by Google Gemini.
  </p>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-ESP32-blue?style=for-the-badge&logo=espressif" />
  <img src="https://img.shields.io/badge/AI-Google%20Gemini-blueviolet?style=for-the-badge&logo=google" />
  <img src="https://img.shields.io/badge/Dashboard-Python-green?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" />
</p>

---

## 📖 Overview

**Emo Bot** is a full-stack robotics project that combines hardware and software to create an emotionally responsive AI robot. Speak to it, and it listens — processes your words with Google Gemini — then responds with a matching facial expression on its OLED display, speaks the answer through a speaker, and even rotates its servo to face the direction of sound.

### ✨ Key Features

| Feature | Description |
|---|---|
| 🎭 **10 Facial Expressions** | Happy, Sad, Angry, Surprised, Love, Confused, Thinking, Wink, Sleepy, Normal |
| 🧠 **AI Conversations** | Google Gemini 2.0 Flash generates emotion-tagged responses |
| 🎤 **Voice Recognition** | Speak naturally — the bot transcribes and processes your speech |
| 🔊 **Text-to-Speech** | TTS audio streamed to the ESP32's MAX98357A speaker |
| 🎙️ **Live Robot Mic** | Stream and transcribe audio from the robot's onboard INMP441 microphone |
| 📡 **Multi-Connectivity** | WiFi, USB Serial, and Bluetooth SPP connections |
| 🎛️ **Desktop Dashboard** | Rich dark-themed GUI built with CustomTkinter |
| 💾 **Persistent Memory** | Robot remembers its last expression and servo angle (NVS storage) |
| 😉 **Auto Blink & Idle** | Lifelike auto-blink and idle expression cycling |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PYTHON DESKTOP DASHBOARD                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐   │
│  │  GUI     │  │  Gemini  │  │  Voice   │  │  Comms Layer  │   │
│  │ (CTk)   │──│  AI      │  │  (STT)   │  │ WiFi/USB/BT   │   │
│  └──────────┘  └──────────┘  └──────────┘  └───────┬───────┘   │
│                                                     │           │
└─────────────────────────────────────────────────────┼───────────┘
                                                      │
                    ┌─────────────── HTTP / Serial / BT ──┐
                    │                                      │
┌───────────────────┼──────────────────────────────────────┼──────┐
│                   ▼        ESP32 FIRMWARE                │      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  Command Processor                       │   │
│  │  PING │ STATUS │ MSG │ EXPR │ SERVO │ BOTH │ ALL │ AUDIO│   │
│  └──────┬───────────┬───────────┬───────────┬───────────────┘   │
│         │           │           │           │                   │
│  ┌──────▼──┐  ┌─────▼────┐  ┌──▼──────┐  ┌─▼──────────────┐   │
│  │  OLED   │  │  Servo   │  │  I2S    │  │  WiFi Server   │   │
│  │ Display │  │  Motor   │  │ Mic+Amp │  │  (HTTP API)    │   │
│  │ (U8g2)  │  │ (GPIO13) │  │ I2S 0+1 │  │  Port 80       │   │
│  └─────────┘  └──────────┘  └─────────┘  └────────────────┘   │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │            Persistent Storage (NVS Preferences)          │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔌 Hardware Wiring

```
ESP32 DevKit v1
┌────────────────────────────┐
│                            │
│  GPIO 21 (SDA) ───►  OLED SSD1306 (SDA)
│  GPIO 22 (SCL) ───►  OLED SSD1306 (SCL)
│                            │
│  GPIO 14 (SCK) ───►  INMP441 Mic (SCK)
│  GPIO 15 (WS)  ───►  INMP441 Mic (WS)
│  GPIO 32 (SD)  ───►  INMP441 Mic (SD)
│                            │
│  GPIO 26 (BCLK)───►  MAX98357A Amp (BCLK)
│  GPIO 25 (LRC) ───►  MAX98357A Amp (LRC)
│  GPIO 27 (DIN) ───►  MAX98357A Amp (DIN)
│                            │
│  GPIO 13 ──────────►  Servo Motor (Signal)
│                            │
│  3.3V ─────────────►  OLED VCC, INMP441 VCC
│  5V   ─────────────►  Servo VCC, MAX98357A VIN
│  GND  ─────────────►  All GND pins
└────────────────────────────┘
```

### 🛒 Bill of Materials

| Component | Purpose | Interface |
|---|---|---|
| ESP32 DevKit v1 | Main microcontroller | — |
| SSD1306 OLED (128×64) | Facial expression display | I2C (SDA=21, SCL=22) |
| INMP441 MEMS Mic | Voice input / ambient audio | I2S RX (Port 0) |
| MAX98357A I2S Amp | Audio output / TTS playback | I2S TX (Port 1) |
| SG90 Servo Motor | Head rotation (0°–180°) | PWM (GPIO 13) |
| Speaker (3W 4Ω) | Connected to MAX98357A | Analog |

---

## 📁 Project Structure

```
Emo Bot/
├── main.py                     # Entry point — launches the desktop dashboard
├── dashboard.py                # Legacy single-file dashboard (reference)
├── requirements.txt            # Python dependencies
├── .env                        # API keys (not committed)
├── .gitignore                  # Git ignore rules
│
├── app/                        # Modular Python application
│   ├── __init__.py             # Package init
│   ├── config.py               # Shared config, env loading, global state
│   ├── gui.py                  # CustomTkinter GUI layout & event handlers
│   ├── comms.py                # Communication layer (WiFi, USB, Bluetooth, TTS)
│   ├── gemini_ai.py            # Gemini AI integration with emotion parsing
│   ├── voice.py                # Speech-to-Text (Google Speech Recognition)
│   └── logger.py               # Threadsafe logging utility
│
└── robot_firmware/
    └── robot_firmware.ino      # Arduino/ESP32 firmware (complete)
```

---

## 🔄 Data Flow

```
                         ┌──────────────┐
                         │   User       │
                         │  (Voice/Text)│
                         └──────┬───────┘
                                │
                    ┌───────────▼───────────┐
                    │   Speech Recognition  │
                    │   (Google STT)        │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Google Gemini AI    │
                    │   (gemini-2.0-flash)  │
                    │                       │
                    │ Input:  User question │
                    │ Output: EMOTION:expr  │
                    │         |TEXT:response │
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                  │
     ┌────────▼──────┐  ┌──────▼──────┐  ┌───────▼───────┐
     │  EXPR:emotion │  │ SERVO:angle │  │  AUDIO:tts    │
     │  → OLED face  │  │ → Head turn │  │  → Speaker    │
     └───────────────┘  └─────────────┘  └───────────────┘
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.9+** installed on your PC
- **Arduino IDE** with ESP32 board support
- **Google Gemini API Key** — get one at [Google AI Studio](https://aistudio.google.com/apikey)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/emo-bot.git
cd emo-bot
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_api_key_here
```

### 4. Flash the ESP32 Firmware

1. Open `robot_firmware/robot_firmware.ino` in Arduino IDE
2. Update the WiFi credentials (lines 28–29):
   ```cpp
   const char* ssid     = "YOUR_WIFI_SSID";
   const char* password = "YOUR_WIFI_PASSWORD";
   ```
3. Install required Arduino libraries:
   - `U8g2` — OLED display driver
   - `ESP32Servo` — Servo motor control
4. Select board: **ESP32 Dev Module**
5. Upload the firmware

### 5. Launch the Dashboard

```bash
python main.py
```

---

## 🎛️ Dashboard Guide

### Connection Setup

| Mode | How to Connect |
|---|---|
| **WiFi** | Enter the ESP32's IP address (shown on OLED at boot) and click Connect |
| **USB Serial** | Select the COM port, set baud to 115200, click Connect USB |
| **Bluetooth** | Pair "AI_ROBOT_ESP32" in Windows Settings → auto-detected |

### Sending Commands

- **AI Assistant Mode** — Your text goes to Gemini, the AI picks an emotion and generates a response
- **Direct Mode** — Your text is sent directly to the robot's OLED display

### ESP32 HTTP API

| Endpoint | Method | Parameters | Description |
|---|---|---|---|
| `/ping` | GET | — | Health check |
| `/status` | GET | — | Returns JSON with angle, expression, mode, volume |
| `/message` | GET | `text` | Scroll text on OLED |
| `/expr` | GET | `expr` | Set facial expression |
| `/servo` | GET | `angle` | Rotate servo (0–180) |
| `/all` | GET | `angle`, `expr`, `text` | Set servo + expression + message |
| `/audio` | POST | Raw PCM body | Play 16-bit 16kHz audio through speaker |
| `/mic_stream` | GET | — | Get ~0.5s of raw 16-bit PCM from onboard mic |

---

## 🎭 Supported Expressions

| Expression | Description | Trigger |
|---|---|---|
| `normal` | Default round eyes with centered pupils | Neutral responses |
| `happy` | Half-circle "smiling" eyes | Jokes, good news |
| `sad` | Droopy eyes with tear drops | Empathetic responses |
| `angry` | Furrowed brow, inward-looking pupils | Frustration |
| `surprised` | Wide-open eyes, raised eyebrows | Unexpected input |
| `wink` | Left eye open, right eye closed | Playful responses |
| `sleepy` | Half-closed eyes with "z z z" | Tired/waiting |
| `love` | Heart-shaped eyes | Affectionate topics |
| `confused` | Asymmetric eyes with "?" | Unclear questions |
| `thinking` | Eyes looking up-right with "..." | Processing |
| `blink` | Smooth animated blink | Auto (periodic) |

---

## 🛡️ Rate Limiting

The Gemini AI integration includes built-in rate limiting to protect your API quota:

- **Cooldown:** Minimum 5 seconds between requests
- **Hourly cap:** Maximum 30 requests per hour
- Remaining credits are displayed in the activity log

---

## 🏗️ Building a Standalone Executable

Package the dashboard as a portable `.exe` using PyInstaller:

```bash
pip install pyinstaller
pyinstaller --noconfirm --onedir --windowed --name EmoBotDashboard main.py
```

The executable will be in `dist/EmoBotDashboard/`.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Google Gemini** — AI backbone for emotion-aware conversations
- **U8g2** — Excellent monochrome display library for Arduino
- **CustomTkinter** — Modern dark-themed Python GUI framework
- **ESP32 Arduino Core** — Making IoT accessible

---

<p align="center">
  Built with ❤️ and 🤖
</p>
