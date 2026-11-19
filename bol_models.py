"""Opt-in, checksum-verified Whisper GGML weights for the existing local runtime."""
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import time
import urllib.parse
import urllib.request

# whisper.cpp conversions of OpenAI Whisper, pinned to this repository revision.
REVISION = '5359861c739e955e79d9a303bcbc70fb988958b1'
MODELS = {
    'tiny': {'title': 'Whisper Tiny', 'size': 77691713, 'sha256': 'be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21', 'hint': '78 MB · Multilingual · Smallest download'},
    'base': {'title': 'Whisper Base', 'size': 147951465, 'sha256': '60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe', 'hint': '148 MB · Multilingual · A good starting point'},
    'small': {'title': 'Whisper Small', 'size': 487601967, 'sha256': '1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b', 'hint': '488 MB · Multilingual · More demanding on your CPU'},
}


def model_folder():
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'bol-linux/models'


class SecureDownloadRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlsplit(newurl)
        if parsed.scheme != 'https' or parsed.username or parsed.password:
            raise ValueError('Model download redirected to an unsafe URL.')
        # Public weights only: no API keys, cookies or account tokens are supplied.
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_model(name, cancelled=lambda: False, progress=lambda done, total: None, folder=None):
    if name not in MODELS:
        raise ValueError('Choose a model from the download catalog.')
    model = MODELS[name]
    folder = Path(folder) if folder is not None else model_folder()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    if shutil.disk_usage(folder).free < model['size'] + 16 * 1024 * 1024:
        raise ValueError('Not enough disk space for this model.')
    destination = folder / ('ggml-' + name + '.bin')
    temporary = None
    deadline = time.monotonic() + 3600
    try:
        url = f'https://huggingface.co/ggerganov/whisper.cpp/resolve/{REVISION}/ggml-{name}.bin'
        opener = urllib.request.build_opener(SecureDownloadRedirect())
        with opener.open(url, timeout=20) as response, tempfile.NamedTemporaryFile(dir=folder, prefix='.download-', delete=False) as output:
            temporary = Path(output.name)
            digest = hashlib.sha256()
            received = 0
            while True:
                if cancelled():
                    raise ValueError('Download cancelled.')
                if time.monotonic() > deadline:
                    raise ValueError('Download timed out. Try again.')
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                received += len(chunk)
                if received > model['size']:
                    raise ValueError('Downloaded model exceeds its expected size.')
                output.write(chunk)
                digest.update(chunk)
                progress(received, model['size'])
            if received != model['size'] or digest.hexdigest() != model['sha256']:
                raise ValueError('Model verification failed. Please download again.')
            if cancelled():
                raise ValueError('Download cancelled.')
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        return destination
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
