"""Sarvam text-to-speech with validated WAV output."""
import base64
import io
import json
import urllib.request
import urllib.error
import wave

TTS_LANGUAGES=['en-IN','hi-IN','pa-IN','bn-IN','ta-IN','te-IN','kn-IN','ml-IN','mr-IN','gu-IN','od-IN']
TTS_VOICES=['shubh','ritu','simran','priya','aditya','rahul','kavya','rohan','neha','shreya','roopa','ratan']


def synthesize(text,key,language='en-IN',voice='shubh',pace=1.0,temperature=.6):
    text=text.strip()
    if not text or len(text)>2500:raise ValueError('Enter between 1 and 2500 characters.')
    if not key:raise ValueError('Add your Sarvam API key in Providers first.')
    if language not in TTS_LANGUAGES:raise ValueError('Choose a supported speech language.')
    if voice not in TTS_VOICES:raise ValueError('Choose a supported voice.')
    if not .5<=float(pace)<=2:raise ValueError('Speech speed must be between 0.5 and 2.0.')
    import math
    if not math.isfinite(float(pace)) or not math.isfinite(float(temperature)) or not .01<=float(temperature)<=1:raise ValueError('Expressiveness must be between 0.01 and 1.0.')
    payload={'temperature':float(temperature),'text':text,'language_code':language,'speaker':voice,'model':'bulbul:v3','pace':float(pace),'speech_sample_rate':24000,'output_audio_codec':'wav'}
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

# Traits are guidance for choosing stock voices, not guarantees of an emotion.
VOICE_TRAITS={
    'shubh':'confident and bold','ritu':'lively and expressive','simran':'rich and mature',
    'priya':'cheerful and engaging','aditya':'crisp and modern','rahul':'deep and authoritative',
    'kavya':'polished and articulate','rohan':'bold and confident','neha':'warm and energetic',
    'shreya':'warm and energetic','roopa':'gentle and soothing','ratan':'rich and mature',
}
STYLE_PRESETS={
    'Manual':None,
    'Calm & soothing':{'voice':'roopa','pace':.85,'temperature':.4},
    'Warm & friendly':{'voice':'neha','pace':.95,'temperature':.55},
    'Professional':{'voice':'kavya','pace':1.0,'temperature':.45},
    'Energetic promo':{'voice':'ritu','pace':1.15,'temperature':.75},
    'Storytelling':{'voice':'ratan','pace':.9,'temperature':.7},
    'Dramatic narration':{'voice':'rahul','pace':.85,'temperature':.8},
}


def suggest_delivery(instructions,settings,language='en-IN'):
    """Map instructions to supported parameters; the script is never sent or rewritten."""
    import math
    instructions=instructions.strip()
    if not instructions or len(instructions)>1500:raise ValueError('Enter 1–1500 characters of delivery instructions.')
    system=('Choose stock text-to-speech settings. Return ONLY one JSON object with voice, pace, temperature. '
            'voice must be an exact key from the supplied voice catalog. pace must be 0.5–2.0; temperature 0.01–1.0. '
            'Higher temperature means more variation, not guaranteed emotion. Interpret instructions only as vocal delivery; '
            'do not write a script or add fields. If a requested effect is unsupported, choose the closest supported controls.')
    payload={'model':settings.get('chat_model','sarvam-105b'),'messages':[{'role':'system','content':system},
             {'role':'user','content':json.dumps({'instructions':instructions,'language':language,'voices':VOICE_TRAITS},ensure_ascii=False)}],
             'temperature':.1,'max_tokens':200}
    if settings.get('writing_provider')=='compatible':
        from bol_providers import chat_api
        result=chat_api(payload,settings)
    else:
        if not settings.get('api_key'):raise ValueError('Add a Sarvam API key or configure a writing provider first.')
        request=urllib.request.Request('https://api.sarvam.ai/v1/chat/completions',data=json.dumps(payload).encode(),headers={'api-subscription-key':settings['api_key'],'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=60) as response:result=json.load(response)
        except urllib.error.HTTPError as error:raise RuntimeError(f'Style suggestion returned HTTP {error.code}. Check writing-model access and credits.') from None
    try:
        content=result['choices'][0]['message']['content'].strip()
        if content.startswith('```'):content='\n'.join(content.splitlines()[1:-1])
        plan=json.loads(content)
        voice=plan['voice'];pace=float(plan['pace']);temperature=float(plan['temperature'])
        if voice not in TTS_VOICES or not math.isfinite(pace) or not math.isfinite(temperature) or not .5<=pace<=2 or not .01<=temperature<=1:raise ValueError()
        return {'voice':voice,'pace':pace,'temperature':temperature}
    except (ValueError,KeyError,TypeError,IndexError,AttributeError):
        raise RuntimeError('The writing model returned invalid style settings. Try a preset or simpler instructions.') from None
