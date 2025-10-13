#!/usr/bin/env python3
# run_stickynotes.py

import sys
from PyQt6.QtWidgets import QApplication
from stickynotes.tray_manager import TrayManager

def main():
    """Main function to initialize and run the application."""
    app = QApplication(sys.argv)

    _ = TrayManager(app) 
    sys.exit(app.exec())

if __name__ == "__main__":
    main()