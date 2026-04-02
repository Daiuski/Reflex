import json
import os
import base64
import io
import pathlib
import subprocess
import threading
import webview
import mss
from PIL import Image

from backend.recorder import MacroRecorder
from backend.player   import MacroPlayer
from backend.monitor  import ColorMonitor
from backend.hotkeys  import HotkeyManager

_DEFAULT_KEYBINDS = {'play_stop': '', 'record': '', 'monitoring': ''}


_AUTOSAVE_DIR  = pathlib.Path.home() / 'Documents' / 'ReflexMacros'
_AUTOSAVE_FILE = _AUTOSAVE_DIR / 'autosave.json'

_DEFAULT_SETTINGS = {
    'always_on_top':        False,
    'countdown_enabled':    True,
    'sounds_enabled':       True,
    'trigger_sound_enabled':True,
}


def _strip_trailing_hotkey(events, key_str):
    """Remove key_press/key_release events for key_str from the tail of events."""
    if not key_str or not events:
        return events
    target = key_str.lower()
    result = list(events)
    while result:
        ev = result[-1]
        if ev['type'] in ('key_press', 'key_release') and ev.get('key', '').lower() == target:
            result.pop()
        else:
            break
    return result


def _notify(title, message):
   
    try:
        from Foundation import NSUserNotification, NSUserNotificationCenter
        n = NSUserNotification.alloc().init()
        n.setTitle_(title)
        n.setInformativeText_(message)
        NSUserNotificationCenter.defaultUserNotificationCenter().deliverNotification_(n)
    except Exception:
         try:
            msg   = message.replace('"', '\\"')
            title = title.replace('"', '\\"')
            subprocess.Popen(
                ['osascript', '-e',
                 f'display notification "{msg}" with title "{title}"'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


class ReflexAPI:
    def __init__(self):
        self.window     = None
        self.recorder   = MacroRecorder()
        self.player     = MacroPlayer()
        self.monitor    = ColorMonitor()
        self.hotkeys    = HotkeyManager()
        self.macros     = []
        self.triggers   = []
        self._recording        = False
        self._monitoring       = False
        self._naming           = False
        self._countdown_cancel = None


        _AUTOSAVE_DIR.mkdir(parents=True, exist_ok=True)
        self._autoload()

   
        _cfg_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
        self._keybinds_file = os.path.join(_cfg_dir, 'keybinds.json')
        self._settings_file = os.path.join(_cfg_dir, 'settings.json')
        self._keybinds = dict(_DEFAULT_KEYBINDS)
        self._load_keybinds()
        self._settings = dict(_DEFAULT_SETTINGS)
        self._load_settings()

    def set_window(self, window):
        self.window = window
        self._start_hotkeys()
        threading.Thread(target=self._check_accessibility, daemon=True).start()
      
        if self._settings.get('always_on_top'):
            try:
                window.on_top = True
            except Exception:
                pass

    # ── Notifications & permissions ───────────────────────────────────────────

    def _check_accessibility(self):
        """Prompt for Accessibility permission if not already granted."""
        try:
            from ctypes import cdll
            lib     = cdll.LoadLibrary(
                '/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
            trusted = bool(lib.AXIsProcessTrusted())
            if not trusted:
                script = (
                    'set res to button returned of (display dialog '
                    '"Reflex needs Accessibility access to record and replay '
                    'keyboard & mouse input.\\n\\nGo to System Settings → '
                    'Privacy & Security → Accessibility and add this app." '
                    'buttons {"Open Settings", "Later"} '
                    'default button "Open Settings" with icon caution)\\n'
                    'if res is "Open Settings" then\\n'
                    '  do shell script "open \\"x-apple.systempreferences:'
                    'com.apple.preference.security?Privacy_Accessibility\\""\\n'
                    'end if'
                )
                subprocess.run(['osascript', '-e', script],
                               check=False, timeout=60)
        except Exception:
            pass

    # ── Auto-save ─────────────────────────────────────────────────────────────

    def _autosave(self):
        try:
            with open(_AUTOSAVE_FILE, 'w') as f:
                json.dump({'macros': self.macros, 'triggers': self.triggers},
                          f, indent=2)
        except Exception:
            pass

    def _autoload(self):
        try:
            if _AUTOSAVE_FILE.exists():
                with open(_AUTOSAVE_FILE) as f:
                    data = json.load(f)
                self.macros   = data.get('macros',   [])
                self.triggers = data.get('triggers', [])
                # Re-register triggers with the monitor
                for t in self.triggers:
                    self.monitor.add_trigger(t)
        except Exception:
            pass

    # ── Recording ──────────────────────────────────────────────────────────────

    def start_recording(self):
        if self._recording:
            return {'ok': False, 'error': 'Already recording'}
        try:
            self.recorder.start()
        except Exception as e:
            return {'ok': False, 'error': str(e)}
        self._recording = True
        _notify('Reflex', 'Recording started')
        return {'ok': True}

    def stop_recording(self):
        if not self._recording:
            return {'ok': False, 'error': 'Not recording'}
        self._recording = False

        # Detect subprocess crash
        if self.recorder._proc and self.recorder._proc.poll() is not None:
            _notify('Reflex — Recorder Error',
                    'Subprocess crashed — please re-launch the program.')
            return {'ok': False,
                    'error': 'Recorder subprocess crashed — please re-launch.'}

        result = self.recorder.stop()
        events = _strip_trailing_hotkey(result['events'], self._keybinds.get('record', ''))
        events = _strip_trailing_hotkey(events,           self._keybinds.get('play_stop', ''))
        _notify('Reflex', f'Recording stopped — {len(events)} events captured')
        return {'ok': True, 'events': events,
                'duration': result['duration'], 'event_count': len(events)}

    def set_naming(self, flag):
        self._naming = bool(flag)
        return {'ok': True}

    def save_macro(self, name, events, duration, loop=False):
        macro = {'name': name, 'events': events,
                 'duration': duration, 'event_count': len(events),
                 'loop': bool(loop)}
        self.macros.append(macro)
        self._autosave()
        return {'ok': True, 'macros': self._macros_summary()}

    def set_macro_loop(self, name, loop):
        for m in self.macros:
            if m['name'] == name:
                m['loop'] = bool(loop)
                break
        self._autosave()
        return {'ok': True}

    def restore_macro(self, macro, index):
        """Re-insert a previously deleted macro at its original index (for undo)."""
        idx = min(int(index), len(self.macros))
        self.macros.insert(idx, macro)
        self._autosave()
        return {'ok': True, 'macros': self._macros_summary()}

    def restore_trigger(self, trigger, index):
        """Re-insert a previously deleted trigger at its original index (for undo)."""
        idx = min(int(index), len(self.triggers))
        self.triggers.insert(idx, trigger)
        self.monitor.clear_triggers()
        for t in self.triggers:
            self.monitor.add_trigger(t)
        self._autosave()
        return {'ok': True, 'triggers': self.triggers}

    def rename_macro(self, old_name, new_name):
        new_name = new_name.strip()
        if not new_name:
            return {'ok': False, 'error': 'Name cannot be empty'}
        if any(m['name'] == new_name for m in self.macros):
            return {'ok': False, 'error': f'Name "{new_name}" already exists'}
        for m in self.macros:
            if m['name'] == old_name:
                m['name'] = new_name
                break
        else:
            return {'ok': False, 'error': f'Macro "{old_name}" not found'}
        # Keep trigger references in sync
        for t in self.triggers:
            if t.get('macro_name') == old_name:
                t['macro_name'] = new_name
        self._autosave()
        return {'ok': True, 'macros': self._macros_summary()}

    def delete_macro(self, name):
        self.macros = [m for m in self.macros if m['name'] != name]
        # Remove orphaned triggers
        removed = [t for t in self.triggers if t.get('macro_name') == name]
        self.triggers = [t for t in self.triggers if t.get('macro_name') != name]
        if removed:
            self.monitor.clear_triggers()
            for t in self.triggers:
                self.monitor.add_trigger(t)
        self._autosave()
        return {'ok': True, 'macros': self._macros_summary(), 'triggers': self.triggers}

    def get_macros(self):
        return {'ok': True, 'macros': self._macros_summary()}

    def _macros_summary(self):
        return [{'name': m['name'], 'duration': m['duration'],
                 'event_count': m['event_count'], 'loop': m.get('loop', False)}
                for m in self.macros]

    # ── Playback ───────────────────────────────────────────────────────────────

    def play_macro(self, name, repeat=1):
        macro = next((m for m in self.macros if m['name'] == name), None)
        if not macro:
            return {'ok': False, 'error': f'Macro "{name}" not found'}
        if self.player.playing or self._countdown_cancel:
            return {'ok': False, 'error': 'Already playing'}

        loop = (int(repeat) == 0)

        def on_complete():
            if self.window:
                self.window.evaluate_js(
                    'window.onPlaybackComplete && window.onPlaybackComplete()')

        if self._settings.get('countdown_enabled', True):
            cancelled = threading.Event()
            self._countdown_cancel = cancelled

            def _countdown_then_play():
                import time
                for i in (3, 2, 1):
                    if cancelled.is_set():
                        return
                    if self.window:
                        self.window.evaluate_js(
                            f'window.onPlaybackCountdown && window.onPlaybackCountdown({i})')
                    time.sleep(1)
                if cancelled.is_set():
                    return
                # Clear the cancel handle before starting playback so future plays aren't blocked
                self._countdown_cancel = None
                if self.window:
                    self.window.evaluate_js(
                        'window.onPlaybackCountdown && window.onPlaybackCountdown(0)')
                self.player.play(macro, repeat=int(repeat), loop=loop, on_complete=on_complete)
            threading.Thread(target=_countdown_then_play, daemon=True).start()
        else:
            self._countdown_cancel = None
            self.player.play(macro, repeat=int(repeat), loop=loop, on_complete=on_complete)
        return {'ok': True}

    def stop_playback(self):
        # Cancel any in-progress countdown so it doesn't start playback after being stopped
        if self._countdown_cancel:
            self._countdown_cancel.set()
            self._countdown_cancel = None
        self.player.stop()
        return {'ok': True}

    # ── File I/O ───────────────────────────────────────────────────────────────

    def save_to_file(self, selected_name=''):
        save_filename = f'{selected_name}.json' if selected_name else 'macros.json'
        result = self.window.create_file_dialog(
            webview.FileDialog.SAVE,
            directory=os.path.expanduser('~'),
            save_filename=save_filename,
            file_types=('JSON Files (*.json)', 'All Files (*.*)')
        )
        if not result:
            return {'ok': False, 'error': 'Cancelled'}
        path = result if isinstance(result, str) else result[0]

        if selected_name:
            macro = next((m for m in self.macros if m['name'] == selected_name), None)
            if not macro:
                return {'ok': False, 'error': f'Macro "{selected_name}" not found'}
            payload = {'macros': [macro], 'triggers': []}
        else:
            payload = {'macros': self.macros, 'triggers': self.triggers}

        with open(path, 'w') as f:
            json.dump(payload, f, indent=2)
        return {'ok': True, 'path': path}

    def load_from_file(self):
        result = self.window.create_file_dialog(
            webview.FileDialog.OPEN,
            directory=os.path.expanduser('~'),
            file_types=('JSON Files (*.json)', 'All Files (*.*)')
        )
        if not result:
            return {'ok': False, 'error': 'Cancelled'}
        path = result[0] if isinstance(result, (list, tuple)) else result
        with open(path) as f:
            data = json.load(f)

        existing_names = {m['name'] for m in self.macros}
        imported_macros = []
        for m in data.get('macros', []):
            if m['name'] not in existing_names:
                self.macros.append(m)
                imported_macros.append(m['name'])
                existing_names.add(m['name'])

        imported_triggers = []
        for t in data.get('triggers', []):
            self.triggers.append(t)
            self.monitor.add_trigger(t)
            imported_triggers.append(t)

        skipped = len(data.get('macros', [])) - len(imported_macros)
        self._autosave()
        return {
            'ok': True,
            'macros':   self._macros_summary(),
            'triggers': self.triggers,
            'imported_macros':   len(imported_macros),
            'imported_triggers': len(imported_triggers),
            'skipped_macros':    max(0, skipped),
        }

    def save_triggers_to_file(self):
        result = self.window.create_file_dialog(
            webview.FileDialog.SAVE,
            directory=os.path.expanduser('~'),
            save_filename='triggers.json',
            file_types=('JSON Files (*.json)', 'All Files (*.*)')
        )
        if not result:
            return {'ok': False, 'error': 'Cancelled'}
        path = result if isinstance(result, str) else result[0]
        with open(path, 'w') as f:
            json.dump({'triggers': self.triggers}, f, indent=2)
        return {'ok': True, 'path': path}

    def load_triggers_from_file(self):
        result = self.window.create_file_dialog(
            webview.FileDialog.OPEN,
            directory=os.path.expanduser('~'),
            file_types=('JSON Files (*.json)', 'All Files (*.*)')
        )
        if not result:
            return {'ok': False, 'error': 'Cancelled'}
        path = result[0] if isinstance(result, (list, tuple)) else result
        with open(path) as f:
            data = json.load(f)
        new_triggers = data.get('triggers', [])
        for t in new_triggers:
            self.triggers.append(t)
            self.monitor.add_trigger(t)
        self._autosave()
        return {'ok': True, 'triggers': self.triggers, 'imported': len(new_triggers)}

    # ── Color Triggers ─────────────────────────────────────────────────────────

    def capture_screen(self):
        try:
            with mss.mss() as sct:
                monitors    = sct.monitors
                monitor_idx = 1 if len(monitors) > 1 else 0
                screenshot  = sct.grab(monitors[monitor_idx])
                img = Image.frombytes('RGB', screenshot.size,
                                      screenshot.bgra, 'raw', 'BGRX')
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                b64 = base64.b64encode(buf.getvalue()).decode()
                return {'ok': True, 'image': b64,
                        'width': screenshot.width, 'height': screenshot.height}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def add_trigger(self, macro_name, region, color, tolerance, loop=False):
        trigger = {'macro_name': macro_name, 'region': region,
                   'color': color, 'tolerance': tolerance,
                   'loop': bool(loop)}
        self.triggers.append(trigger)
        self.monitor.add_trigger(trigger)
        self._autosave()
        return {'ok': True, 'triggers': self.triggers}

    def remove_trigger(self, index):
        idx = int(index)
        if 0 <= idx < len(self.triggers):
            self.triggers.pop(idx)
            self.monitor.remove_trigger(idx)
        self._autosave()
        return {'ok': True, 'triggers': self.triggers}

    def update_trigger(self, index, color, loop):
        idx = int(index)
        if 0 <= idx < len(self.triggers):
            self.triggers[idx]['color'] = color
            self.triggers[idx]['loop']  = bool(loop)
            # Rebuild monitor so _mid and loop flag are fresh
            self.monitor.clear_triggers()
            for t in self.triggers:
                self.monitor.add_trigger(t)
        self._autosave()
        return {'ok': True, 'triggers': self.triggers}

    def get_triggers(self):
        return {'ok': True, 'triggers': self.triggers}

    # ── Monitoring ─────────────────────────────────────────────────────────────

    def start_monitoring(self):
        if self._monitoring:
            return {'ok': True}
        self._monitoring = True

        def on_trigger(macro_name):
            macro = next((m for m in self.macros if m['name'] == macro_name), None)
            if macro and not self.player.playing:
                self.player.play(macro, repeat=1)
            if self.window:
                safe = macro_name.replace("'", "\\'")
                self.window.evaluate_js(
                    f"window.onColorTrigger && window.onColorTrigger('{safe}')")

        def on_exhausted():
            """All fire-once triggers fired — stop monitoring automatically."""
            self._monitoring = False
            if self.window:
                self.window.evaluate_js(
                    'window.onMonitorExhausted && window.onMonitorExhausted()')

        self.monitor.start(on_trigger, on_exhausted=on_exhausted)
        return {'ok': True}

    def stop_monitoring(self):
        self._monitoring = False
        self.monitor.stop()
        return {'ok': True}

    def is_monitoring(self):
        return {'ok': True, 'monitoring': self._monitoring}

    # ── Keybinds ───────────────────────────────────────────────────────────────

    def get_keybinds(self):
        return {'ok': True, 'keybinds': self._keybinds}

    def set_keybinds(self, keybinds):
        self._keybinds = keybinds
        self._save_keybinds()
        self.hotkeys.update_binds(keybinds)
        return {'ok': True}

    def _load_keybinds(self):
        try:
            with open(self._keybinds_file) as f:
                saved = json.load(f)
            self._keybinds = {**_DEFAULT_KEYBINDS, **saved}
        except Exception:
            pass

    def _save_keybinds(self):
        try:
            with open(self._keybinds_file, 'w') as f:
                json.dump(self._keybinds, f, indent=2)
        except Exception:
            pass

    # ── Settings ───────────────────────────────────────────────────────────────

    def get_settings(self):
        return {'ok': True, 'settings': self._settings}

    def set_settings(self, settings):
        prev_top = self._settings.get('always_on_top', False)
        self._settings = {**_DEFAULT_SETTINGS, **settings}
        self._save_settings()
        # Apply always-on-top live
        if self.window:
            try:
                self.window.on_top = bool(self._settings.get('always_on_top', False))
            except Exception:
                pass
        return {'ok': True, 'settings': self._settings}

    def clear_all_data(self):
        """Wipe all macros, triggers, keybinds and settings back to defaults."""
        self.macros   = []
        self.triggers = []
        self.monitor.clear_triggers()
        self._keybinds  = dict(_DEFAULT_KEYBINDS)
        self._settings  = dict(_DEFAULT_SETTINGS)
        self._save_keybinds()
        self._save_settings()
        self.hotkeys.update_binds(self._keybinds)
        # Wipe autosave
        try:
            _AUTOSAVE_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        if self.window:
            try:
                self.window.on_top = False
            except Exception:
                pass
        return {'ok': True}

    def _load_settings(self):
        try:
            with open(self._settings_file) as f:
                saved = json.load(f)
            self._settings = {**_DEFAULT_SETTINGS, **saved}
        except Exception:
            pass

    def _save_settings(self):
        try:
            with open(self._settings_file, 'w') as f:
                json.dump(self._settings, f, indent=2)
        except Exception:
            pass

    def _start_hotkeys(self):
        def on_hotkey(action):
            if self._naming:
                return
            if action == 'play_stop':
                if self._recording:
                    return
                if self.window:
                    self.window.evaluate_js(
                        'window.hotkeyPlayStop && window.hotkeyPlayStop()')

            elif action == 'monitoring':
                if self.window:
                    self.window.evaluate_js(
                        'window.hotkeyMonitoring && window.hotkeyMonitoring()')

            elif action == 'record':
                if self._recording:
                    self._recording = False
                    # Detect crash first
                    if self.recorder._proc and self.recorder._proc.poll() is not None:
                        _notify('Reflex — Recorder Error',
                                'Subprocess crashed — please re-launch the program.')
                        if self.window:
                            self.window.evaluate_js(
                                'window.hotkeyRecordCrashed && window.hotkeyRecordCrashed()')
                        return
                    try:
                        result = self.recorder.stop()
                    except Exception:
                        result = {'events': [], 'duration': 0, 'event_count': 0}
                    events = _strip_trailing_hotkey(
                        result['events'], self._keybinds.get('record', ''))
                    events = _strip_trailing_hotkey(
                        events, self._keybinds.get('play_stop', ''))
                    result = {**result, 'events': events, 'event_count': len(events)}
                    _notify('Reflex', f'Recording stopped — {len(events)} events captured')
                    if self.window:
                        data = json.dumps(result)
                        self.window.evaluate_js(
                            f'window.hotkeyStopRecord && window.hotkeyStopRecord({data})')
                else:
                    try:
                        self.recorder.start()
                        self._recording = True
                        _notify('Reflex', 'Recording started')
                        if self.window:
                            self.window.evaluate_js(
                                'window.hotkeyStartRecord && window.hotkeyStartRecord()')
                    except Exception:
                        pass

        try:
            self.hotkeys.start(self._keybinds, on_hotkey)
        except Exception:
            pass
