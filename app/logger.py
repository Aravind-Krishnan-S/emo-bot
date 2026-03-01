"""
Logging utilities for the dashboard.
"""
from datetime import datetime
from app import config


def log(message: str, level: str = "info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefixes = {
        "info":    "[INFO]   ",
        "success": "[OK]     ",
        "error":   "[ERROR]  ",
        "warning": "[WARN]   ",
        "user":    "[YOU]    ",
        "ai":      "[GEMINI] ",
    }
    prefix = prefixes.get(level, "[INFO]   ")
    entry  = f"{timestamp} {prefix} {message}\n"
    config.log_queue.put((entry, level))
