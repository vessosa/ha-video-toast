import os
import platform
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import config as cfg_module
from ha_client import HAClient
from monitors import get_monitors

# ------------------------------------------------------------------
# Theme — zinc/cyan palette
# ------------------------------------------------------------------
BG       = "#18181b"   # zinc-900
BG2      = "#09090b"   # zinc-950
SURFACE  = "#27272a"   # zinc-800
BORDER   = "#3f3f46"   # zinc-700
FG       = "#f4f4f5"   # zinc-100
FG2      = "#a1a1aa"   # zinc-400
FG3      = "#52525b"   # zinc-600
ACCENT   = "#06b6d4"   # cyan-500
ACCENT2  = "#0891b2"   # cyan-600
SUCCESS  = "#22c55e"
ERROR    = "#ef4444"

AUTOMATION_YAML = """\
action: event.fire
event_type: ha_video_toast
event_data:
  camera: camera.your_camera
  duration: 15   # optional, overrides default\
"""


def _apply_theme(widget_root):
    style = ttk.Style(widget_root)
    style.theme_use("clam")

    style.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10))
    style.configure("TFrame", background=BG)

    style.configure("TNotebook", background=BG, borderwidth=0, tabmargins=[0, 0, 0, 0])
    style.configure("TNotebook.Tab", background=BG2, foreground=FG2,
                    padding=[14, 6], borderwidth=0)
    style.map("TNotebook.Tab",
              background=[("selected", BG)],
              foreground=[("selected", ACCENT)])

    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("Dim.TLabel", background=BG, foreground=FG3)
    style.configure("TCheckbutton", background=BG, foreground=FG2)
    style.map("TCheckbutton", background=[("active", BG)])

    style.configure("TEntry", fieldbackground=BG2, foreground=FG,
                    insertcolor=FG, bordercolor=BORDER, relief="flat")
    style.map("TEntry", fieldbackground=[("focus", SURFACE)])

    style.configure("TSpinbox", fieldbackground=BG2, foreground=FG,
                    insertcolor=FG, bordercolor=BORDER, arrowcolor=FG2, relief="flat")

    style.configure("TCombobox", fieldbackground=BG2, foreground=FG,
                    selectbackground=SURFACE, selectforeground=FG,
                    arrowcolor=FG2, relief="flat")
    style.map("TCombobox", fieldbackground=[("readonly", BG2)])

    style.configure("TButton", background=ACCENT, foreground=BG2,
                    font=("Segoe UI", 9, "bold"), relief="flat", padding=[10, 5])
    style.map("TButton",
              background=[("active", ACCENT2), ("pressed", ACCENT2)],
              foreground=[("active", BG2)])

    style.configure("Ghost.TButton", background=SURFACE, foreground=FG2,
                    font=("Segoe UI", 9), relief="flat", padding=[8, 4])
    style.map("Ghost.TButton", background=[("active", BORDER)])

    style.configure("TSeparator", background=BORDER)


