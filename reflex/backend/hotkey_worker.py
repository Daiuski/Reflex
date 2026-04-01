"""
Global hotkey listener subprocess.
Runs in its own process/main-thread — avoids macOS CFRunLoop issues with pywebview.

Startup protocol:
  stdin  → JSON line: {"play_stop": "Key.f8", "record": "Key.f9"}
  stdout ← "ready\n"   once listener is up

Runtime protocol:
  stdout ← "<action>\n"           when a hotkey fires  (action = "play_stop" | "record")
  stdin  → "reload <json>\n"      update binds without restart
  stdin  → "quit\n"               shut down
"""
import sys
import json
import threading


def key_to_str(key):
    """Normalise a pynput key to the same string format the JS side stores."""
    try:
        if hasattr(key, 'name'):          # Special key  (Key.f8, Key.ctrl …)
            return f'Key.{key.name}'
        c = key.char
        if c is not None:
            return c.lower()
    except (AttributeError, ValueError):
        pass
    return str(key).lower()


def main():
    try:
        from pynput import keyboard
    except Exception as e:
        sys.stdout.write(json.dumps({'error': f'pynput import failed: {e}'}) + '\n')
        sys.stdout.flush()
        return

    # ── Read initial config ────────────────────────────────────────────────
    try:
        line = sys.stdin.readline().strip()
        config = json.loads(line)
    except Exception as e:
        sys.stdout.write(json.dumps({'error': f'bad config: {e}'}) + '\n')
        sys.stdout.flush()
        return

    # binds: { key_str -> action_name }
    binds = {}
    lock  = threading.Lock()

    def update_binds(cfg):
        new = {}
        for action, key_str in cfg.items():
            if key_str:
                new[key_str] = action
        with lock:
            binds.clear()
            binds.update(new)

    update_binds(config)

    # ── pynput listener ───────────────────────────────────────────────────
    def on_press(key):
        ks = key_to_str(key)
        with lock:
            action = binds.get(ks)
        if action:
            sys.stdout.write(action + '\n')
            sys.stdout.flush()

    try:
        kl = keyboard.Listener(on_press=on_press, suppress=False)
        kl.start()
        kl.wait()
    except Exception as e:
        sys.stdout.write(json.dumps({'error': str(e)}) + '\n')
        sys.stdout.flush()
        return

    sys.stdout.write('ready\n')
    sys.stdout.flush()

    # ── stdin command loop ────────────────────────────────────────────────
    while True:
        try:
            line = sys.stdin.readline()
        except Exception:
            break
        if not line:
            break
        line = line.strip()
        if line == 'quit':
            break
        elif line.startswith('reload '):
            try:
                update_binds(json.loads(line[7:]))
            except Exception:
                pass

    try:
        kl.stop()
    except Exception:
        pass


if __name__ == '__main__':
    main()
