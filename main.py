"""
HA Video Toast
Copyright (c) 2026 Luiz Vessosa
MIT License — see LICENSE

Desktop notification app that displays always-on-top toast popups with a live
MJPEG camera feed, triggered by a Home Assistant automation event.

Architecture:
  main.py           — entry point, wires all components
  ha_client.py      — HA WebSocket connection, subscribes to ha_video_toast events
  toast_manager.py  — slot layout, slide animation, DND gate
  toast_window.py   — individual toast: MJPEG stream + countdown + fade in/out
  settings_window.py — tabbed GUI settings (Connection / Appearance / System / About)
  tray.py           — system tray icon with 4-state indicator
  monitors.py       — cross-platform monitor enumeration
  dnd.py            — OS Do Not Disturb detection (Windows ctypes)
  logo.py           — app icon and badge drawn with Pillow
  config.py         — load/save JSON config (~/.ha-video-toast/config.json)

Run:
  python main.py

Build (PyInstaller):
  pip install pyinstaller
  pyinstaller --onefile --windowed --name ha-video-toast main.py
"""

import platform
import sys
import tkinter as tk

import config as cfg_module
from ha_client import HAClient
from settings_window import SettingsWindow
from toast_manager import ToastManager
from tray import TrayIcon


def _set_dpi_awareness():
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def main():
    _set_dpi_awareness()  # must be before Tk()
    config = cfg_module.load()

    # Hidden root window — never shown, owns all Toplevels
    root = tk.Tk()
    root.withdraw()
    root.title("HA Video Toast")
    root.protocol("WM_DELETE_WINDOW", lambda: None)

    ha_client: HAClient | None = None
    toast_manager: ToastManager | None = None

    # ------------------------------------------------------------------
    # HA client lifecycle
    # ------------------------------------------------------------------

    def on_toast_event(event_data):
        if toast_manager:
            toast_manager.handle_event(event_data)

    def start_client():
        nonlocal ha_client, toast_manager
        if ha_client:
            ha_client.stop()
        ha_client = HAClient(config, on_toast_event)
        ha_client.on_status_change = lambda c: root.after(0, lambda: tray.set_connected(c))
        ha_client.start()
        toast_manager = ToastManager(root, ha_client, config)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def on_save(new_config):
        config.update(new_config)
        tray.set_configured(cfg_module.is_configured(config))
        if cfg_module.is_configured(config):
            start_client()

    def open_settings():
        SettingsWindow(root, config, on_save)

    # ------------------------------------------------------------------
    # Quit
    # ------------------------------------------------------------------

    def quit_app():
        if ha_client:
            ha_client.stop()
        root.quit()

    # ------------------------------------------------------------------
    # Tray icon
    # ------------------------------------------------------------------

    tray = TrayIcon(
        on_settings=lambda: root.after(0, open_settings),
        on_quit=lambda: root.after(0, quit_app),
    )
    tray.start(configured=cfg_module.is_configured(config))

    # ------------------------------------------------------------------
    # First-run: open settings if not configured, else connect
    # ------------------------------------------------------------------

    if cfg_module.is_configured(config):
        start_client()
    else:
        root.after(300, open_settings)

    root.mainloop()


if __name__ == "__main__":
    main()
