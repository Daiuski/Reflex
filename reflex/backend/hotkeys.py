"""
In-process global hotkey listener.

Runs pynput's keyboard.Listener directly inside the main pywebview process.
Must be started from the main thread (before webview.start()) so pynput
can attach to the process's event stream — a headless subprocess cannot
receive keyboard events because macOS only delivers them to the focused app.

For hotkeys to fire when Reflex is NOT in the foreground, the user must grant
Accessibility permission to Python/Terminal in System Preferences.
"""
import threading
from pynput import keyboard as kb


def _key_to_str(key) -> str:
    """Normalise a pynput key to the canonical string we store."""
    try:
        if hasattr(key, 'name'):          # Key enum  (Key.f8, Key.ctrl …)
            return f'Key.{key.name}'
        c = key.char
        if c is not None:
            return c.lower()
    except (AttributeError, ValueError):
        pass
    return str(key).lower()


class HotkeyManager:
    def __init__(self):
        self._listener = None
        self._binds    = {}      # key_str -> action_name
        self._lock     = threading.Lock()
        self._callback = None

    def start(self, binds: dict, callback):
        """Start the in-process keyboard listener.

        Must be called from the main thread (before webview.start()).
        Raises RuntimeError if pynput fails to initialise.
        """
        self.stop()
        self._callback = callback
        self._set_binds(binds)

        def on_press(key):
            ks = _key_to_str(key)
            with self._lock:
                action = self._binds.get(ks)
            if action and self._callback:
                try:
                    self._callback(action)
                except Exception:
                    pass

        self._listener = kb.Listener(on_press=on_press, suppress=False)
        self._listener.start()
        self._listener.wait()   # blocks until listener is fully up (or raises)

    def update_binds(self, binds: dict):
        """Hot-swap keybinds without restarting the listener."""
        self._set_binds(binds)

    def stop(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _set_binds(self, cfg: dict):
        # Invert: action -> key_str  becomes  key_str -> action
        new = {v: k for k, v in cfg.items() if v}
        with self._lock:
            self._binds = new