class SettingsWindow:
    def __init__(self, root, config, on_save):
        self.root = root
        self.config = config
        self.on_save = on_save
        self._build()

    # ------------------------------------------------------------------
    # Window scaffold
    # ------------------------------------------------------------------

    def _build(self):
        self.win = tk.Toplevel(self.root)
        self.win.title("HA Video Toast — Settings")
        self.win.geometry("520x480")
        self.win.resizable(False, False)
        self.win.grab_set()
        self.win.configure(bg=BG)

        _apply_theme(self.win)

        nb = ttk.Notebook(self.win)
        nb.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        self._build_connection_tab(nb)
        self._build_appearance_tab(nb)
        self._build_system_tab(nb)
        self._build_about_tab(nb)

        sep = tk.Frame(self.win, bg=BORDER, height=1)
        sep.pack(fill=tk.X, padx=14)

        btn_frame = tk.Frame(self.win, bg=BG)
        btn_frame.pack(fill=tk.X, padx=14, pady=12)
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(btn_frame, text="Cancel", style="Ghost.TButton",
                   command=self.win.destroy).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # Connection tab
    # ------------------------------------------------------------------

    def _build_connection_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Connection  ")
        f.columnconfigure(0, weight=1)

        ttk.Label(f, text="Home Assistant URL").grid(
            row=0, column=0, columnspan=3, sticky=tk.W, padx=14, pady=(16, 3))
        self._url_var = tk.StringVar(value=self.config.get("ha_url", ""))
        ttk.Entry(f, textvariable=self._url_var, width=48).grid(
            row=1, column=0, columnspan=3, padx=14, sticky=tk.EW)
        ttk.Label(f, text="e.g.  http://192.168.1.100:8123", style="Dim.TLabel").grid(
            row=2, column=0, columnspan=3, padx=14, sticky=tk.W, pady=(2, 0))

        ttk.Label(f, text="Long-Lived Access Token").grid(
            row=3, column=0, columnspan=3, sticky=tk.W, padx=14, pady=(14, 3))

        token_frame = tk.Frame(f, bg=BG)
        token_frame.grid(row=4, column=0, columnspan=3, padx=14, sticky=tk.EW)
        self._token_var = tk.StringVar(value=self.config.get("token", ""))
        self._token_entry = ttk.Entry(token_frame, textvariable=self._token_var,
                                      width=40, show="•")
        self._token_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self._show_token = False
        self._show_btn = ttk.Button(token_frame, text="Show", style="Ghost.TButton",
                                    width=6, command=self._toggle_token)
        self._show_btn.pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(f, text="Generate in HA → Profile → Security → Long-lived tokens",
                  style="Dim.TLabel").grid(
            row=5, column=0, columnspan=3, padx=14, sticky=tk.W, pady=(2, 0))

        self._conn_status = ttk.Label(f, text="")
        self._conn_status.grid(row=6, column=0, columnspan=3, padx=14,
                               pady=(10, 0), sticky=tk.W)

        ttk.Button(f, text="Test Connection", command=self._test_connection).grid(
            row=7, column=0, padx=14, pady=10, sticky=tk.W)

    def _toggle_token(self):
        self._show_token = not self._show_token
        self._token_entry.config(show="" if self._show_token else "•")
        self._show_btn.config(text="Hide" if self._show_token else "Show")

    def _test_connection(self):
        self._conn_status.config(text="Testing…", foreground=FG3)
        url = self._url_var.get().strip()
        token = self._token_var.get().strip()

        def run():
            ok, err = HAClient.test_connection(url, token)
            self.root.after(0, lambda: self._show_conn_result(ok, err))

        threading.Thread(target=run, daemon=True).start()

    def _show_conn_result(self, ok, err):
        if ok:
            self._conn_status.config(text="✓  Connected successfully", foreground=SUCCESS)
        else:
            self._conn_status.config(text=f"✗  {err}", foreground=ERROR)

    # ------------------------------------------------------------------
    # Appearance tab
    # ------------------------------------------------------------------

    def _build_appearance_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  Appearance  ")

        t = self.config.get("toast", {})
        fields = [
            ("Width (px)",               "width",      200, 1200, t.get("width", 400)),
            ("Height (px)",              "height",     100,  800, t.get("height", 225)),
            ("Duration (s)",             "duration",     3,  120, t.get("duration", 15)),
            ("Gap between toasts (px)",  "gap",          0,  100, t.get("gap", 10)),
            ("Screen margin (px)",       "margin",       0,  200, t.get("margin", 15)),
            ("Max simultaneous toasts",  "max_toasts",   1,    8, t.get("max_toasts", 4)),
        ]

        self._appearance_vars = {}
        for r, (label, key, lo, hi, default) in enumerate(fields):
            ttk.Label(f, text=label).grid(row=r, column=0, sticky=tk.W,
                                          padx=(14, 8), pady=7)
            var = tk.IntVar(value=default)
            self._appearance_vars[key] = var
            ttk.Spinbox(f, from_=lo, to=hi, textvariable=var, width=8).grid(
                row=r, column=1, padx=(0, 14), sticky=tk.W)

        # Corner picker + stack preview (right column, spans all rows)
        right = tk.Frame(f, bg=BG)
        right.grid(row=0, column=2, rowspan=len(fields) + 2, padx=(0, 14),
                   pady=14, sticky=tk.NE)

        ttk.Label(right, text="Corner").pack(anchor=tk.W, pady=(0, 6))
        self._corner_var = tk.StringVar(value=self.config.get("toast", {}).get("corner", "bottom-right"))
        self._corner_picker = _CornerPicker(right, self._corner_var)
        self._corner_picker.pack()

        # Stack preview label (updates when corner changes)
        self._preview_label = ttk.Label(right, text="", style="Dim.TLabel",
                                        font=("Segoe UI", 8))
        self._preview_label.pack(anchor=tk.W, pady=(8, 0))
        self._corner_var.trace_add("write", lambda *_: self._update_preview())
        self._update_preview()

    def _update_preview(self):
        corner = self._corner_var.get()
        v, h = corner.split("-")
        arrow = {"top-left": "→", "top-right": "←",
                 "bottom-left": "→", "bottom-right": "←"}[corner]
        self._preview_label.config(
            text=f"Stack grows {arrow}  from {v}-{h}")

    # ------------------------------------------------------------------
    # System tab
    # ------------------------------------------------------------------

    def _build_system_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  System  ")

        t = self.config.get("toast", {})
        row = 0

        # Monitor selector
        ttk.Label(f, text="Display toasts on").grid(
            row=row, column=0, sticky=tk.W, padx=(14, 8), pady=(16, 4))
        self._monitor_var = tk.StringVar()
        self._monitors = get_monitors()
        monitor_labels = [m.label(i) for i, m in enumerate(self._monitors)]
        if not monitor_labels:
            monitor_labels = ["Primary monitor"]
        self._monitor_combo = ttk.Combobox(f, textvariable=self._monitor_var,
                                           values=monitor_labels, state="readonly", width=40)
        saved_idx = t.get("monitor_index", 0)
        self._monitor_combo.current(min(saved_idx, max(0, len(monitor_labels) - 1)))
        self._monitor_combo.grid(row=row, column=1, columnspan=2, padx=(0, 14),
                                 pady=(16, 4), sticky=tk.W)
        row += 1

        # Taskbar height
        ttk.Label(f, text="Taskbar height (px)").grid(
            row=row, column=0, sticky=tk.W, padx=(14, 8), pady=6)
        self._taskbar_var = tk.IntVar(value=t.get("taskbar_height", 48))
        ttk.Spinbox(f, from_=0, to=300, textvariable=self._taskbar_var, width=8).grid(
            row=row, column=1, sticky=tk.W, pady=6)
        ttk.Label(f, text="auto-detected on save", style="Dim.TLabel").grid(
            row=row, column=2, padx=8, sticky=tk.W)
        row += 1

        # DND
        self._dnd_var = tk.BooleanVar(value=t.get("respect_dnd", True))
        ttk.Checkbutton(f, text="Suppress toasts when OS Do Not Disturb is active",
                        variable=self._dnd_var).grid(
            row=row, column=0, columnspan=3, padx=14, pady=8, sticky=tk.W)
        row += 1

        # Start with Windows
        self._startup_var = tk.BooleanVar(value=t.get("start_with_windows", False))
        startup_cb = ttk.Checkbutton(f, text="Start with Windows",
                                     variable=self._startup_var,
                                     command=self._apply_startup)
        startup_cb.grid(row=row, column=0, columnspan=3, padx=14, pady=2, sticky=tk.W)
        if platform.system() != "Windows":
            startup_cb.state(["disabled"])
        ttk.Label(
            f,
            text="Adds a Windows startup entry using this Python interpreter.",
            style="Dim.TLabel",
        ).grid(row=row + 1, column=0, columnspan=3, padx=(28, 14), sticky=tk.W)
        row += 2

        # Separator
        tk.Frame(f, bg=BORDER, height=1).grid(
            row=row, column=0, columnspan=3, sticky=tk.EW, padx=14, pady=12)
        row += 1

        # Automation YAML with copy button
        ttk.Label(f, text="HA Automation action (paste into any automation):").grid(
            row=row, column=0, columnspan=3, padx=14, sticky=tk.W, pady=(0, 6))
        row += 1

        code_frame = tk.Frame(f, bg=BG2, bd=0, highlightthickness=1,
                              highlightbackground=BORDER)
        code_frame.grid(row=row, column=0, columnspan=3, padx=14, sticky=tk.EW)

        code_text = tk.Text(code_frame, bg=BG2, fg=ACCENT, font=("Courier New", 9),
                            relief="flat", bd=6, height=6, width=52,
                            state="disabled", cursor="arrow",
                            selectbackground=SURFACE, selectforeground=FG)
        code_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        code_text.config(state="normal")
        code_text.insert("1.0", AUTOMATION_YAML)
        code_text.config(state="disabled")

        self._copy_btn = ttk.Button(code_frame, text="Copy", style="Ghost.TButton",
                                    command=lambda: self._copy_yaml(code_text))
        self._copy_btn.pack(side=tk.RIGHT, anchor=tk.NE, padx=6, pady=6)

    def _copy_yaml(self, code_text):
        self.root.clipboard_clear()
        self.root.clipboard_append(AUTOMATION_YAML)
        self._copy_btn.config(text="Copied!")
        self.root.after(1800, lambda: self._copy_btn.config(text="Copy"))

    # ------------------------------------------------------------------
    # Start with Windows
    # ------------------------------------------------------------------

    def _apply_startup(self):
        if platform.system() != "Windows":
            return
        enabled = self._startup_var.get()
        startup_dir = os.path.join(
            os.environ.get("APPDATA", ""),
            "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
        )
        bat_path = os.path.join(startup_dir, "ha-video-toast.bat")
        vbs_path = os.path.join(startup_dir, "ha-video-toast.vbs")
        try:
            if enabled:
                self._set_windows_run_entry(self._startup_command())
                self._remove_startup_file(bat_path)
                self._remove_startup_file(vbs_path)
            else:
                self._remove_windows_run_entry()
                self._remove_startup_file(bat_path)
                self._remove_startup_file(vbs_path)
        except Exception as e:
            messagebox.showerror("Startup", f"Could not update startup entry:\n{e}",
                                 parent=self.win)

    def _startup_command(self):
        if getattr(sys, "frozen", False):
            return f'"{os.path.abspath(sys.executable)}"'

        python_exe = self._windows_gui_python_exe()
        script = os.path.abspath(sys.argv[0])
        return f'"{python_exe}" "{script}"'

    def _windows_gui_python_exe(self):
        python_exe = sys.executable
        if getattr(sys, "frozen", False):
            return python_exe

        exe_dir = os.path.dirname(python_exe)
        pythonw_exe = os.path.join(exe_dir, "pythonw.exe")
        if os.path.exists(pythonw_exe):
            return pythonw_exe
        return python_exe

    @staticmethod
    def _set_windows_run_entry(command):
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "HA Video Toast", 0, winreg.REG_SZ, command)

    @staticmethod
    def _remove_windows_run_entry():
        import winreg
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.DeleteValue(key, "HA Video Toast")
        except FileNotFoundError:
            pass

    @staticmethod
    def _remove_startup_file(path):
        if os.path.exists(path):
            os.remove(path)

    # ------------------------------------------------------------------
    # About tab
    # ------------------------------------------------------------------

    def _build_about_tab(self, nb):
        f = ttk.Frame(nb)
        nb.add(f, text="  About  ")

        # App icon (large)
        try:
            from logo import make_app_icon
            from PIL import ImageTk
            icon_img = make_app_icon(size=56)
            self._about_icon = ImageTk.PhotoImage(icon_img)
            tk.Label(f, image=self._about_icon, bg=BG).pack(pady=(24, 8))
        except Exception:
            tk.Label(f, text="📷", bg=BG, fg=ACCENT,
                     font=("Segoe UI", 32)).pack(pady=(24, 8))

        # App name
        tk.Label(f, text="HA Video Toast", bg=BG, fg=FG,
                 font=("Segoe UI", 16, "bold")).pack()

        # Description
        tk.Label(
            f,
            text=(
                "Desktop toast notifications with live camera feeds\n"
                "triggered by Home Assistant automations.\n"
                "No RTSP configuration required."
            ),
            bg=BG, fg=FG2, font=("Segoe UI", 9),
            justify=tk.CENTER,
        ).pack(pady=(8, 0))

        # Divider
        tk.Frame(f, bg=BORDER, height=1).pack(fill=tk.X, padx=40, pady=16)

        # Author + links grid
        info = tk.Frame(f, bg=BG)
        info.pack()

        def row(label, value, url=None, mailto=None):
            r = info.grid_size()[1]
            tk.Label(info, text=label, bg=BG, fg=FG3,
                     font=("Segoe UI", 9), anchor=tk.E, width=10).grid(
                row=r, column=0, sticky=tk.E, padx=(0, 8), pady=3)
            if url or mailto:
                target = url or f"mailto:{mailto}"
                lnk = tk.Label(info, text=value, bg=BG, fg=ACCENT,
                               font=("Segoe UI", 9, "underline"), cursor="hand2")
                lnk.grid(row=r, column=1, sticky=tk.W, pady=3)
                lnk.bind("<Button-1>", lambda _: _open_url(target))
                lnk.bind("<Enter>", lambda _: lnk.config(fg=FG))
                lnk.bind("<Leave>", lambda _: lnk.config(fg=ACCENT))
            else:
                tk.Label(info, text=value, bg=BG, fg=FG,
                         font=("Segoe UI", 9)).grid(row=r, column=1, sticky=tk.W, pady=3)

        row("Author",  "Luiz Vessosa")
        row("GitHub",  "github.com/vessosa/ha-video-toast",
            url="https://github.com/vessosa/ha-video-toast")
        row("License", "MIT")
        row("Donate",  "paypal.me/vessosa ♥", url="https://paypal.me/vessosa")

    # ------------------------------------------------------------------
    # Auto-detect taskbar height (Windows)
    # ------------------------------------------------------------------

    def _detect_taskbar_height(self):
        if platform.system() != "Windows":
            return
        try:
            import ctypes
            import ctypes.wintypes
            work_area = ctypes.wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(work_area), 0)
            screen_h = ctypes.windll.user32.GetSystemMetrics(1)
            taskbar_h = screen_h - work_area.bottom
            if taskbar_h > 0:
                self._taskbar_var.set(taskbar_h)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save(self):
        self.config["ha_url"] = self._url_var.get().strip()
        self.config["token"] = self._token_var.get().strip()

        t = self.config.setdefault("toast", {})
        for key, var in self._appearance_vars.items():
            t[key] = var.get()

        t["taskbar_height"] = self._taskbar_var.get()
        t["respect_dnd"] = self._dnd_var.get()
        t["start_with_windows"] = self._startup_var.get()
        t["monitor_index"] = self._monitor_combo.current()
        t["corner"] = self._corner_var.get()

        self._apply_startup()
        self._detect_taskbar_height()

        cfg_module.save(self.config)
        if self.on_save:
            self.on_save(self.config)
        self.win.destroy()


