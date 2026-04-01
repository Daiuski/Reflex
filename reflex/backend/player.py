import time
import threading
from pynput import mouse, keyboard
from pynput.keyboard import Key

class MacroPlayer:
    def __init__(self):
        self.playing = False
        self._thread = None
        self._mouse_ctrl = mouse.Controller()
        self._keyboard_ctrl = keyboard.Controller()
        self.on_complete = None

    def play(self, macro, repeat=1, loop=False, on_complete=None):
        if self.playing:
            return
        self.on_complete = on_complete
        self.playing = True
        self._thread = threading.Thread(target=self._run, args=(macro, repeat, loop), daemon=True)
        self._thread.start()

    def stop(self):
        self.playing = False

    def _run(self, macro, repeat, loop):
        events = macro.get('events', [])
        if not events:
            self.playing = False
            if self.on_complete:
                self.on_complete()
            return

        if loop:
            while self.playing:
                self._play_once(events)
        else:
            for _ in range(repeat):
                if not self.playing:
                    break
                self._play_once(events)

        self.playing = False
        if self.on_complete:
            self.on_complete()

    def _play_once(self, events):
        start = time.time()
        for event in events:
            if not self.playing:
                return

            target_time = event['t']
            elapsed = time.time() - start
            sleep_time = target_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

            if not self.playing:
                return

            etype = event['type']
            if etype == 'move':
                self._mouse_ctrl.position = (event['x'], event['y'])
            elif etype == 'click':
                btn = mouse.Button.left if event['button'] == 'left' else mouse.Button.right
                self._mouse_ctrl.position = (event['x'], event['y'])
                if event['pressed']:
                    self._mouse_ctrl.press(btn)
                else:
                    self._mouse_ctrl.release(btn)
            elif etype == 'scroll':
                self._mouse_ctrl.scroll(event['dx'], event['dy'])
            elif etype == 'key_press':
                self._press_key(event['key'])
            elif etype == 'key_release':
                self._release_key(event['key'])

    def _parse_key(self, key_str):
        special = {
            'Key.space': Key.space,
            'Key.enter': Key.enter,
            'Key.tab': Key.tab,
            'Key.backspace': Key.backspace,
            'Key.shift': Key.shift,
            'Key.shift_r': Key.shift_r,
            'Key.ctrl': Key.ctrl,
            'Key.ctrl_r': Key.ctrl_r,
            'Key.alt': Key.alt,
            'Key.alt_r': Key.alt_r,
            'Key.cmd': Key.cmd,
            'Key.cmd_r': Key.cmd_r,
            'Key.esc': Key.esc,
            'Key.up': Key.up,
            'Key.down': Key.down,
            'Key.left': Key.left,
            'Key.right': Key.right,
            'Key.delete': Key.delete,
            'Key.home': Key.home,
            'Key.end': Key.end,
            'Key.page_up': Key.page_up,
            'Key.page_down': Key.page_down,
            'Key.f1': Key.f1, 'Key.f2': Key.f2, 'Key.f3': Key.f3,
            'Key.f4': Key.f4, 'Key.f5': Key.f5, 'Key.f6': Key.f6,
            'Key.f7': Key.f7, 'Key.f8': Key.f8, 'Key.f9': Key.f9,
            'Key.f10': Key.f10, 'Key.f11': Key.f11, 'Key.f12': Key.f12,
        }
        if key_str in special:
            return special[key_str]
        if key_str and len(key_str) == 1:
            return key_str
        return None

    def _press_key(self, key_str):
        key = self._parse_key(key_str)
        if key:
            try:
                self._keyboard_ctrl.press(key)
            except Exception:
                pass

    def _release_key(self, key_str):
        key = self._parse_key(key_str)
        if key:
            try:
                self._keyboard_ctrl.release(key)
            except Exception:
                pass
