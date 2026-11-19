#!/usr/bin/env python3
"""Independent Linux dictation app. Python standard library only."""
import argparse
import json
import os
import re
import wave
from copy import deepcopy
from datetime import datetime, timezone
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

from bol_features import DEFAULTS, History, expand, write
from bol_providers import validate_speech, transcribe_local, transcribe_api
import bol_desktop as desktop

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'bol-linux'
RUNTIME = Path(os.environ.get('XDG_RUNTIME_DIR', f'/tmp/bol-{os.getuid()}')) / 'bol-linux'
SOCKET = RUNTIME / 'control.sock'
SCRIPT = str(Path(__file__).resolve())


def config():
    try:
        return {**deepcopy(DEFAULTS), **json.loads((CONFIG / 'settings.json').read_text())}
    except FileNotFoundError:
        return deepcopy(DEFAULTS)


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


def multipart(audio, language, mode="transcribe", vocabulary=None):
    boundary = uuid.uuid4().hex
    parts = []
    fields = [('model', 'saaras:v4'), ('language_code', language), ('mode', mode)]
    if vocabulary:
        fields.append(('keyterms', json.dumps(vocabulary[:50], ensure_ascii=False)))
    for key, value in fields:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="speech.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode())
    parts.extend([audio, f'\r\n--{boundary}--\r\n'.encode()])
    return b''.join(parts), boundary


def transcribe_one(path, settings):
    if settings.get('speech_provider') == 'compatible':
        return transcribe_api(path, settings)
    body, boundary = multipart(path.read_bytes(), settings.get('language', 'unknown'), settings.get('output_mode', 'transcribe'), settings.get('vocabulary', []))
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


