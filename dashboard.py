"""
================================================
  AI ROBOT DASHBOARD - Windows GUI
  Controls ESP32 Robot via WiFi / Bluetooth / USB
  AI: Google Gemini
  
  Install requirements:
  pip install google-generativeai customtkinter
              pyserial SpeechRecognition pyaudio
              pillow requests bleak
================================================
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import customtkinter as ctk
import threading
import time
import requests
import serial
import serial.tools.list_ports
import socket
import speech_recognition as sr
import google.generativeai as genai
import queue
import sys
import json
import subprocess
import re
import pyttsx3
import numpy as np
import io
import wave
from datetime import datetime

# =============================================
#  THEME SETUP
# =============================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# =============================================
#  GLOBALS
# =============================================
GEMINI_API_KEY = "AIzaSyBuLfjc5rqS0vzAyaaW5ZVyD3TWMyOIBRs"

esp32_ip      = ""
serial_conn   = None
bt_conn       = None
gemini_model  = None
is_listening  = False
log_queue     = queue.Queue()
cached_bt_mac = ""

# Init TTS Engine
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 150) # Speed
tts_engine.setProperty('volume', 1.0)

CONNECTION_MODES = ["WiFi", "USB Serial", "Bluetooth"]

# =============================================
#  COMMUNICATION LAYER
# =============================================

def send_command(cmd: str) -> str:
    """Send command to ESP32 via selected connection mode."""
    mode = conn_mode_var.get()
    try:
        if mode == "WiFi":
            return send_wifi(cmd)
        elif mode == "USB Serial":
            return send_serial(cmd)
        elif mode == "Bluetooth":
            return send_bluetooth(cmd)
    except Exception as e:
        return f"ERROR: {e}"

def send_wifi(cmd: str) -> str:
    global esp32_ip
    esp32_ip = wifi_ip_entry.get().strip()
    if not esp32_ip:
        return "ERROR: No IP entered"

    if cmd.startswith("MSG:"):
        text = cmd[4:]
        r = requests.get(f"http://{esp32_ip}/message",
                         params={"text": text}, timeout=5)
        return r.text

    elif cmd.startswith("SERVO:"):
        angle = cmd[6:]
        r = requests.get(f"http://{esp32_ip}/servo",
                         params={"angle": angle}, timeout=5)
        return r.text

    elif cmd.startswith("BOTH:"):
        # BOTH:angle:text
        parts  = cmd[5:].split(":", 1)
        angle  = parts[0]
        text   = parts[1] if len(parts) > 1 else ""
        r = requests.get(f"http://{esp32_ip}/both",
                         params={"angle": angle, "text": text}, timeout=5)
        return r.text

    elif cmd == "PING":
        r = requests.get(f"http://{esp32_ip}/ping", timeout=5)
        return r.text

    elif cmd == "STATUS":
        r = requests.get(f"http://{esp32_ip}/status", timeout=5)
        return r.text

    elif cmd.startswith("AUDIO:"):
        text = cmd[6:]
        return send_audio_wifi(text)

    return "Unknown command"

def send_audio_wifi(text: str) -> str:
    global esp32_ip
    if not esp32_ip:
        return "ERROR: No IP"
    
    log("Generating TTS Audio...", "info")
    
    # Save TTS to bytes in memory
    import tempfile
    import os
    
    temp_wav = os.path.join(tempfile.gettempdir(), "temp_tts.wav")
    tts_engine.save_to_file(text, temp_wav)
    tts_engine.runAndWait()
    
    try:
        # Read the WAV, resample if necessary, extract raw PCM
        with wave.open(temp_wav, 'rb') as wf:
            framerate = wf.getframerate()
            nchannels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            frames = wf.readframes(wf.getnframes())
            
            # Convert to numpy array
            if sampwidth == 2:
                dtype = np.int16
            else:
                dtype = np.uint8
                
            audio_data = np.frombuffer(frames, dtype=dtype)
            
            # Very basic downmix to mono if stereo
            if nchannels == 2:
                audio_data = audio_data[::2] // 2 + audio_data[1::2] // 2
                
            # Send raw 16-bit PCM bytes
            raw_bytes = audio_data.astype(np.int16).tobytes()
            
            log(f"Streaming {len(raw_bytes)} bytes of audio to ESP32...", "info")
            r = requests.post(f"http://{esp32_ip}/audio", 
                              data=raw_bytes, 
                              headers={'Content-Type': 'application/octet-stream'},
                              timeout=10)
            return r.text
    except Exception as e:
        return f"Audio Error: {e}"
    finally:
        if os.path.exists(temp_wav):
            os.remove(temp_wav)

def send_serial(cmd: str) -> str:
    global serial_conn
    if serial_conn is None or not serial_conn.is_open:
        port = serial_port_var.get()
        baud = int(baud_var.get())
        serial_conn = serial.Serial(port, baud, timeout=3)
        time.sleep(2)

    serial_conn.write((cmd + "\n").encode())
    time.sleep(0.3)
    response = ""
    while serial_conn.in_waiting:
        response += serial_conn.readline().decode(errors="ignore")
    return response.strip() or "Sent"

def send_bluetooth(cmd: str) -> str:
    # Uses socket RFCOMM for Bluetooth SPP
    global bt_conn, cached_bt_mac
    if not cached_bt_mac:
        refresh_bt_mac()

    if not cached_bt_mac:
        return "ERROR: AI_ROBOT_ESP32 not found"

    if bt_conn is None:
        bt_conn = socket.socket(socket.AF_BLUETOOTH,
                                socket.SOCK_STREAM,
                                socket.BTPROTO_RFCOMM)
        try:
            bt_conn.connect((cached_bt_mac, 1))
        except Exception as e:
            bt_conn = None
            return f"ERROR: BT Connect failed ({e})"

    try:
        bt_conn.send((cmd + "\n").encode())
        time.sleep(0.3)
        response = bt_conn.recv(1024).decode(errors="ignore")
        return response.strip()
    except:
        bt_conn = None
        return "Sent"

def auto_detect_bt_mac():
    global cached_bt_mac
    try:
        cmd = 'powershell -NoProfile -Command "Get-PnpDevice -Class Bluetooth | Where-Object { $_.FriendlyName -like \'*AI_ROBOT*\' -or $_.FriendlyName -like \'*ESP32*\' } | Select-Object -ExpandProperty InstanceId"'
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True, creationflags=0x08000000)
        match = re.search(r'DEV_([0-9A-F]{12})', result.stdout, re.IGNORECASE)
        if match:
            mac_hex = match.group(1)
            cached_bt_mac = ':'.join(mac_hex[i:i+2] for i in range(0, 12, 2))
            return cached_bt_mac
    except Exception as e:
        pass
    return ""

def refresh_bt_mac():
    mac = auto_detect_bt_mac()
    if mac:
        bt_status_label.configure(text=f"Status: Found MAC {mac}", text_color="#00ff88")
        log(f"Auto-detected ESP32 Bluetooth: {mac}", "success")
    else:
        bt_status_label.configure(text="Status: Not found (Pair in Windows)", text_color="#ffaa00")

# =============================================
#  GEMINI AI
# =============================================

def init_gemini():
    global gemini_model
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_API_KEY_HERE":
        log("ERROR: Please set GEMINI_API_KEY in the code!", "error")
        return False
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel("gemini-pro")
        log("Gemini AI connected!", "success")
        return True
    except Exception as e:
        log(f"Gemini error: {e}", "error")
        return False

def ask_gemini(question: str) -> str:
    global gemini_model
    if gemini_model is None:
        if not init_gemini():
            return "Gemini not connected."
    try:
        response = gemini_model.generate_content(
            f"You are a helpful robot assistant. Answer briefly in 1-2 sentences. Question: {question}"
        )
        return response.text.strip()
    except Exception as e:
        return f"Gemini error: {e}"

# =============================================
#  VOICE RECOGNITION
# =============================================

recognizer = sr.Recognizer()

def start_listening():
    global is_listening
    if is_listening:
        return
    is_listening = True
    listen_btn.configure(text="🔴 Listening...", fg_color="#cc0000")
    threading.Thread(target=listen_thread, daemon=True).start()

def listen_thread():
    global is_listening
    try:
        with sr.Microphone() as source:
            log("Adjusting for ambient noise...", "info")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            log("Listening... Speak now!", "info")
            audio = recognizer.listen(source, timeout=8)
            text  = recognizer.recognize_google(audio)
            log(f"You said: {text}", "user")

            # Update input box
            user_input.delete(0, tk.END)
            user_input.insert(0, text)

            # Process
            if message_mode_var.get() == "AI":
                process_input(text)
            else:
                process_direct(text)

    except sr.WaitTimeoutError:
        log("No speech detected.", "warning")
    except sr.UnknownValueError:
        log("Could not understand audio.", "warning")
    except Exception as e:
        log(f"Mic error: {e}", "error")
    finally:
        is_listening = False
        listen_btn.configure(text="🎤 Listen", fg_color="#1f538d")

def process_direct(text: str):
    """Send text directly to ESP32 to be spoken/displayed."""
    log("Sending directly...", "info")
    
    # Update response box
    response_box.configure(state="normal")
    response_box.delete("1.0", tk.END)
    response_box.insert(tk.END, f"[Direct Message] {text}")
    response_box.configure(state="disabled")

    # Detect direction angle
    angle = detect_direction(text)
    angle_slider.set(angle)

    # Send to ESP32
    cmd    = f"BOTH:{angle}:{text}"
    result = send_command(cmd)
    log(f"ESP32 response: {result}", "info")

def process_input(text: str):
    """Send text to Gemini, then send response to ESP32."""
    log("Asking Gemini...", "info")
    ai_response = ask_gemini(text)
    log(f"Gemini: {ai_response}", "ai")

    # Update response box
    response_box.configure(state="normal")
    response_box.delete("1.0", tk.END)
    response_box.insert(tk.END, ai_response)
    response_box.configure(state="disabled")

    # Detect direction angle
    angle = detect_direction(text)
    angle_slider.set(angle)

    # 1. Send the BOTH command (Servo + OLED) quickly
    cmd    = f"BOTH:{angle}:{ai_response}"
    result = send_command(cmd)
    log(f"ESP32 response (Both): {result}", "info")
    
    # 2. If WiFi, stream the audio!
    if conn_mode_var.get() == "WiFi":
        audio_res = send_command(f"AUDIO:{ai_response}")
        log(f"ESP32 Audio Result: {audio_res}", "info")

def detect_direction(text: str) -> int:
    text = text.lower()
    if any(w in text for w in ["left", "this side"]):
        return 45
    elif any(w in text for w in ["right"]):
        return 135
    elif any(w in text for w in ["front", "forward", "center"]):
        return 90
    return 90

# =============================================
#  LOGGING
# =============================================

def log(message: str, level: str = "info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    colors = {
        "info":    "[INFO]   ",
        "success": "[OK]     ",
        "error":   "[ERROR]  ",
        "warning": "[WARN]   ",
        "user":    "[YOU]    ",
        "ai":      "[GEMINI] ",
    }
    prefix = colors.get(level, "[INFO]   ")
    entry  = f"{timestamp} {prefix} {message}\n"
    log_queue.put((entry, level))

def update_log():
    color_map = {
        "info":    "#aaaaaa",
        "success": "#00ff88",
        "error":   "#ff4444",
        "warning": "#ffaa00",
        "user":    "#44aaff",
        "ai":      "#cc88ff",
    }
    while not log_queue.empty():
        entry, level = log_queue.get()
        log_box.configure(state="normal")
        color = color_map.get(level, "#aaaaaa")
        log_box.insert(tk.END, entry)
        log_box.tag_add(level, f"end-{len(entry)+1}c", "end-1c")
        log_box.tag_configure(level, foreground=color)
        log_box.see(tk.END)
        log_box.configure(state="disabled")
    root.after(100, update_log)

# =============================================
#  TOOLBAR ACTIONS
# =============================================

def ping_robot():
    result = send_command("PING")
    log(f"Ping result: {result}", "success" if "PONG" in result else "error")

def get_status():
    result = send_command("STATUS")
    log(f"Status: {result}", "info")

def send_manual():
    text = user_input.get().strip()
    if not text:
        return
    log(f"Manual input: {text}", "user")
    if message_mode_var.get() == "AI":
        threading.Thread(target=process_input, args=(text,), daemon=True).start()
    else:
        threading.Thread(target=process_direct, args=(text,), daemon=True).start()

def send_servo_angle():
    angle = int(angle_slider.get())
    result = send_command(f"SERVO:{angle}")
    log(f"Servo set to {angle}°: {result}", "info")

def connect_serial():
    global serial_conn
    try:
        port = serial_port_var.get()
        baud = int(baud_var.get())
        serial_conn = serial.Serial(port, baud, timeout=3)
        time.sleep(2)
        log(f"USB Serial connected: {port} @ {baud}", "success")
        serial_status.configure(text="● Connected", text_color="#00ff88")
    except Exception as e:
        log(f"Serial error: {e}", "error")

def disconnect_serial():
    global serial_conn
    if serial_conn:
        serial_conn.close()
        serial_conn = None
        log("USB Serial disconnected", "warning")
        serial_status.configure(text="● Disconnected", text_color="#ff4444")

def refresh_ports():
    ports = [p.device for p in serial.tools.list_ports.comports()]
    serial_port_combo["values"] = ports
    if ports:
        serial_port_var.set(ports[0])
    log(f"Found ports: {ports}", "info")

def clear_log():
    log_box.configure(state="normal")
    log_box.delete("1.0", tk.END)
    log_box.configure(state="disabled")

# =============================================
#  GUI LAYOUT
# =============================================

root = ctk.CTk()
root.title("🤖 AI Robot Dashboard")
root.geometry("1100x750")
root.resizable(True, True)

# ---- Header ----
header = ctk.CTkFrame(root, height=60, fg_color="#0d1117")
header.pack(fill="x", padx=0, pady=0)
ctk.CTkLabel(header, text="🤖  AI ROBOT CONTROL DASHBOARD",
             font=("Consolas", 20, "bold"),
             text_color="#00ff88").pack(side="left", padx=20, pady=10)
ctk.CTkLabel(header, text="Powered by Google Gemini",
             font=("Consolas", 12),
             text_color="#888888").pack(side="right", padx=20)

# ---- Main Container ----
main = ctk.CTkFrame(root, fg_color="transparent")
main.pack(fill="both", expand=True, padx=10, pady=5)

# Left panel
left = ctk.CTkFrame(main, width=380, fg_color="#161b22")
left.pack(side="left", fill="y", padx=(0, 5), pady=0)
left.pack_propagate(False)

# Right panel
right = ctk.CTkFrame(main, fg_color="#161b22")
right.pack(side="right", fill="both", expand=True)

# =============================================
#  LEFT PANEL
# =============================================

# -- Connection Mode --
ctk.CTkLabel(left, text="📡 CONNECTION MODE",
             font=("Consolas", 11, "bold"),
             text_color="#888888").pack(anchor="w", padx=15, pady=(5, 2))
conn_mode_var = ctk.StringVar(value="WiFi")
for mode in CONNECTION_MODES:
    ctk.CTkRadioButton(left, text=mode, variable=conn_mode_var,
                       value=mode).pack(anchor="w", padx=30, pady=1)

ctk.CTkFrame(left, height=1, fg_color="#30363d").pack(fill="x", padx=15, pady=8)

# -- WiFi Settings --
ctk.CTkLabel(left, text="🌐 WIFI SETTINGS",
             font=("Consolas", 11, "bold"),
             text_color="#888888").pack(anchor="w", padx=15, pady=(0, 2))
wifi_ip_entry = ctk.CTkEntry(left, placeholder_text="ESP32 IP e.g. 192.168.1.100", width=340)
wifi_ip_entry.pack(padx=15, pady=(0, 8))

ctk.CTkFrame(left, height=1, fg_color="#30363d").pack(fill="x", padx=15, pady=5)

# -- USB Serial Settings --
ctk.CTkLabel(left, text="🔌 USB SERIAL SETTINGS",
             font=("Consolas", 11, "bold"),
             text_color="#888888").pack(anchor="w", padx=15, pady=(0, 2))

serial_port_var = tk.StringVar(value="COM3")
baud_var        = tk.StringVar(value="115200")

port_frame = ctk.CTkFrame(left, fg_color="transparent")
port_frame.pack(fill="x", padx=15)

serial_port_combo = ttk.Combobox(port_frame, textvariable=serial_port_var, width=12)
serial_port_combo.pack(side="left", padx=(0, 5))

baud_combo = ttk.Combobox(port_frame, textvariable=baud_var,
                           values=["9600", "115200", "250000"], width=8)
baud_combo.pack(side="left", padx=(0, 5))

ctk.CTkButton(port_frame, text="🔄", width=30, command=refresh_ports).pack(side="left")

serial_btn_frame = ctk.CTkFrame(left, fg_color="transparent")
serial_btn_frame.pack(fill="x", padx=15, pady=5)
ctk.CTkButton(serial_btn_frame, text="Connect USB", width=155,
              command=connect_serial,
              fg_color="#1a472a").pack(side="left", padx=(0, 5))
ctk.CTkButton(serial_btn_frame, text="Disconnect", width=155,
              command=disconnect_serial,
              fg_color="#7d1a1a").pack(side="left")

serial_status = ctk.CTkLabel(left, text="● Disconnected", text_color="#ff4444",
                              font=("Consolas", 11))
serial_status.pack(anchor="w", padx=15)

ctk.CTkFrame(left, height=1, fg_color="#30363d").pack(fill="x", padx=15, pady=8)

# -- Bluetooth Settings --
ctk.CTkLabel(left, text="📶 BLUETOOTH SETTINGS",
             font=("Consolas", 11, "bold"),
             text_color="#888888").pack(anchor="w", padx=15, pady=(0, 2))
bt_status_label = ctk.CTkLabel(left, text="Status: Auto-detecting...",
             font=("Consolas", 10),
             text_color="#666666")
bt_status_label.pack(anchor="w", padx=15)
ctk.CTkButton(left, text="🔄 Retry Detection", width=120, height=24,
              command=refresh_bt_mac,
              fg_color="#333333").pack(anchor="w", padx=15, pady=(0, 8))

ctk.CTkFrame(left, height=1, fg_color="#30363d").pack(fill="x", padx=15, pady=5)

# -- Ping / Status --
btn_row = ctk.CTkFrame(left, fg_color="transparent")
btn_row.pack(fill="x", padx=15, pady=5)
ctk.CTkButton(btn_row, text="📡 Ping", width=155,
              command=ping_robot).pack(side="left", padx=(0, 5))
ctk.CTkButton(btn_row, text="ℹ Status", width=155,
              command=get_status).pack(side="left")

# =============================================
#  RIGHT PANEL
# =============================================

# -- Voice + Text Input --
input_frame = ctk.CTkFrame(right, fg_color="#0d1117")
input_frame.pack(fill="x", padx=10, pady=10)

header_row = ctk.CTkFrame(input_frame, fg_color="transparent")
header_row.pack(fill="x", padx=10, pady=(10, 2))

ctk.CTkLabel(header_row, text="💬 YOUR INPUT",
             font=("Consolas", 12, "bold"),
             text_color="#00ff88").pack(side="left")

message_mode_var = ctk.StringVar(value="AI")
ctk.CTkRadioButton(header_row, text="Direct Output", variable=message_mode_var, value="Direct").pack(side="right", padx=10)
ctk.CTkRadioButton(header_row, text="AI Assistant", variable=message_mode_var, value="AI").pack(side="right", padx=10)

input_row = ctk.CTkFrame(input_frame, fg_color="transparent")
input_row.pack(fill="x", padx=10, pady=(0, 10))

user_input = ctk.CTkEntry(input_row,
                           placeholder_text="Type your message or use mic...",
                           height=40, font=("Consolas", 12))
user_input.pack(side="left", fill="x", expand=True, padx=(0, 5))
user_input.bind("<Return>", lambda e: send_manual())

listen_btn = ctk.CTkButton(input_row, text="🎤 Listen", width=110, height=40,
                            command=lambda: threading.Thread(
                                target=start_listening, daemon=True).start())
listen_btn.pack(side="left", padx=(0, 5))

ctk.CTkButton(input_row, text="▶ Send", width=80, height=40,
              command=send_manual,
              fg_color="#1f538d").pack(side="left")

# -- Gemini Response --
resp_frame = ctk.CTkFrame(right, fg_color="#0d1117")
resp_frame.pack(fill="x", padx=10, pady=(0, 5))

ctk.CTkLabel(resp_frame, text="🤖 GEMINI RESPONSE",
             font=("Consolas", 12, "bold"),
             text_color="#cc88ff").pack(anchor="w", padx=10, pady=(10, 2))

response_box = ctk.CTkTextbox(resp_frame, height=80,
                               font=("Consolas", 12),
                               fg_color="#161b22",
                               text_color="#ffffff")
response_box.pack(fill="x", padx=10, pady=(0, 10))
response_box.configure(state="disabled")

# -- Servo Control --
servo_frame = ctk.CTkFrame(right, fg_color="#0d1117")
servo_frame.pack(fill="x", padx=10, pady=(0, 5))

ctk.CTkLabel(servo_frame, text="🔄 SERVO ANGLE CONTROL",
             font=("Consolas", 12, "bold"),
             text_color="#ffaa00").pack(anchor="w", padx=10, pady=(10, 2))

slider_row = ctk.CTkFrame(servo_frame, fg_color="transparent")
slider_row.pack(fill="x", padx=10, pady=(0, 10))

angle_slider = ctk.CTkSlider(slider_row, from_=0, to=180,
                              number_of_steps=180, width=300)
angle_slider.set(90)
angle_slider.pack(side="left", padx=(0, 10))

angle_label = ctk.CTkLabel(slider_row, text="90°",
                            font=("Consolas", 14, "bold"),
                            text_color="#ffaa00", width=50)
angle_label.pack(side="left")

def update_angle_label(val):
    angle_label.configure(text=f"{int(float(val))}°")

angle_slider.configure(command=update_angle_label)

ctk.CTkButton(slider_row, text="Set Servo", width=100,
              command=send_servo_angle,
              fg_color="#7d5a00").pack(side="left", padx=10)

# Quick angle buttons
quick_frame = ctk.CTkFrame(servo_frame, fg_color="transparent")
quick_frame.pack(fill="x", padx=10, pady=(0, 10))
for angle in [0, 45, 90, 135, 180]:
    ctk.CTkButton(quick_frame, text=f"{angle}°", width=60,
                  command=lambda a=angle: [angle_slider.set(a),
                                           angle_label.configure(text=f"{a}°"),
                                           send_command(f"SERVO:{a}"),
                                           log(f"Quick servo: {a}°", "info")]
                  ).pack(side="left", padx=3)

# -- Activity Log --
log_frame = ctk.CTkFrame(right, fg_color="#0d1117")
log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
log_header.pack(fill="x", padx=10, pady=(10, 2))
ctk.CTkLabel(log_header, text="📋 ACTIVITY LOG",
             font=("Consolas", 12, "bold"),
             text_color="#44aaff").pack(side="left")
ctk.CTkButton(log_header, text="Clear", width=60, height=24,
              command=clear_log,
              fg_color="#333333").pack(side="right")

log_box = tk.Text(log_frame,
                  bg="#0d1117", fg="#aaaaaa",
                  font=("Consolas", 10),
                  state="disabled",
                  relief="flat",
                  wrap="word")
log_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

scrollbar = ttk.Scrollbar(log_frame, command=log_box.yview)
log_box.configure(yscrollcommand=scrollbar.set)

# =============================================
#  START
# =============================================

refresh_ports()
refresh_bt_mac()
log("Dashboard started! Configure connection and click Ping to test.", "success")
log("Steps: 1) Pick WiFi/USB/BT  2) Enter IP/Port  3) Ping!  4) Send message!", "info")
init_gemini()

root.after(100, update_log)
root.mainloop()
