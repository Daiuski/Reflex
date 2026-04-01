"""
Standalone recorder subprocess.
Runs entirely outside pywebview — owns its own main thread + CFRunLoop.
Protocol:
  stdout ← "ready\n"          once listeners are up
  stdout ← json + "\n"        when stop is received (events + duration)
  stdin  → anything + "\n"    triggers stop
"""
import sys, json, time, threading

def main():
    try:
        from pynput import mouse, keyboard
    except Exception as e:
        sys.stdout.write(json.dumps({'error': f'pynput import failed: {e}'}) + '\n')
        sys.stdout.flush()
        return

    events = []
    start_time = time.time()
    last_move = [0.0]
    move_interval = 1.0 / 60

    def ts():
        return round(time.time() - start_time, 4)

    def on_move(x, y):
        now = time.time()
        if now - last_move[0] < move_interval:
            return
        last_move[0] = now
        events.append({'type': 'move', 'x': x, 'y': y, 't': ts()})

    def on_click(x, y, button, pressed):
        events.append({'type': 'click', 'x': x, 'y': y,
                       'button': button.name, 'pressed': pressed, 't': ts()})

    def on_scroll(x, y, dx, dy):
        events.append({'type': 'scroll', 'x': x, 'y': y,
                       'dx': dx, 'dy': dy, 't': ts()})

    def key_str(key):
        try:
            c = key.char
            if c is not None:
                return c
        except (AttributeError, ValueError):
            pass
        return str(key)

    def on_press(key):
        events.append({'type': 'key_press', 'key': key_str(key), 't': ts()})

    def on_release(key):
        events.append({'type': 'key_release', 'key': key_str(key), 't': ts()})

    try:
        ml = mouse.Listener(on_move=on_move, on_click=on_click,
                            on_scroll=on_scroll, suppress=False)
        kl = keyboard.Listener(on_press=on_press, on_release=on_release,
                               suppress=False)
        ml.start(); ml.wait()
        kl.start(); kl.wait()
    except Exception as e:
        sys.stdout.write(json.dumps({'error': str(e)}) + '\n')
        sys.stdout.flush()
        return

    sys.stdout.write('ready\n')
    sys.stdout.flush()

    # Block until parent sends stop signal
    try:
        sys.stdin.readline()
    except Exception:
        pass

    try: ml.stop()
    except Exception: pass
    try: kl.stop()
    except Exception: pass

    result = {
        'events': events,
        'duration': round(time.time() - start_time, 2),
        'event_count': len(events),
    }
    sys.stdout.write(json.dumps(result) + '\n')
    sys.stdout.flush()

if __name__ == '__main__':
    main()