def transcribe(path, settings, cancelled=lambda: False, on_process=lambda p: None):
    if settings.get('speech_provider') == 'elevenlabs':
        from bol_elevenlabs import transcribe as elevenlabs_transcribe
        return elevenlabs_transcribe(path,settings,cancelled,on_process)
    if settings.get('speech_provider') == 'whispercpp':
        return transcribe_local(path, settings, cancelled, on_process)
    with wave.open(str(path), 'rb') as audio:
        seconds = audio.getnframes() / audio.getframerate()
    if cancelled():
        raise RuntimeError('Cancelled')
    if seconds < 26:
        return transcribe_one(path, settings)
    # Keep each REST request below the API's short-audio limit.
    if not shutil.which('ffmpeg'):
        raise RuntimeError('Long recordings need ffmpeg. Install it or record less than 25 seconds.')
    segment = str(path.parent / 'part-%03d.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'segment', '-segment_time', '24', '-c:a', 'pcm_s16le', segment], check=True, timeout=30, capture_output=True)
    texts = []
    for chunk in sorted(path.parent.glob('part-*.wav')):
        if cancelled():
            raise RuntimeError('Cancelled')
        texts.append(transcribe_one(chunk, settings))
    return '\n'.join(texts)


def active_window():
    return desktop.active_window()


def shortcut(key, mods='CTRL'):
    return desktop.shortcut(key, mods)


def copy_text(text):
    return desktop.copy_text(text)


def read_clipboard():
    return desktop.read_clipboard()


def focus_window(target):
    return desktop.focus_window(target)


def selection_for(target):
    """Explicit Ctrl+C capture with sentinel; never mistake old clipboard text for a selection."""
    if not target or active_window().get('address') != target:
        return ''
    try:old = read_clipboard()
    except ValueError:old = b''
    sentinel = 'bol-selection-' + uuid.uuid4().hex
    copy_text(sentinel)
    try:
        shortcut('C')
        for _ in range(12):
            time.sleep(.04)
            try:copied = read_clipboard()
            except ValueError:continue
            if copied != sentinel.encode():
                if active_window().get('address') == target:
                    return copied.decode('utf-8', errors='replace')[:24000]
                return ''
        return ''
    finally:
        copy_text(old)


class Service:
    def __init__(self):
        self.lock = threading.RLock()
        self.state = 'Ready'
        self.error = ''
        self.recorder = None
        self.inference_process = None
        self.directory = None
        self.target = ''
        self.app = ''
        self.selection = ''
        self.mode = 'dictate'
        self.generation = 0
        self.latest = ''
        self.latest_metadata = {}
        self.original = ''
        self.started = 0
        self.outcome = ''
        self.settings = {}
        self.pending_edit = None

    def status(self):
        return {'state': self.state, 'error': self.error, 'mode': self.mode,
                'seconds': round(time.monotonic() - self.started, 1) if self.recorder else 0,
                'outcome': self.outcome, 'has_result': bool(self.latest), 'has_pending_edit': self.pending_edit is not None}

    def stop_recorder(self):
        if self.recorder:
            process, self.recorder = self.recorder, None
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)

    def cancel(self, silent=False):
        self.generation += 1
        self.pending_edit = None
        self.stop_recorder()
        if self.inference_process and self.inference_process.poll() is None:
            self.inference_process.terminate()
        if self.directory:
            self.directory.cleanup()
            self.directory = None
        self.state, self.error, self.outcome = 'Ready', '', 'Cancelled'
        if not silent:
            notify('Cancelled. Microphone stopped.')
        return self.status()

    def command(self, command):
        with self.lock:
            payload=command if isinstance(command,dict) else {}
            command=payload.get('command') if payload else command
            if command == 'review':
                return {key:self.pending_edit[key] for key in ['generation','text','original','selection','app']} if self.pending_edit else {'error':'No edit is waiting for review.'}
            if command == 'accept-edit':
                if not self.pending_edit or payload.get('generation')!=self.pending_edit['generation']:
                    return {'error':'This edit is no longer waiting for review.'}
                pending=self.pending_edit
                text=payload.get('text',pending['text'])
                if not isinstance(text,str) or not text.strip() or len(text)>100000:
                    return {'error':'The reviewed text must contain 1–100000 characters.'}
                self.pending_edit=None
                try:
                    self.commit_result(pending['generation'],text,pending['original'],pending['settings'],pending['app'],'edit',pending['selection'],pending['target'],focus=True)
                except Exception as error:
                    self.state,self.error='Ready',str(error)
                return self.status()
            if command == 'status':
                return self.status()
            if command == 'result':
                return {'text': self.latest, 'original': self.original, **self.latest_metadata}
            if command == 'copy-last':
                if self.latest:
                    copy_text(self.latest)
                    notify('Last result copied.')
                return self.status()
            if command == 'cancel':
                return self.cancel()
            if command == 'stop':
                if self.recorder:
                    self.finish(self.generation)
                return self.status()
            if command not in ['toggle', 'start', 'edit', 'edit-clipboard']:
                return {'error': 'Unknown command'}
            if self.state in ['Transcribing', 'Writing', 'Review']:
                notify('An edit is waiting in Bol for review.' if self.state=='Review' else 'Still processing. F9 cancels this request.')
                return self.status()
            if self.recorder:
                if command != 'start':
                    self.finish(self.generation)
                return self.status()
            settings = config()
            try:
                validate_speech(settings)
                copied_source = None
                if command == 'edit' and not desktop.desktop_info()['selection_capture']:
                    raise ValueError('This Wayland desktop cannot capture another app’s selection. Copy the text, then run bol edit-clipboard; the reviewed result will be copied for you to paste.')
                if command == 'edit-clipboard':
                    copied_source = payload['source'] if 'source' in payload else read_clipboard().decode('utf-8', errors='replace')
                    if not isinstance(copied_source,str):raise ValueError('The copied source must be text.')
                    if not copied_source.strip():raise ValueError('Copy the text you want to edit before running bol edit-clipboard.')
                    if len(copied_source)>24000:raise ValueError('Copy at most 24000 characters for voice editing.')
                if command in ('edit', 'edit-clipboard') and settings.get('speech_provider') == 'whispercpp' and not settings.get('local_speech_writing'):
                    raise ValueError('Enable AI writing with local speech in Writing settings to use voice editing.')
            except ValueError as error:
                self.error = str(error)
                notify(self.error)
                return self.status()
            for binary in desktop.recording_dependencies():
                if not shutil.which(binary):
                    raise RuntimeError(f'Missing dependency: {binary}')
            active = active_window()
            self.target, self.app = active.get('address', ''), active.get('class', '')
            self.mode = 'edit' if command in ('edit', 'edit-clipboard') else 'dictate'
            terminal = any(name in self.app.casefold() for name in ['kitty', 'alacritty', 'foot', 'wezterm', 'konsole', 'terminal'])
            self.selection = copied_source if copied_source is not None else selection_for(self.target) if self.mode == 'edit' and not terminal else ''
            if copied_source is not None:self.target = ''  # Explicit clipboard edits are never inserted into an inferred source window.
            self.settings = settings
            self.directory = tempfile.TemporaryDirectory(prefix='recording-', dir=RUNTIME)
            self.path = Path(self.directory.name) / 'speech.wav'
            args = ['pw-record', '--rate=16000', '--channels=1', '--format=s16']
            if settings.get('microphone'):
                args += ['--target', settings['microphone']]
            self.recorder = subprocess.Popen(args + [str(self.path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.state, self.error, self.outcome = 'Recording', '', ''
            self.started = time.monotonic()
            self.generation += 1
            generation = self.generation
            timer = threading.Timer(min(300, max(5, int(settings.get('record_seconds', 120)))), self.auto_finish, args=(generation,))
            timer.daemon = True
            timer.start()
            notify('Listening for an editing instruction…' if self.mode == 'edit' else 'Listening… Press the recording key again to finish.')
            return self.status()

    def auto_finish(self, generation):
        with self.lock:
            if self.recorder and self.generation == generation:
                self.finish(generation)

    def finish(self, generation):
        self.stop_recorder()
        self.state = 'Transcribing'
        directory, path, target = self.directory, self.path, self.target
        self.directory = None
        context = (dict(self.settings), self.app, self.mode, self.selection)
        threading.Thread(target=self.deliver, args=(generation, directory, path, target, context), daemon=True).start()

    def deliver(self, generation, directory, path, target, context):
        settings, app, mode, selection = context
        try:
            if not path.exists() or path.stat().st_size < 100:
                raise RuntimeError('No audio recorded. Check your microphone in PipeWire.')
            def local_process(process):
                with self.lock:
                    if generation == self.generation:
                        self.inference_process = process
                    elif process and process.poll() is None:
                        process.terminate()
            original = transcribe(path, settings, cancelled=lambda: generation != self.generation, on_process=local_process)
            with self.lock:
                if generation != self.generation:
                    return
            text, snippet = expand(original, settings)
            warning = ''
            writing_allowed = settings.get('speech_provider') != 'whispercpp' or settings.get('local_speech_writing', False)
            if mode == 'edit' or (settings.get('polish') and not snippet and writing_allowed):
                with self.lock:
                    if generation != self.generation:
                        return
                    self.state = 'Writing'
                try:
                    text = write(text, settings, app=app, selection=selection, editing=mode == 'edit')
                except Exception as error:
                    if mode == 'edit':
                        raise
                    warning = str(error) + ' Original transcription recovered.'
            with self.lock:
                if generation != self.generation:
                    return
                if mode=='edit' and settings.get('review_edits',False):
                    self.pending_edit={'generation':generation,'text':text,'original':original,'settings':settings,'app':app,'selection':selection,'target':target}
                    self.state,self.error,self.outcome='Review','','Edit ready — review it in Bol'
                    notify(self.outcome)
                    return
                self.commit_result(generation,text,original,settings,app,mode,selection,target,warning=warning)
        except Exception as error:
            with self.lock:
                if generation == self.generation:
                    self.state, self.error = 'Ready', str(error)
                    notify(self.error)
        finally:
            directory.cleanup()


    def commit_result(self,generation,text,original,settings,app,mode,selection,target,warning='',focus=False):
        if generation!=self.generation:return
        self.latest, self.original = text, original
        self.latest_metadata = {'app': app, 'mode': mode, 'created': datetime.now(timezone.utc).isoformat()}
        if focus and target and focus_window(target):
            time.sleep(.15)
        if settings.get('history_enabled'):
            History(CONFIG,settings.get('history_retention_days',0)).add(app, mode, original, text)
        same_window = target and active_window().get('address') == target
        selection_unchanged = True
        terminal = any(name in app.casefold() for name in ['kitty', 'alacritty', 'foot', 'wezterm', 'konsole', 'terminal'])
        if mode == 'edit' and same_window and not terminal:
            selection_unchanged = selection_for(target) == selection
        try:copy_text(text)
        except (OSError, subprocess.SubprocessError, RuntimeError, ValueError):
            self.state = 'Ready'
            self.error = warning or 'Clipboard access is unavailable on this desktop. Open Bol History and use Copy, then paste into your app.'
            self.outcome = 'Text ready in Bol — use History → Copy'
            notify(self.error)
            return
        same_window = same_window and active_window().get('address') == target
        if settings.get('auto_paste', True) and same_window and selection_unchanged:
            # Electron editors and terminals often use different paste shortcuts.
            terminal = any(name in app.casefold() for name in ['kitty', 'alacritty', 'foot', 'wezterm', 'konsole', 'terminal'])
            if mode == 'edit' and selection:
                # Some X11 text widgets insert on Ctrl+V without replacing a selection.
                shortcut('BackSpace', '')
            shortcut('V', 'CTRL SHIFT' if terminal else 'CTRL')
            self.outcome = 'Paste shortcut sent'
        else:
            self.outcome = 'Copied — paste into your app' if not target else 'Copied — paste manually (focus or selection changed)' if not same_window or not selection_unchanged else 'Copied'
        self.state, self.error = 'Ready', warning
        notify(warning or self.outcome)


def request(command, start=True):
    try:
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(10)
            client.connect(str(SOCKET))
            client.sendall((json.dumps(command) if isinstance(command,dict) else command).encode())
            client.shutdown(socket.SHUT_WR)
            chunks = []
            while chunk := client.recv(65536):
                chunks.append(chunk)
            return json.loads(b''.join(chunks))
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
        def terminate(signum, frame):
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, terminate)
        signal.signal(signal.SIGINT, terminate)
        indicator = subprocess.Popen([sys.executable, SCRIPT, 'indicator'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
                            chunks=[]
                            size=0
                            while chunk:=client.recv(65536):
                                size+=len(chunk)
                                if size>1048576:raise ValueError('Control request is too large.')
                                chunks.append(chunk)
                            message=b''.join(chunks).decode()
                            result = service.command(json.loads(message) if message.startswith('{') else message)
                        except Exception as error:
                            result = {'error': str(error)}
                        client.sendall(json.dumps(result).encode())
            finally:
                service.cancel(silent=True)
                indicator.terminate()
                SOCKET.unlink(missing_ok=True)


def gui():
    try:
        from bol_gtk import settings_window
    except (ImportError, ValueError):
        from bol_ui import settings_window
    settings_window(sys.modules[__name__])


def indicator():
    from bol_ui import recording_indicator
    recording_indicator(sys.modules[__name__])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', default='settings', choices=['settings', 'toggle', 'start', 'stop', 'edit', 'edit-clipboard', 'cancel', 'status', 'result', 'copy-last', 'daemon', 'doctor', 'indicator'])
    args = parser.parse_args()
    if args.command == 'daemon':
        daemon()
    elif args.command == 'indicator':
        indicator()
    elif args.command == 'settings':
        gui()
    elif args.command == 'doctor':
        print('Desktop:', desktop.desktop_info()['name'], '('+desktop.desktop_info()['session']+')')
        print(desktop.desktop_info()['summary'])
        for name in ['python', 'notify-send'] + desktop.recording_dependencies():
            print(f'{name}: {shutil.which(name) or "MISSING"}')
        print('API key:', 'configured' if config().get('api_key') else 'not configured')
        print('Speech provider:', config().get('speech_provider', 'sarvam'))
        print('Writing provider:', config().get('writing_provider', 'sarvam'))
        from bol_providers import detect_whisper
        binary, model = detect_whisper()
        print('Detected whisper.cpp:', binary or 'not found')
        print('Detected Whisper model:', model or 'not found')
        if desktop.desktop_info()['backend']=='wayland':
            for name in ['wl-copy','wl-paste']:print(f'{name} (optional background clipboard): {shutil.which(name) or "unavailable; use Bol Copy"}')
        print('Session:', os.environ.get('XDG_SESSION_TYPE', 'unknown'))
    else:
        print(json.dumps(request(args.command)))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Bol: {error}', file=sys.stderr)
        sys.exit(1)
