"""
IntelliSign Django Views
=========================
Handles all HTTP routes for the IntelliSign application.
"""

import json
import os
import time
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

from .nlp_engine import translate, resolve_sigml_sequence, adjust_keywords_from_feedback
from .speech_engine import transcribe_audio, save_uploaded_audio, get_supported_formats
from .sign_manager import get_available_signs, get_sigml_json, get_sign_names_set
from .models import TranslationSession, FeedbackEntry


# ─────────────────────────────────────────────────────────────────────────────
# Main Pages
# ─────────────────────────────────────────────────────────────────────────────

def index(request):
    """Landing / Dashboard page."""
    stats = {
        'total_translations': TranslationSession.objects.count(),
        'total_signs': len(get_available_signs()),
        'recent': TranslationSession.objects.all()[:5],
    }
    return render(request, 'core/index.html', {'stats': stats})


def translator(request):
    """Main translator page with live speech and avatar."""
    return render(request, 'core/translator.html', {
        'supported_formats': ', '.join(get_supported_formats()),
    })


def history(request):
    """Translation history page."""
    if request.user.is_authenticated:
        sessions = TranslationSession.objects.filter(user=request.user)[:50]
    else:
        sessions = TranslationSession.objects.all()[:50]
    return render(request, 'core/history.html', {'sessions': sessions})


def about(request):
    """About IntelliSign page."""
    return render(request, 'core/about.html')


# ─────────────────────────────────────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────────────────────────────────────

def login_view(request):
    """Handle user login."""
    if request.user.is_authenticated:
        return redirect('core:translator')
        
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            return redirect('core:translator')
        else:
            return render(request, 'core/login.html', {'error': 'Invalid username or password.'})
    
    return render(request, 'core/login.html')

def register_view(request):
    """Handle new user registration."""
    if request.user.is_authenticated:
        return redirect('core:translator')
        
    if request.method == 'POST':
        u = request.POST.get('username')
        e = request.POST.get('email', '')
        p = request.POST.get('password')
        
        if User.objects.filter(username=u).exists():
            return render(request, 'core/register.html', {'error': 'Username already exists.'})
            
        user = User.objects.create_user(username=u, email=e, password=p)
        login(request, user)
        return redirect('core:translator')
        
    return render(request, 'core/register.html')