# ------------------------------------------------------------------
# Corner picker widget
# ------------------------------------------------------------------

_CORNERS = ["top-left", "top-right", "bottom-left", "bottom-right"]

# Canvas coords for each corner box inside the 110×80 monitor outline
_CORNER_BOXES = {
    "top-left":     (8,   8,  36,  26),
    "top-right":    (74,  8, 102,  26),
    "bottom-left":  (8,  54,  36,  72),
    "bottom-right": (74, 54, 102,  72),
}

_CORNER_LABEL = {
    "top-left": "TL", "top-right": "TR",
    "bottom-left": "BL", "bottom-right": "BR",
}


class _CornerPicker(tk.Canvas):
    """2×2 visual corner selector drawn on a mini monitor outline."""

    W, H = 110, 80

    def __init__(self, parent, var: tk.StringVar):
        super().__init__(parent, width=self.W, height=self.H,
                         bg=BG, highlightthickness=0)
        self._var = var
        self._rect_ids: dict[str, int] = {}
        self._text_ids: dict[str, int] = {}
        self._draw()
        self.bind("<Button-1>", self._on_click)
        self.bind("<Motion>",   self._on_motion)
        self.bind("<Leave>",    lambda _: self.config(cursor=""))
        var.trace_add("write", lambda *_: self._refresh())

    def _draw(self):
        # Monitor bezel
        self.create_rectangle(2, 2, self.W - 2, self.H - 2,
                              outline=BORDER, fill=BG2, width=1)
        # Stand
        mx = self.W // 2
        self.create_rectangle(mx - 10, self.H - 2, mx + 10, self.H,
                              fill=BORDER, outline="")

        for corner, (x1, y1, x2, y2) in _CORNER_BOXES.items():
            color = ACCENT if corner == self._var.get() else SURFACE
            rid = self.create_rectangle(x1, y1, x2, y2,
                                        fill=color, outline="", tags=corner)
            tid = self.create_text((x1 + x2) // 2, (y1 + y2) // 2,
                                   text=_CORNER_LABEL[corner],
                                   fill=BG2 if color == ACCENT else FG3,
                                   font=("Segoe UI", 7, "bold"), tags=corner)
            self._rect_ids[corner] = rid
            self._text_ids[corner] = tid

    def _refresh(self):
        selected = self._var.get()
        for corner in _CORNERS:
            active = corner == selected
            self.itemconfig(self._rect_ids[corner],
                            fill=ACCENT if active else SURFACE)
            self.itemconfig(self._text_ids[corner],
                            fill=BG2 if active else FG3)

    def _hit(self, x, y) -> str | None:
        for corner, (x1, y1, x2, y2) in _CORNER_BOXES.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return corner
        return None

    def _on_click(self, event):
        corner = self._hit(event.x, event.y)
        if corner:
            self._var.set(corner)

    def _on_motion(self, event):
        self.config(cursor="hand2" if self._hit(event.x, event.y) else "")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _open_url(url: str):
    import webbrowser
    webbrowser.open(url)

