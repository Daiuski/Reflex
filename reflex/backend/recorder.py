import json
import os
import subprocess
import sys
import time


class MacroRecorder:
    def __init__(self):
        self._proc = None
        self._start_time = None

    # Path to the worker script
    _WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'recorder_worker.py')

    @staticmethod
    def _python_executable():
        """Return a real Python interpreter path that works both in dev and inside a py2app bundle."""
        exe = sys.executable
        # Inside a py2app .app bundle sys.executable points to the bundle launcher binary.
        # Walk up to find the bundled python3 in Contents/MacOS/ or fall back to the system one.
        if 'Contents/MacOS' in exe or exe.endswith('.app/Contents/MacOS/python'):
            # Try the python3 shipped inside the bundle first
            bundle_python = os.path.join(os.path.dirname(exe), 'python3')
            if os.path.isfile(bundle_python):
                return bundle_python
            # Fallback: use the system Python (not ideal but prevents a hard crash)
            import shutil
            system_py = shutil.which('python3') or shutil.which('python')
            if system_py:
                return system_py
        return exe

    def start(self):
        """Launch the recorder subprocess. Raises RuntimeError on failure."""
        if self._proc and self._proc.poll() is None:
            return  # already running

        self._proc = subprocess.Popen(
            [self._python_executable(), self._WORKER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._start_time = time.time()

        # Wait for the 'ready' handshake (or an error JSON)
        try:
            line = self._proc.stdout.readline().decode('utf-8', errors='replace').strip()
        except Exception as e:
            self._kill()
            raise RuntimeError(f'Recorder subprocess died: {e}')

        if line != 'ready':
            stderr = self._proc.stderr.read(512).decode('utf-8', errors='replace')
            self._kill()
            # Try to parse an error payload
            try:
                payload = json.loads(line)
                raise RuntimeError(payload.get('error', line))
            except (json.JSONDecodeError, TypeError):
                raise RuntimeError(f'Unexpected response: {line!r}  stderr: {stderr}')

    def stop(self):
        """Stop the recorder and return events dict."""
        if not self._proc:
            return {'events': [], 'duration': 0, 'event_count': 0}

        # Signal the worker to stop
        try:
            self._proc.stdin.write(b'stop\n')
            self._proc.stdin.flush()
        except Exception:
            pass

        # Read the JSON result
        result = {'events': [], 'duration': 0, 'event_count': 0}
        try:
            line = self._proc.stdout.readline().decode('utf-8', errors='replace').strip()
            if line:
                result = json.loads(line)
        except Exception:
            pass

        self._proc.wait(timeout=3)
        self._proc = None
        return result

    def _kill(self):
        try:
            self._proc.kill()
        except Exception:
            pass
        self._proc = None
