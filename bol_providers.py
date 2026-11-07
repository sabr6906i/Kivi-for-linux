"""Local whisper.cpp and configurable compatible speech/chat APIs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import urllib.error
import uuid

SPEECH_PROVIDERS=['sarvam','whispercpp','compatible']
WRITING_PROVIDERS=['sarvam','compatible']


def detect_whisper():
    base=Path.home()/'.local/share/whisper-dictation'
    executable=shutil.which('whisper-cli') or str(base/'bin/whisper-cli')
    model=base/'models/ggml-small.en.bin'
    return executable if Path(executable).is_file() else '',str(model) if model.is_file() else ''


def local_paths(settings):
    binary,model=detect_whisper()
    return Path(settings.get('whisper_binary') or binary).expanduser(),Path(settings.get('whisper_model') or model).expanduser()


def api_endpoint(url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use an endpoint URL without embedded credentials, query parameters, or fragments.')
    if not parsed.hostname or (parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ['localhost','127.0.0.1','::1'])):
        raise ValueError('Use HTTPS, or HTTP for a server on localhost.')
    return url.rstrip('/')


def validate_speech(settings):
    provider=settings.get('speech_provider','sarvam')
    if provider=='sarvam':
        if not settings.get('api_key'):raise ValueError('Save your Sarvam API key in General first.')
    elif provider=='whispercpp':
        binary,model=local_paths(settings)
        if not binary.is_file() or not os.access(binary,os.X_OK):raise ValueError('Choose a valid executable whisper-cli binary.')
        if not model.is_file():raise ValueError('Choose a downloaded whisper.cpp model file.')
        language=settings.get('language','unknown')
        if '.en.' in model.name and language not in ['unknown','en-IN']:
            raise ValueError('This Whisper model is English-only. Select English/auto, or choose a multilingual model.')
        if settings.get('output_mode','transcribe') not in ['transcribe','verbatim','translate']:
            raise ValueError('Local Whisper supports original language, verbatim and English translation. Choose one of those output styles.')
    elif provider=='compatible':
        api_endpoint(settings.get('speech_api_url',''))
        if not settings.get('speech_api_model','').strip():raise ValueError('Enter a speech model ID.')
        if settings.get('output_mode','transcribe') not in ['transcribe','verbatim']:
            raise ValueError('The compatible speech endpoint uses transcription. Select original language or verbatim.')
    else:raise ValueError('Unknown speech provider.')


def transcribe_local(path,settings,cancelled=lambda:False,on_process=lambda p:None):
    validate_speech(settings)
    binary,model=local_paths(settings)
    language=settings.get('language','unknown')
    language='en' if '.en.' in model.name else 'auto' if language=='unknown' else language.split('-')[0]
    output=path.parent/('whisper-'+uuid.uuid4().hex)
    args=[str(binary),'-m',str(model),'-f',str(path),'-l',language,'-otxt','-of',str(output),'-nt','-np','-t',str(min(8,os.cpu_count() or 4))]
    if settings.get('output_mode')=='translate':args+=['-tr']
    if settings.get('vocabulary'):args+=['--prompt',', '.join(settings['vocabulary'])[:1500]]
    env=os.environ.copy()
    env['LD_LIBRARY_PATH']=os.pathsep.join(filter(None,[str(binary.parent),str(binary.parent.parent/'lib'),env.get('LD_LIBRARY_PATH','')]))
    # Diagnostics may include recognized speech: keep them in the temporary audio directory.
    with (path.parent/'whisper.log').open('wb') as log:
        process=subprocess.Popen(args,stdout=log,stderr=log,env=env)
        on_process(process)
        deadline=time.monotonic()+600
        try:
            while process.poll() is None:
                if cancelled():raise RuntimeError('Cancelled')
                if time.monotonic()>deadline:raise RuntimeError('Local Whisper timed out after ten minutes.')
                time.sleep(.05)
            if cancelled():raise RuntimeError('Cancelled')
            if process.returncode:raise RuntimeError('whisper.cpp failed. Check binary libraries, model and audio compatibility.')
        finally:
            if process.poll() is None:process.terminate()
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            on_process(None)
    result=output.with_suffix('.txt')
    text=result.read_text().strip() if result.exists() else ''
    if not text:raise RuntimeError('Local Whisper returned no speech.')
    return text


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise RuntimeError('API endpoint redirected. Enter the final API endpoint URL directly.')


def request_json(url,key,body,content_type):
    url=api_endpoint(url)
    headers={'Content-Type':content_type}
    if key:headers['Authorization']='Bearer '+key
    req=urllib.request.Request(url,data=body,headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=90) as response:return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'Configured API returned HTTP {error.code}. Check endpoint, model, key and credits.') from None


def transcribe_api(path,settings):
    validate_speech(settings)
    boundary=uuid.uuid4().hex
    fields={'model':settings['speech_api_model'],'response_format':'json'}
    language=settings.get('language','unknown')
    if language!='unknown':fields['language']=language.split('-')[0]
    if settings.get('vocabulary'):fields['prompt']=', '.join(settings['vocabulary'])[:1500]
    parts=[]
    for key,value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    parts += [f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="speech.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode(),path.read_bytes(),f'\r\n--{boundary}--\r\n'.encode()]
    result=request_json(settings['speech_api_url'],settings.get('speech_api_key',''),b''.join(parts),'multipart/form-data; boundary='+boundary)
    text=result.get('text','').strip()
    if not text:raise RuntimeError('Speech API returned no text.')
    return text


def chat_api(payload,settings):
    payload={**payload,'model':settings.get('writing_api_model','').strip()}
    if not payload['model']:raise ValueError('Enter a writing model ID.')
    return request_json(settings.get('writing_api_url',''),settings.get('writing_api_key',''),json.dumps(payload).encode(),'application/json')
