#!/usr/bin/env python3
"""Independent Linux dictation app. Python standard library only."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
import uuid

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'bol-linux'
RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', f'/tmp/bol-{os.getuid()}')) / 'bol-linux'
SOCKET = RUNTIME / 'control.sock'
SCRIPT = str(Path(__file__).resolve())


def config():
    try:
        return json.loads((CONFIG / 'settings.json').read_text())
    except FileNotFoundError:
        return {}


def save_config(value):
    CONFIG.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(mode='w', dir=CONFIG, delete=False) as f:
        json.dump(value, f)
        name = f.name
    os.chmod(name, 0o600)
    os.replace(name, CONFIG / 'settings.json')


def notify(message):
    if shutil.which('notify-send'):
        def send():
            try:
                subprocess.run(['notify-send', '-a', 'Bol', '-r', '7868', '-t', '2500', 'Bol dictation', message], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
            except subprocess.TimeoutExpired:
                pass
        threading.Thread(target=send, daemon=True).start()


def multipart(audio, language):
    boundary = uuid.uuid4().hex
    parts = []
    for key, value in [('model', 'saaras:v4'), ('language_code', language)]:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="speech.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode())
    parts.extend([audio, f'\r\n--{boundary}--\r\n'.encode()])
    return b''.join(parts), boundary


def transcribe(path, settings):
    body, boundary = multipart(path.read_bytes(), settings.get('language', 'unknown'))
    request = urllib.request.Request('https://api.sarvam.ai/speech-to-text', data=body,
        headers={'api-subscription-key': settings['api_key'], 'Content-Type': f'multipart/form-data; boundary={boundary}'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'Sarvam returned HTTP {error.code}. Check your API key, credits and connection.') from None
    text = result.get('transcript', '').strip()
    if not text:
        raise RuntimeError('No speech detected. Please try again.')
    return text


class Service:
    def __init__(self):
        self.lock = threading.RLock()
        self.state = 'Ready'
        self.error = ''
        self.recorder = None
        self.directory = None
        self.target = ''
        self.generation = 0

    def status(self):
        return {'state': self.state, 'error': self.error}

    def cancel(self):
        self.generation += 1
        if self.recorder:
            self.recorder.send_signal(signal.SIGINT)
            self.recorder.wait(timeout=5)
            self.recorder = None
        if self.directory:
            self.directory.cleanup()
            self.directory = None
        self.state, self.error = 'Ready', ''
        notify('Cancelled. Microphone stopped.')
        return self.status()

    def command(self, command):
        with self.lock:
            if command == 'status':
                return self.status()
            if command == 'cancel':
                return self.cancel()
            if command != 'toggle':
                return {'error': 'Unknown command'}
            if self.state == 'Transcribing':
                return self.status()
            if self.recorder:
                self.finish(self.generation)
                return self.status()
            settings = config()
            if not settings.get('api_key'):
                self.error = 'Open Bol settings and save your Sarvam API key first.'
                notify(self.error)
                return self.status()
            for binary in ['pw-record', 'wl-copy', 'hyprctl']:
                if not shutil.which(binary):
                    raise RuntimeError(f'Missing dependency: {binary}')
            active = subprocess.run(['hyprctl', '-j', 'activewindow'], capture_output=True, text=True, check=True)
            self.target = json.loads(active.stdout).get('address', '')
            self.directory = tempfile.TemporaryDirectory(prefix='recording-', dir=RUNTIME)
            self.path = Path(self.directory.name) / 'speech.wav'
            self.recorder = subprocess.Popen(['pw-record', '--rate=16000', '--channels=1', '--format=s16', str(self.path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.state, self.error = 'Recording', ''
            self.generation += 1
            generation = self.generation
            timer = threading.Timer(25, self.auto_finish, args=(generation,))
            timer.daemon = True
            timer.start()
            notify('Listening… Press the shortcut again to finish. Limit: 25 seconds.')
            return self.status()

    def auto_finish(self, generation):
        with self.lock:
            if self.recorder and self.generation == generation:
                self.finish(generation)

    def finish(self, generation):
        self.recorder.send_signal(signal.SIGINT)
        self.recorder.wait(timeout=5)
        self.recorder = None
        self.state = 'Transcribing'
        directory, path, target = self.directory, self.path, self.target
        self.directory = None
        threading.Thread(target=self.deliver, args=(generation, directory, path, target), daemon=True).start()

    def deliver(self, generation, directory, path, target):
        try:
            if not path.exists() or path.stat().st_size < 100:
                raise RuntimeError('No audio recorded. Check your microphone in PipeWire.')
            settings = config()
            text = transcribe(path, settings)
            with self.lock:
                if generation != self.generation:
                    return
                subprocess.run(['wl-copy', '--', text], check=True, timeout=5)
                # Never refocus a window or paste into a different application.
                current = subprocess.run(['hyprctl', '-j', 'activewindow'], capture_output=True, text=True, check=True)
                same_window = target and json.loads(current.stdout).get('address') == target
                if settings.get('auto_paste', True) and same_window:
                    pasted = subprocess.run(['hyprctl', 'dispatch', 'hl.dsp.send_shortcut({ mods = "CTRL", key = "V" })'], capture_output=True, text=True, timeout=5)
                    if pasted.returncode or 'ok' not in pasted.stdout.lower():
                        raise RuntimeError('Text copied, but automatic paste failed. Press Ctrl+V.')
                    notify('Dictation pasted.')
                else:
                    notify('Dictation copied. Press Ctrl+V to paste.')
                self.state, self.error = 'Ready', ''
        except Exception as error:
            with self.lock:
                if generation == self.generation:
                    self.state, self.error = 'Ready', str(error)
                    notify(self.error)
        finally:
            directory.cleanup()


def request(command, start=True):
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(10)
            client.connect(str(SOCKET))
            client.sendall(command.encode())
            return json.loads(client.recv(8192))
    except (FileNotFoundError, ConnectionRefusedError):
        if not start:
            raise
        subprocess.Popen([sys.executable, SCRIPT, 'daemon'], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            time.sleep(.05)
            try:
                return request(command, start=False)
            except (FileNotFoundError, ConnectionRefusedError):
                pass
        raise RuntimeError('Could not start Bol background service.')


def daemon():
    import fcntl
    RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (RUNTIME / 'daemon.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        SOCKET.unlink(missing_ok=True)
        service = Service()
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(SOCKET))
            os.chmod(SOCKET, 0o600)
            server.listen(5)
            try:
                while True:
                    client, _ = server.accept()
                    with client:
                        client.settimeout(5)
                        try:
                            result = service.command(client.recv(64).decode())
                        except Exception as error:
                            result = {'error': str(error)}
                        client.sendall(json.dumps(result).encode())
            finally:
                service.cancel()
                SOCKET.unlink(missing_ok=True)


def gui():
    import tkinter as tk
    from tkinter import ttk, messagebox
    root = tk.Tk()
    root.title('Bol · Voice typing for Linux')
    root.geometry('510x430')
    root.configure(bg='#111827')
    root.resizable(False, False)
    settings = config()
    frame = ttk.Frame(root, padding=26)
    frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='Bol', font=('', 26, 'bold')).pack(anchor='w')
    ttk.Label(frame, text='Speak naturally. Type anywhere.', font=('', 12)).pack(anchor='w', pady=(0, 16))
    status = tk.StringVar(value='Ready')
    ttk.Label(frame, textvariable=status, wraplength=450).pack(anchor='w', pady=8)
    ttk.Label(frame, text='Sarvam API key').pack(anchor='w')
    key = tk.StringVar(value=settings.get('api_key', ''))
    ttk.Entry(frame, textvariable=key, show='•', width=52).pack(fill='x', pady=(4, 12))
    ttk.Label(frame, text='Speech language').pack(anchor='w')
    language = tk.StringVar(value=settings.get('language', 'unknown'))
    ttk.Combobox(frame, textvariable=language, state='readonly', values=['unknown', 'en-IN', 'hi-IN', 'pa-IN', 'ta-IN', 'te-IN', 'bn-IN', 'mr-IN', 'gu-IN', 'kn-IN', 'ml-IN', 'ur-IN']).pack(fill='x', pady=4)
    paste = tk.BooleanVar(value=settings.get('auto_paste', True))
    ttk.Checkbutton(frame, text='Paste automatically when the original app is focused', variable=paste).pack(anchor='w', pady=8)
    def save():
        save_config({'api_key': key.get().strip(), 'language': language.get(), 'auto_paste': paste.get()})
        messagebox.showinfo('Saved', 'Settings saved locally. Use F8 in the app where you want to type.')
    ttk.Button(frame, text='Save settings', command=save).pack(anchor='w', pady=6)
    ttk.Button(frame, text='Cancel recording / pending result', command=lambda: request('cancel')).pack(anchor='w')
    ttk.Label(frame, text='Audio is sent to Sarvam for transcription.\nRecordings are deleted after each request.', foreground='#666666').pack(anchor='w', pady=12)
    def poll():
        try:
            result = request('status')
            status.set(result.get('error') or result['state'])
        except Exception as error:
            status.set(str(error))
        root.after(1000, poll)
    root.after(100, poll)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', default='settings', choices=['settings', 'toggle', 'cancel', 'status', 'daemon', 'doctor'])
    args = parser.parse_args()
    if args.command == 'daemon':
        daemon()
    elif args.command == 'settings':
        gui()
    elif args.command == 'doctor':
        for name in ['python', 'pw-record', 'wl-copy', 'hyprctl', 'notify-send']:
            print(f'{name}: {shutil.which(name) or "MISSING"}')
        print('API key:', 'configured' if config().get('api_key') else 'not configured')
        print('Session:', os.environ.get('XDG_SESSION_TYPE', 'unknown'))
    else:
        print(json.dumps(request(args.command)))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Bol: {error}', file=sys.stderr)
        sys.exit(1)
