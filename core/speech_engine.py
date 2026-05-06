"""
Speech Processing Module for IntelliSign
=========================================
Handles audio file transcription using multiple backends (Whisper, Google, Sphinx).
Supports: MP3, WAV, OGG, FLAC, M4A, WEBM formats.
"""

import os
import tempfile
import time
from typing import Tuple, Dict, Any, Optional

# Module-level cache for Whisper model to avoid reloading on every request
WHISPER_CACHE: Dict[str, Any] = {
    'model': None,
    'model_name': None,
}

def transcribe_audio(file_path: str) -> Tuple[str, float]:
    """
    Transcribe an audio file to text.
    Returns (transcript_text, confidence_score).
    """
    try:
        import speech_recognition as sr
    except ImportError as e:
        return (f"Speech recognition library error: {str(e)}", 0.0)

    recognizer = sr.Recognizer()
    
    # Pre-process for non-WAV
    wav_path = file_path
    converted = False
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext not in ('.wav',):
        try:
            from pydub import AudioSegment
            audio_map = {'.mp3': 'mp3', '.ogg': 'ogg', '.flac': 'flac', '.m4a': 'mp4', '.webm': 'webm', '.mpeg': 'mp3'}
            fmt = audio_map.get(ext, 'mp3')
            audio = AudioSegment.from_file(file_path, format=fmt)
            
            # Secure way to get a closed temp file path on Windows
            fd, path = tempfile.mkstemp(suffix='.wav')
            os.close(fd)
            
            audio.export(path, format='wav')
            wav_path = path
            converted = True
        except Exception as e:
            return (f"Audio conversion failed: {str(e)}", 0.0)

    try:
        # 1. Try OpenAI Whisper (High Accuracy, Offline)
        try:
            import whisper
            import torch
            global WHISPER_CACHE
            model_name = "base" 
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
            if WHISPER_CACHE['model_name'] != model_name or WHISPER_CACHE['model'] is None:
                WHISPER_CACHE['model'] = whisper.load_model(model_name, device=device)
                WHISPER_CACHE['model_name'] = model_name
                
            result = WHISPER_CACHE['model'].transcribe(wav_path)
            if result and result.get('text'):
                return (result['text'].strip(), 0.95)
        except (ImportError, Exception):
            # Gracefully ignore whisper if missing or failing
            pass

        # Fallback to SpeechRecognition backends
        try:
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
            
            # 2. Try Google Speech API (Online)
            try:
                text = recognizer.recognize_google(audio_data, language='en-IN')
                return (text, 0.90)
            except:
                pass
                
            # 3. Try CMU Sphinx (Offline)
            try:
                text = recognizer.recognize_sphinx(audio_data)
                return (text, 0.60)
            except:
                pass
                
        except Exception as e:
            return (f"Audio processing error: {str(e)}", 0.0)

        return ("Transcription failed.", 0.0)
    finally:
        # Always clean up converted file
        if converted and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except:
                pass # Silent fail on cleanup to avoid crashing response

def get_supported_formats() -> list:
    return ['.wav', '.mp3', '.ogg', '.flac', '.m4a', '.webm', '.mpeg']

def save_uploaded_audio(uploaded_file) -> str:
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    tmp = tempfile.NamedTemporaryFile(suffix=ext, mode='wb', delete=False)
    for chunk in uploaded_file.chunks():
        tmp.write(chunk)
    tmp.close()
    return tmp.name
