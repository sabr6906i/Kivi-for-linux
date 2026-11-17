"""ElevenLabs OAuth through the official CLI; credentials stay with that CLI."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

CLI_VERSION='1.12.1'
TOOLS=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'bol-linux/tools'


def cli_path():
    return shutil.which('elevenlabs') or (str(TOOLS/'node_modules/.bin/elevenlabs') if (TOOLS/'node_modules/.bin/elevenlabs').exists() else '')


def environment():
    env=os.environ.copy();env['DO_NOT_TRACK']='1'
    return env


def workdir():
    path=Path(os.environ.get('XDG_CACHE_HOME',str(Path.home()/'.cache')))/'bol-linux/elevenlabs'
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    return path


def status():
    binary=cli_path()
    if not binary:return {'installed':False,'logged_in':False}
    result=subprocess.run([binary,'auth','status','--format','json'],capture_output=True,text=True,timeout=15,env=environment(),cwd=workdir())
    if result.returncode:raise RuntimeError('The ElevenLabs helper could not report its sign-in status.')
    data=json.loads(result.stdout)
    return {'installed':True,'logged_in':any(scheme.get('logged_in') for scheme in data.get('schemes',[]))}


def account_action(action,on_process=lambda p:None):
    if action=='install':
        if not shutil.which('npm'):raise RuntimeError('Install Node.js/npm to install the official ElevenLabs helper.')
        command=['npm','install','--prefix',str(TOOLS),'--no-audit','--no-fund','@elevenlabs/cli@'+CLI_VERSION]
    else:
        binary=cli_path()
        if not binary:raise RuntimeError('Install the sign-in helper first.')
        if action not in ['login','logout']:raise ValueError('Unknown connection action.')
        command=[binary,'auth',action]
    process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment(),cwd=workdir())
    on_process(process)
    try:
        _,_=process.communicate(timeout=300)
        if process.returncode:raise RuntimeError('ElevenLabs sign-in did not complete. Try again, or check your browser and account.')
    except subprocess.TimeoutExpired:
        process.kill();process.communicate();raise RuntimeError('ElevenLabs connection timed out. Try again.') from None
    finally:on_process(None)
    return status()


def transcribe(path,settings,cancelled=lambda:False,on_process=lambda p:None):
    binary=cli_path()
    if not binary:raise RuntimeError('Install and connect ElevenLabs in Profile → Connections first.')
    command=[binary,'speech-to-text','convert','--file',str(path),'--model-id',settings.get('elevenlabs_model','scribe_v2'),'--diarize','false','--tag-audio-events','false','--webhook','false','--format','json','--no-retry']
    language=settings.get('language','unknown')
    if language!='unknown':command+=['--language-code',language.split('-')[0]]
    with (path.parent/'elevenlabs-result.json').open('wb') as output, (path.parent/'elevenlabs-error.log').open('wb') as error:
        process=subprocess.Popen(command,stdout=output,stderr=error,stdin=subprocess.DEVNULL,env=environment(),cwd=workdir());on_process(process)
        try:
            deadline=time.monotonic()+300
            while process.poll() is None:
                if cancelled():raise RuntimeError('Cancelled')
                if time.monotonic()>deadline:raise RuntimeError('ElevenLabs transcription timed out.')
                time.sleep(.05)
            if cancelled():raise RuntimeError('Cancelled')
            if process.returncode:raise RuntimeError('ElevenLabs transcription failed. Check sign-in, credits, and the speech model in Connections.')
        finally:
            if process.poll() is None:process.terminate()
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            on_process(None)
    try:text=json.loads((path.parent/'elevenlabs-result.json').read_text()).get('text','').strip()
    except (ValueError,AttributeError):raise RuntimeError('The ElevenLabs helper returned an unexpected response.') from None
    if not text:raise RuntimeError('ElevenLabs returned no speech.')
    return text
