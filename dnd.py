import platform


def is_dnd_active():
    if platform.system() == "Windows":
        return _windows_dnd()
    return False


def _windows_dnd():
    try:
        import ctypes
        # QUNS_ACCEPTS_NOTIFICATIONS = 5; anything else = busy/DND/fullscreen
        state = ctypes.c_int()
        ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state))
        return state.value != 5
    except Exception:
        return False
