"""
Shared configuration and global state for the AI Robot Dashboard.
"""
import os
import sys
import queue
from dotenv import load_dotenv

# Find .env relative to the exe or script location
if getattr(sys, 'frozen', False):
    # Running as PyInstaller exe
    _base_dir = os.path.dirname(sys.executable)
else:
    # Running as Python script
    _base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(_base_dir, ".env"))

# =============================================
#  API KEY — loaded from .env file
# =============================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# =============================================
#  SHARED STATE
# =============================================
esp32_ip      = ""
serial_conn   = None
bt_conn       = None
gemini_model  = None
is_listening  = False
log_queue     = queue.Queue()
cached_bt_mac = ""

CONNECTION_MODES = ["WiFi", "USB Serial", "Bluetooth"]
