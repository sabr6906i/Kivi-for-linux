"""Sarvam text-to-speech with validated WAV output."""
import base64
import io
import json
import urllib.request
import urllib.error
import wave

TTS_LANGUAGES=['en-IN','hi-IN','pa-IN','bn-IN','ta-IN','te-IN','kn-IN','ml-IN','mr-IN','gu-IN','od-IN']
TTS_VOICES=['shubh','ritu','simran','priya','aditya','rahul','kavya','rohan','neha','shreya']


def synthesize(text,key,language='en-IN',voice='shubh',pace=1.0):
    text=text.strip()
    if not text or len(text)>2500:raise ValueError('Enter between 1 and 2500 characters.')
    if not key:raise ValueError('Add your Sarvam API key in Providers first.')
    if language not in TTS_LANGUAGES:raise ValueError('Choose a supported speech language.')
    if voice not in TTS_VOICES:raise ValueError('Choose a supported voice.')
    if not .5<=float(pace)<=2:raise ValueError('Speech speed must be between 0.5 and 2.0.')
    payload={'text':text,'language_code':language,'speaker':voice,'model':'bulbul:v3','pace':float(pace),'speech_sample_rate':24000,'output_audio_codec':'wav'}
    request=urllib.request.Request('https://api.sarvam.ai/text-to-speech',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'api-subscription-key':key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request,timeout=90) as response:result=json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'Speech generation returned HTTP {error.code}. Check key, credits and voice access.') from None
    audios=result.get('audios')
    if not isinstance(audios,list) or not audios:raise RuntimeError('The speech API returned no audio.')
    frames=[];params=None
    try:
        for encoded in audios:
            raw=base64.b64decode(encoded,validate=True)
            with wave.open(io.BytesIO(raw),'rb') as audio:
                current=(audio.getnchannels(),audio.getsampwidth(),audio.getframerate())
                if params and current!=params:raise ValueError('Mismatched audio formats')
                params=current;frames.append(audio.readframes(audio.getnframes()))
        if not any(frames):raise ValueError('Empty audio')
        output=io.BytesIO()
        with wave.open(output,'wb') as audio:
            audio.setnchannels(params[0]);audio.setsampwidth(params[1]);audio.setframerate(params[2]);audio.writeframes(b''.join(frames))
        return output.getvalue()
    except (ValueError,TypeError,wave.Error,EOFError) as error:
        raise RuntimeError('The speech API returned invalid WAV audio.') from error
