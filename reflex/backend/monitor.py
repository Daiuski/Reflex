import time
import threading
import numpy as np
import mss


class ColorMonitor:
    def __init__(self):
        self._triggers  = []        # runtime copies with '_mid' added
        self.running    = False
        self._thread    = None
        self._cooldowns = {}        # mid -> last_fire_time  (for loop triggers)
        self._fired     = set()     # mids that have fire-once'd
        self.on_trigger   = None
        self.on_exhausted = None    # called when all fire-once triggers consumed
        self._lock      = threading.Lock()
        self._mid_seq   = 0

    # ── Trigger management ────────────────────────────────────────────────────

    def add_trigger(self, trigger):
        with self._lock:
            t = dict(trigger)
            t['_mid'] = self._mid_seq
            self._mid_seq += 1
            self._triggers.append(t)

    def remove_trigger(self, index):
        with self._lock:
            if 0 <= index < len(self._triggers):
                self._triggers.pop(index)

    def clear_triggers(self):
        with self._lock:
            self._triggers = []
            self._fired.clear()

    def get_triggers(self):
        with self._lock:
            return list(self._triggers)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self, on_trigger, on_exhausted=None):
        if self.running:
            return
        self.on_trigger   = on_trigger
        self.on_exhausted = on_exhausted
        # Always reset fired set so re-enabling monitoring re-arms all fire-once triggers
        self._fired.clear()
        self._cooldowns.clear()
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

    # ── Main loop ─────────────────────────────────────────────────────────────

    def _run(self):
        with mss.mss() as sct:
            while self.running:
                with self._lock:
                    triggers = list(self._triggers)

                for trigger in triggers:
                    if not self.running:
                        break

                    mid  = trigger['_mid']
                    loop = trigger.get('loop', False)

                    # Fire-once trigger already consumed — skip
                    if not loop and mid in self._fired:
                        continue

                    now = time.time()
                    # Loop triggers respect a 2-second cooldown
                    if loop and now - self._cooldowns.get(mid, 0) < 2.0:
                        continue

                    region       = trigger.get('region', {})
                    target_color = trigger.get('color', {})
                    tolerance    = trigger.get('tolerance', 10)

                    try:
                        mon = {
                            'left':   region['x'],
                            'top':    region['y'],
                            'width':  max(1, region['w']),
                            'height': max(1, region['h']),
                        }
                        screenshot = sct.grab(mon)
                        img     = np.array(screenshot)[:, :, :3]   # BGRA → BGR
                        avg     = img.mean(axis=(0, 1))             # BGR
                        avg_rgb = avg[[2, 1, 0]]                    # → RGB

                        tr   = np.array([target_color['r'],
                                         target_color['g'],
                                         target_color['b']], dtype=float)
                        dist = np.sqrt(np.sum((avg_rgb - tr) ** 2))
                        scaled_tol = tolerance * 2.55               # 0-100 → 0-255

                        if dist <= scaled_tol:
                            if loop:
                                self._cooldowns[mid] = now
                            else:
                                self._fired.add(mid)
                            if self.on_trigger:
                                self.on_trigger(trigger.get('macro_name', ''))
                    except Exception:
                        pass

                # After scanning all triggers: check if all fire-once are consumed
                fire_once_mids = {t['_mid'] for t in triggers if not t.get('loop', False)}
                has_loop       = any(t.get('loop', False) for t in triggers)

                if fire_once_mids and fire_once_mids.issubset(self._fired) and not has_loop:
                    self.running = False
                    if self.on_exhausted:
                        self.on_exhausted()
                    return

                time.sleep(0.1)  # ~10 fps
