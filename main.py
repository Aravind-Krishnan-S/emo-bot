"""
AI Robot Dashboard - Entry Point
Double-click this or run: python main.py
"""
from app.gui import build_app

if __name__ == "__main__":
    root = build_app()
    root.mainloop()
