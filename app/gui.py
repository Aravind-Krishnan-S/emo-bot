"""
GUI Layout and event handlers for the AI Robot Dashboard.
All blocking operations are wrapped in threads to keep the UI responsive.
"""
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import threading
import requests
import struct
import io
import wave
import speech_recognition as sr
import numpy as np

from app import config
from app.logger import log
from app.comms import (
    send_command, connect_serial, disconnect_serial,
    list_serial_ports, auto_detect_bt_mac
)
from app.gemini_ai import init_gemini, ask_gemini
from app.voice import listen_once

# =============================================
#  THEME
# =============================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# =============================================
#  HELPER: Direction Detection
# =============================================
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
#  BUILD GUI
# =============================================
def build_app():
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

    left = ctk.CTkFrame(main, width=380, fg_color="#161b22")
    left.pack(side="left", fill="y", padx=(0, 5), pady=0)
    left.pack_propagate(False)

    right = ctk.CTkFrame(main, fg_color="#161b22")
    right.pack(side="right", fill="both", expand=True)

    # =============================================
    #  LEFT PANEL
    # =============================================

    # -- Connection Mode --
    ctk.CTkLabel(left, text="📡 CONNECTION MODE",
                 font=("Consolas", 11, "bold"),
                 text_color="#888888").pack(anchor="w", padx=15, pady=(15, 2))
    conn_mode_var = ctk.StringVar(value="WiFi")
    for mode in config.CONNECTION_MODES:
        ctk.CTkRadioButton(left, text=mode, variable=conn_mode_var,
                           value=mode).pack(anchor="w", padx=30, pady=1)

    ctk.CTkFrame(left, height=1, fg_color="#30363d").pack(fill="x", padx=15, pady=8)

    # -- WiFi Settings --
    ctk.CTkLabel(left, text="🌐 WIFI SETTINGS",
                 font=("Consolas", 11, "bold"),
                 text_color="#888888").pack(anchor="w", padx=15, pady=(0, 2))

    wifi_frame = ctk.CTkFrame(left, fg_color="transparent")
    wifi_frame.pack(fill="x", padx=15, pady=(0, 8))

    wifi_ip_entry = ctk.CTkEntry(wifi_frame, placeholder_text="ESP32 IP e.g. 192.168.1.100",
                                  width=250)
    wifi_ip_entry.pack(side="left", padx=(0, 5))

    def save_wifi_ip():
        ip = wifi_ip_entry.get().strip()
        if ip:
            config.esp32_ip = ip
            log(f"WiFi IP set: {ip}", "success")
        else:
            log("Please enter an IP address", "warning")

    ctk.CTkButton(wifi_frame, text="Connect", width=80, height=28,
                  command=save_wifi_ip,
                  fg_color="#1a472a", hover_color="#2d6a4f").pack(side="left")

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

    def refresh_ports():
        ports = list_serial_ports()
        serial_port_combo["values"] = ports
        if ports:
            serial_port_var.set(ports[0])
        log(f"Found ports: {ports}", "info")

    ctk.CTkButton(port_frame, text="🔄", width=30, command=refresh_ports).pack(side="left")

    serial_status = ctk.CTkLabel(left, text="● Disconnected", text_color="#ff4444",
                                  font=("Consolas", 11))

    serial_btn_frame = ctk.CTkFrame(left, fg_color="transparent")
    serial_btn_frame.pack(fill="x", padx=15, pady=5)

    def do_connect_serial():
        def _worker():
            port = serial_port_var.get()
            baud = int(baud_var.get())
            ok, msg = connect_serial(port, baud)
            if ok:
                log(msg, "success")
                serial_status.configure(text="● Connected", text_color="#00ff88")
            else:
                log(msg, "error")
        threading.Thread(target=_worker, daemon=True).start()

    def do_disconnect_serial():
        disconnect_serial()
        log("USB Serial disconnected", "warning")
        serial_status.configure(text="● Disconnected", text_color="#ff4444")

    ctk.CTkButton(serial_btn_frame, text="Connect USB", width=155,
                  command=do_connect_serial,
                  fg_color="#1a472a").pack(side="left", padx=(0, 5))
    ctk.CTkButton(serial_btn_frame, text="Disconnect", width=155,
                  command=do_disconnect_serial,
                  fg_color="#7d1a1a").pack(side="left")

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

    def refresh_bt_mac():
        def _worker():
            mac = auto_detect_bt_mac()
            if mac:
                bt_status_label.configure(text=f"Status: Found MAC {mac}", text_color="#00ff88")
                log(f"Auto-detected ESP32 Bluetooth: {mac}", "success")
            else:
                bt_status_label.configure(text="Status: Not found (Pair in Windows)", text_color="#ffaa00")
        threading.Thread(target=_worker, daemon=True).start()

    ctk.CTkButton(left, text="🔄 Retry Detection", width=120, height=24,
                  command=refresh_bt_mac,
                  fg_color="#333333").pack(anchor="w", padx=15, pady=(0, 8))

    ctk.CTkFrame(left, height=1, fg_color="#30363d").pack(fill="x", padx=15, pady=5)

    # -- Ping / Status --
    btn_row = ctk.CTkFrame(left, fg_color="transparent")
    btn_row.pack(fill="x", padx=15, pady=5)

    def ping_robot():
        def _worker():
            result = send_command("PING", conn_mode_var.get())
            log(f"Ping result: {result}", "success" if "PONG" in result else "error")
        threading.Thread(target=_worker, daemon=True).start()

    def get_status():
        def _worker():
            result = send_command("STATUS", conn_mode_var.get())
            log(f"Status: {result}", "info")
        threading.Thread(target=_worker, daemon=True).start()

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
    ctk.CTkRadioButton(header_row, text="Direct Output", variable=message_mode_var,
                       value="Direct").pack(side="right", padx=10)
    ctk.CTkRadioButton(header_row, text="AI Assistant", variable=message_mode_var,
                       value="AI").pack(side="right", padx=10)

    input_row = ctk.CTkFrame(input_frame, fg_color="transparent")
    input_row.pack(fill="x", padx=10, pady=(0, 10))

    user_input = ctk.CTkEntry(input_row,
                               placeholder_text="Type your message or use mic...",
                               height=40, font=("Consolas", 12))
    user_input.pack(side="left", fill="x", expand=True, padx=(0, 5))

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

    # -- Live Robot Mic Transcription --
    mic_frame = ctk.CTkFrame(right, fg_color="#0d1117")
    mic_frame.pack(fill="x", padx=10, pady=(0, 5))

    mic_header = ctk.CTkFrame(mic_frame, fg_color="transparent")
    mic_header.pack(fill="x", padx=10, pady=(10, 2))

    ctk.CTkLabel(mic_header, text="🎙️ LIVE ROBOT MIC",
                 font=("Consolas", 12, "bold"),
                 text_color="#ff6b6b").pack(side="left")

    mic_streaming = {"active": False}

    mic_status_label = ctk.CTkLabel(mic_header, text="● Stopped",
                                     font=("Consolas", 10),
                                     text_color="#ff4444")
    mic_status_label.pack(side="right", padx=10)

    transcript_box = ctk.CTkTextbox(mic_frame, height=70,
                                     font=("Consolas", 11),
                                     fg_color="#161b22",
                                     text_color="#ff6b6b")
    transcript_box.pack(fill="x", padx=10, pady=(2, 5))
    transcript_box.configure(state="disabled")

    mic_btn_row = ctk.CTkFrame(mic_frame, fg_color="transparent")
    mic_btn_row.pack(fill="x", padx=10, pady=(0, 10))

    def mic_stream_worker():
        """Continuously poll ESP32 /mic_stream and transcribe."""
        recognizer = sr.Recognizer()
        audio_buffer = b""
        chunk_count = 0

        while mic_streaming["active"]:
            try:
                ip = config.esp32_ip
                if not ip:
                    log("Robot Mic: Set WiFi IP first", "warning")
                    break

                r = requests.get(f"http://{ip}/mic_stream", timeout=3)
                if r.status_code != 200:
                    continue

                audio_buffer += r.content
                chunk_count += 1

                # Transcribe every 4 chunks (~2 seconds of audio)
                if chunk_count >= 4:
                    try:
                        # Wrap raw PCM into a WAV for speech_recognition
                        wav_io = io.BytesIO()
                        with wave.open(wav_io, 'wb') as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(2)  # 16-bit
                            wf.setframerate(16000)
                            wf.writeframes(audio_buffer)
                        wav_io.seek(0)

                        audio_data = sr.AudioFile(wav_io)
                        with audio_data as source:
                            audio = recognizer.record(source)

                        text = recognizer.recognize_google(audio)
                        if text:
                            log(f"Robot heard: {text}", "user")
                            transcript_box.configure(state="normal")
                            transcript_box.insert("end", text + "\n")
                            transcript_box.see("end")
                            transcript_box.configure(state="disabled")
                    except sr.UnknownValueError:
                        pass  # silence, skip
                    except Exception as e:
                        log(f"Transcription error: {e}", "warning")

                    audio_buffer = b""
                    chunk_count = 0

            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.ConnectionError:
                log("Robot Mic: Lost connection to ESP32", "error")
                break
            except Exception as e:
                log(f"Mic stream error: {e}", "error")
                break

        mic_streaming["active"] = False
        mic_status_label.configure(text="● Stopped", text_color="#ff4444")
        start_mic_btn.configure(text="▶ Start Listening", fg_color="#1a472a")

    def toggle_mic_stream():
        if mic_streaming["active"]:
            mic_streaming["active"] = False
            log("Robot Mic: Stopping...", "info")
        else:
            mic_streaming["active"] = True
            mic_status_label.configure(text="● Streaming", text_color="#00ff88")
            start_mic_btn.configure(text="⏹ Stop", fg_color="#7d1a1a")
            log("Robot Mic: Streaming started", "success")
            threading.Thread(target=mic_stream_worker, daemon=True).start()

    start_mic_btn = ctk.CTkButton(mic_btn_row, text="▶ Start Listening", width=150, height=28,
                                   command=toggle_mic_stream,
                                   fg_color="#1a472a", hover_color="#2d6a4f")
    start_mic_btn.pack(side="left", padx=(0, 5))

    def clear_transcript():
        transcript_box.configure(state="normal")
        transcript_box.delete("1.0", tk.END)
        transcript_box.configure(state="disabled")

    ctk.CTkButton(mic_btn_row, text="Clear", width=60, height=28,
                  command=clear_transcript,
                  fg_color="#333333").pack(side="left")

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

    def send_servo_angle():
        def _worker():
            angle = int(angle_slider.get())
            result = send_command(f"SERVO:{angle}", conn_mode_var.get())
            log(f"Servo set to {angle}°: {result}", "info")
        threading.Thread(target=_worker, daemon=True).start()

    ctk.CTkButton(slider_row, text="Set Servo", width=100,
                  command=send_servo_angle,
                  fg_color="#7d5a00").pack(side="left", padx=10)

    quick_frame = ctk.CTkFrame(servo_frame, fg_color="transparent")
    quick_frame.pack(fill="x", padx=10, pady=(0, 10))
    for angle in [0, 45, 90, 135, 180]:
        def quick_servo(a=angle):
            def _worker():
                angle_slider.set(a)
                angle_label.configure(text=f"{a}°")
                send_command(f"SERVO:{a}", conn_mode_var.get())
                log(f"Quick servo: {a}°", "info")
            threading.Thread(target=_worker, daemon=True).start()
        ctk.CTkButton(quick_frame, text=f"{angle}°", width=60,
                      command=quick_servo).pack(side="left", padx=3)

    # -- Activity Log --
    log_frame = ctk.CTkFrame(right, fg_color="#0d1117")
    log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
    log_header.pack(fill="x", padx=10, pady=(10, 2))
    ctk.CTkLabel(log_header, text="📋 ACTIVITY LOG",
                 font=("Consolas", 12, "bold"),
                 text_color="#44aaff").pack(side="left")

    def clear_log():
        log_box.configure(state="normal")
        log_box.delete("1.0", tk.END)
        log_box.configure(state="disabled")

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
    #  INPUT PROCESSING (threaded)
    # =============================================
    def process_direct(text: str):
        log("Sending directly...", "info")
        response_box.configure(state="normal")
        response_box.delete("1.0", tk.END)
        response_box.insert(tk.END, f"[Direct Message] {text}")
        response_box.configure(state="disabled")

        angle = detect_direction(text)
        angle_slider.set(angle)

        cmd    = f"BOTH:{angle}:{text}"
        result = send_command(cmd, conn_mode_var.get())
        log(f"ESP32 response: {result}", "info")

    def process_input(text: str):
        log("Asking Gemini...", "info")
        ai_response, emotion = ask_gemini(text)
        log(f"Gemini [{emotion}]: {ai_response}", "ai")

        response_box.configure(state="normal")
        response_box.delete("1.0", tk.END)
        response_box.insert(tk.END, f"[{emotion}] {ai_response}")
        response_box.configure(state="disabled")

        angle = detect_direction(text)
        angle_slider.set(angle)

        # Send ALL command: servo + emotion + text
        cmd    = f"ALL:{angle}:{emotion}:{ai_response}"
        result = send_command(cmd, conn_mode_var.get())
        log(f"ESP32 response: {result}", "info")

        if conn_mode_var.get() == "WiFi":
            audio_res = send_command(f"AUDIO:{ai_response}", conn_mode_var.get())
            log(f"ESP32 Audio Result: {audio_res}", "info")

    def send_manual():
        text = user_input.get().strip()
        if not text:
            return
        log(f"Manual input: {text}", "user")
        if message_mode_var.get() == "AI":
            threading.Thread(target=process_input, args=(text,), daemon=True).start()
        else:
            threading.Thread(target=process_direct, args=(text,), daemon=True).start()

    user_input.bind("<Return>", lambda e: send_manual())

    listen_btn = ctk.CTkButton(input_row, text="🎤 Listen", width=110, height=40)

    def start_listening():
        if config.is_listening:
            return
        config.is_listening = True
        listen_btn.configure(text="🔴 Listening...", fg_color="#cc0000")

        def _worker():
            try:
                text = listen_once()
                if text:
                    user_input.delete(0, tk.END)
                    user_input.insert(0, text)
                    if message_mode_var.get() == "AI":
                        process_input(text)
                    else:
                        process_direct(text)
            finally:
                config.is_listening = False
                listen_btn.configure(text="🎤 Listen", fg_color="#1f538d")

        threading.Thread(target=_worker, daemon=True).start()

    listen_btn.configure(command=start_listening)
    listen_btn.pack(side="left", padx=(0, 5))

    ctk.CTkButton(input_row, text="▶ Send", width=80, height=40,
                  command=send_manual,
                  fg_color="#1f538d").pack(side="left")

    # =============================================
    #  LOG UPDATER
    # =============================================
    color_map = {
        "info":    "#aaaaaa",
        "success": "#00ff88",
        "error":   "#ff4444",
        "warning": "#ffaa00",
        "user":    "#44aaff",
        "ai":      "#cc88ff",
    }

    def update_log():
        while not config.log_queue.empty():
            entry, level = config.log_queue.get()
            log_box.configure(state="normal")
            color = color_map.get(level, "#aaaaaa")
            log_box.insert(tk.END, entry)
            log_box.tag_add(level, f"end-{len(entry)+1}c", "end-1c")
            log_box.tag_configure(level, foreground=color)
            log_box.see(tk.END)
            log_box.configure(state="disabled")
        root.after(100, update_log)

    # =============================================
    #  STARTUP
    # =============================================
    refresh_ports()
    refresh_bt_mac()
    log("Dashboard started! Configure connection and click Ping to test.", "success")
    log("Steps: 1) Pick WiFi/USB/BT  2) Enter IP/Port  3) Ping!  4) Send message!", "info")
    threading.Thread(target=init_gemini, daemon=True).start()

    root.after(100, update_log)
    return root