def logout_view(request):
    """Handle user logout."""
    logout(request)
    return redirect('core:index')


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@csrf_exempt
@require_http_methods(["POST", "GET"])
def api_translate(request):
    """
    Translate text to ISL.
    GET:  ?text=<input>
    POST: JSON body {"text": "<input>"}
    """
    if request.method == 'GET':
        text = request.GET.get('text', '') or request.GET.get('speech', '')
    else:
        try:
            body = json.loads(request.body)
            text = body.get('text', '')
        except Exception:
            text = request.POST.get('text', '')

    if not text:
        return JsonResponse({'error': 'No text provided'}, status=400)

    # Run NLP pipeline
    result = translate(text)

    # Resolve sign files
    available = get_available_signs()
    sequence = resolve_sigml_sequence(result['isl_tokens'], available)

    # Build pre_process_string (comma-separated sigml paths for legacy player)
    pre_process_string = ' '.join(
        item['file'].split('/')[-1].replace('.sigml', '')
        for item in sequence
    )

    # Save to DB
    sigml_names = ','.join(item['file'] for item in sequence)
    session = TranslationSession.objects.create(
        user=request.user if request.user.is_authenticated else None,
        raw_input=result['raw_input'],
        detected_context=result['context'],
        detected_emotion=result['emotion'],
        isl_tokens=result['isl_string'],
        sigml_sequence=sigml_names,
        input_type='text',
        confidence_score=result['confidence'],
        processing_time_ms=result['processing_ms'],
    )

    return JsonResponse({
        'session_id': session.id,
        'raw_input': result['raw_input'],
        'isl_string': result['isl_string'],
        'isl_tokens': result['isl_tokens'],
        'context': result['context'],
        'context_confidence': result['context_confidence'],
        'emotion': result['emotion'],
        'emotion_confidence': result['emotion_confidence'],
        'confidence': result['confidence'],
        'processing_ms': result['processing_ms'],
        'sign_sequence': sequence,
        'pre_process_string': pre_process_string,
        # Legacy compatibility key
        'isl_text_string': result['isl_string'],
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_audio_upload(request):
    """
    Upload an audio file for transcription and translation.
    Returns full translation result.
    """
    if 'audio' not in request.FILES:
        return JsonResponse({'error': 'No audio file uploaded'}, status=400)

    uploaded = request.FILES['audio']
    ext = os.path.splitext(uploaded.name)[1].lower()

    if ext not in get_supported_formats():
        return JsonResponse({
            'error': f'Unsupported format. Supported: {", ".join(get_supported_formats())}'
        }, status=400)

    # Save and transcribe
    tmp_path = save_uploaded_audio(uploaded)
    try:
        transcript, speech_confidence = transcribe_audio(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not transcript or speech_confidence == 0.0:
        return JsonResponse({
            'error': transcript or 'Transcription failed',
            'transcript': '',
        }, status=422)

    # Translate
    result = translate(transcript)
    available = get_available_signs()
    sequence = resolve_sigml_sequence(result['isl_tokens'], available)

    # Save session
    sigml_names = ','.join(item['file'] for item in sequence)
    session = TranslationSession.objects.create(
        user=request.user if request.user.is_authenticated else None,
        raw_input=result['raw_input'],
        detected_context=result['context'],
        detected_emotion=result['emotion'],
        isl_tokens=result['isl_string'],
        sigml_sequence=sigml_names,
        input_type='audio_file',
        confidence_score=result['confidence'],
        processing_time_ms=result['processing_ms'],
    )

    return JsonResponse({
        'session_id': session.id,
        'transcript': transcript,
        'speech_confidence': speech_confidence,
        'raw_input': result['raw_input'],
        'isl_string': result['isl_string'],
        'isl_tokens': result['isl_tokens'],
        'context': result['context'],
        'context_confidence': result['context_confidence'],
        'emotion': result['emotion'],
        'emotion_confidence': result['emotion_confidence'],
        'confidence': result['confidence'],
        'processing_ms': result['processing_ms'],
        'sign_sequence': sequence,
        'isl_text_string': result['isl_string'],
    })


@csrf_exempt
@require_http_methods(["POST"])
def api_feedback(request):
    """Submit user feedback for a translation session."""
    try:
        body = json.loads(request.body)
    except Exception:
        body = {}

    session_id = body.get('session_id')
    rating = body.get('rating', 3)
    correction = body.get('correction', '')
    comment = body.get('comment', '')

    if not session_id:
        return JsonResponse({'error': 'session_id required'}, status=400)

    try:
        session = TranslationSession.objects.get(id=session_id)
        
        # Ensure rating is an integer
        try:
            rating_val = int(rating)
        except (ValueError, TypeError):
            rating_val = 3

        feedback, created = FeedbackEntry.objects.update_or_create(
            session=session,
            defaults={'rating': rating_val, 'correction': correction, 'comment': comment}
        )

        # Trigger adaptive learning
        try:
            adjust_keywords_from_feedback(
                session.raw_input, 
                session.detected_context, 
                rating_val
            )
        except Exception as e:
            print(f"Adaptive learning error: {e}")

        return JsonResponse({
            'status': 'saved',
            'feedback_id': feedback.id,
            'created': created,
        })
    except TranslationSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["DELETE", "POST"])
def api_delete_session(request, session_id):
    """Delete a translation session from history."""
    try:
        session = get_object_or_404(TranslationSession, id=session_id)
        
        # Ownership check: If authenticated, only delete your own. 
        # If not authenticated, allow deletion if they have access to the page 
        # (assuming public history for anonymous users based on current index view).
        if request.user.is_authenticated and session.user and session.user != request.user:
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        session.delete()
        return JsonResponse({
            'status': 'success',
            'message': 'Session deleted successfully',
            'session_id': session_id
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_http_methods(["GET"])
def api_sigml_list(request):
    """Return the full sigml file list for the avatar player (legacy compat)."""
    return JsonResponse(get_sigml_json(), safe=False)


@require_http_methods(["GET"])
def api_stats(request):
    """Return system statistics."""
    from django.db.models import Avg, Count

    stats = TranslationSession.objects.aggregate(
        total=Count('id'),
        avg_confidence=Avg('confidence_score'),
        avg_time=Avg('processing_time_ms'),
    )

    context_dist = {}
    for item in TranslationSession.objects.values('detected_context').annotate(count=Count('id')):
        context_dist[item['detected_context']] = item['count']

    emotion_dist = {}
    for item in TranslationSession.objects.values('detected_emotion').annotate(count=Count('id')):
        emotion_dist[item['detected_emotion']] = item['count']

    return JsonResponse({
        'total_translations': stats['total'] or 0,
        'avg_confidence': round(stats['avg_confidence'] or 0, 2),
        'avg_processing_ms': round(stats['avg_time'] or 0, 1),
        'total_signs_available': len(get_available_signs()),
        'context_distribution': context_dist,
        'emotion_distribution': emotion_dist,
    })
