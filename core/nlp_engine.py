"""
IntelliSign NLP Engine
======================
Handles:
  - Context detection (medical, educational, casual, emergency, legal)
  - Emotion recognition (neutral, happy, sad, urgent, questioning, angry)
  - ISL grammar-aware transformation (English → ISL word order)
  - Lemmatization and stop-word removal
  - Fallback to letter-by-letter spelling when word not found
"""

import re
import time
from typing import Tuple, List, Dict, Optional
from django.apps import apps


# ─────────────────────────────────────────────────────────────────────────────
# Context Detection
# ─────────────────────────────────────────────────────────────────────────────

CONTEXT_KEYWORDS: Dict[str, List[str]] = {
    'medical': [
        'doctor', 'hospital', 'medicine', 'pain', 'sick', 'fever', 'nurse',
        'clinic', 'injection', 'blood', 'heart', 'ambulance', 'emergency',
        'surgery', 'diagnosis', 'treatment', 'patient', 'prescription',
        'pharmacy', 'allergy', 'symptom', 'disease', 'infection', 'wound',
        'health', 'checkup', 'operation', 'tablet', 'pill', 'dose',
        'appointment', 'bandage', 'audiologist', 'hearing', 'deaf',
    ],
    'educational': [
        'school', 'college', 'university', 'teacher', 'student', 'class',
        'exam', 'learn', 'study', 'homework', 'book', 'lesson', 'education',
        'subject', 'science', 'math', 'english', 'library', 'assignment',
        'lecture', 'grade', 'certificate', 'research', 'knowledge',
        'laboratory', 'classroom', 'principal', 'blackboard', 'pen',
        'lecture', 'professor', 'degree', 'scholarship', 'teach',
    ],
    'emergency': [
        'help', 'danger', 'fire', 'accident', 'police', 'urgent', 'stop',
        'run', 'escape', 'save', 'attack', 'crash', 'flood', 'quickly',
        'now', 'immediately', 'alert', 'warning', 'critical', 'serious',
        'help-me', 'help-you', 'ambulance', 'rescue', 'police-station',
    ],
    'legal': [
        'law', 'court', 'judge', 'police', 'crime', 'arrest', 'rights',
        'complaint', 'case', 'advocate', 'bail', 'offense', 'penalty',
        'legal', 'justice', 'lawyer', 'evidence', 'witness', 'accuse',
        'prison', 'jail', 'lawsuit', 'verdict', 'attorney',
    ],
    'casual': [
        'hello', 'hi', 'bye', 'good', 'thanks', 'please', 'sorry',
        'happy', 'friend', 'play', 'fun', 'food', 'home', 'family',
        'enjoy', 'love', 'like', 'want', 'have', 'today', 'tomorrow',
        'how-are-you', 'nice-to-meet-you', 'weekend', 'party', 'dinner',
    ],
}


def detect_context(text: str) -> Tuple[str, float]:
    """
    Detect the domain/context of the input text.
    Uses database keywords if available, else falls back to defaults.
    """
    text_lower = text.lower()
    words = re.findall(r'\b\w+\b', text_lower)

    db_keywords: Optional[Dict[str, List[Tuple[str, float]]]] = None
    try:
        ContextKeyword = apps.get_model('core', 'ContextKeyword')
        db_keywords = {}
        for dk in ContextKeyword.objects.all():
            if dk.context not in db_keywords:
                db_keywords[dk.context] = []
            db_keywords[dk.context].append((dk.keyword, dk.weight))
    except (ImportError, LookupError, Exception):
        pass

    scores: Dict[str, float] = {ctx: 0.0 for ctx in CONTEXT_KEYWORDS}

    for word in words:
        # Check DB keywords
        if db_keywords:
            for ctx, keywords in db_keywords.items():
                for kw, weight in keywords:
                    if word == kw:
                        scores[ctx] += weight

        # Check hardcoded fallbacks
        for ctx, keywords in CONTEXT_KEYWORDS.items():
            if word in keywords:
                # Give slight bonus to hardcoded keywords if not in DB
                scores[ctx] += 1.0

    best_ctx = max(scores, key=lambda k: scores[k])
    total = sum(scores.values())

    if total == 0:
        return ('general', 0.5)

    confidence = scores[best_ctx] / total
    if scores[best_ctx] == 0:
        return ('general', 0.5)

    return (str(best_ctx), round(float(confidence), 2))


# ─────────────────────────────────────────────────────────────────────────────
# Emotion Recognition
# ─────────────────────────────────────────────────────────────────────────────

EMOTION_PATTERNS = {
    'urgent': [
        r'\b(help|urgent|emergency|quickly|now|immediately|hurry|danger|fire|stop)\b',
        r'[!]{2,}',
        r'\b(please|asap|critical|serious)\b',
        r'\b(fast|now|run|quick)\b',
    ],
    'questioning': [
        r'\?',
        r'\b(what|where|when|why|who|how|which|whose)\b',
        r'\b(is|are|can|do|did|will)\b.*\?',
    ],
    'happy': [
        r'\b(happy|great|wonderful|amazing|excellent|good|love|enjoy|fantastic|yay|celebrate)\b',
        r'\b(congratulations|perfect|cool|awesome)\b',
    ],
    'sad': [
        r'\b(sad|cry|sorry|unfortunate|pain|hurt|miss|lonely|depressed|unhappy)\b',
        r'\b(bad|terrible|horrible|pity|shame)\b',
    ],
    'angry': [
        r'\b(angry|hate|furious|terrible|awful|wrong|bad|horrible|upset)\b',
        r'[A-Z]{3,}',  # ALL CAPS words suggest anger
        r'\b(no|never|stop|stupid|idiot)\b',
    ],
    'fearful': [
        r'\b(scared|afraid|fear|worried|anxious|nervous|panic|danger)\b',
        r'\b(scary|frightened|terrified)\b',
    ],
    'casual': [
        r'\b(hello|hi|hey|thanks|thank you|please|welcome|nice|cool|okay|ok|fine)\b',
        r'\b(bye|see you|take care)\b',
    ],
}


def detect_emotion(text: str) -> Tuple[str, float]:
    """
    Detect the emotional tone of the text.
    Returns (emotion_label, confidence_score).
    """
    scores: Dict[str, float] = {em: 0.0 for em in EMOTION_PATTERNS}
    text_lower = text.lower()

    for emotion, patterns in EMOTION_PATTERNS.items():
        for pattern in patterns:
            # Special case: ALL CAPS patterns should NOT use IGNORECASE
            if '[A-Z]' in pattern:
                matches = re.findall(pattern, text)
            else:
                matches = re.findall(pattern, text_lower)
            scores[emotion] += len(matches)

    # Find best emotion
    best_em = max(scores, key=lambda k: scores[k])
    total = sum(scores.values())

    # Default to neutral if no distinct patterns found
    if total == 0 or scores[best_em] == 0:
        return ('neutral', 0.8)

    confidence = min(scores[best_em] / max(total, 1.0), 1.0)
    return (str(best_em), round(float(confidence), 2))


# ─────────────────────────────────────────────────────────────────────────────
# ISL Grammar Transformer
# ─────────────────────────────────────────────────────────────────────────────

# ISL follows a Topic-Comment structure, similar to SOV (Subject-Object-Verb).

STOPWORDS_ISL = {
    'a', 'an', 'the', 'is', 'am', 'was', 'were',
    'be', 'been', 'being', 'do', 'does', 'did', 'have',
    'has', 'had', 'will', 'would', 'could', 'should',
    'may', 'might', 'shall', 'of', 'at', 'by', 'for',
    'with', 'about', 'against', 'between', 'into', 'through',
    'during', 'before', 'after', 'above', 'below', 'to',
    'from', 'up', 'down', 'in', 'out', 'on', 'off',
    'over', 'under', 'again', 'then', 'once',
}

TIME_WORDS = {
    'today', 'tomorrow', 'yesterday', 'now', 'morning',
    'afternoon', 'evening', 'night', 'monday', 'tuesday',
    'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
    'everyday', 'always', 'never', 'often', 'soon', 'later',
}

QUESTION_WORDS = {'what', 'where', 'when', 'why', 'who', 'how', 'which', 'whose'}


def simple_lemmatize(word: str) -> str:
    """
    Basic rule-based lemmatizer for common English inflections.
    Used as fallback when NLTK is not available.
    """
    word = word.lower()
    irregulars = {
        'am': 'be', 'is': 'be', 'was': 'be', 'were': 'be',
        'went': 'go', 'gone': 'go', 'seen': 'see', 'saw': 'see',
        'ran': 'run', 'run': 'run', 'eaten': 'eat', 'ate': 'eat',
        'taught': 'teach', 'bought': 'buy', 'brought': 'bring',
        'wrote': 'write', 'written': 'write', 'spoken': 'speak',
        'spoke': 'speak', 'known': 'know', 'knew': 'know',
        'children': 'child', 'men': 'man', 'women': 'woman',
        'teeth': 'tooth', 'feet': 'foot', 'leaves': 'leaf',
    }
    if word in irregulars:
        return irregulars[word]

    # Common suffixes
    if word.endswith('ing') and len(word) > 5:
        stem = word[:-3]
        # Rule: if stem ends in double consonant (e.g., 'runn'), drop one
        if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in 'aeiou':
            return stem[:-1]
        return stem
    if word.endswith('ed') and len(word) > 4:
        stem = word[:-2]
        if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in 'aeiou':
            return stem[:-1]
        return stem
    if word.endswith('es') and len(word) > 3:
        if word.endswith('ies'):
            return word[:-3] + 'y'
        return word[:-1]
    if word.endswith('s') and len(word) > 3 and not word.endswith('ss'):
        return word[:-1]
    return word


def transform_to_isl(tokens: List[str]) -> List[str]:
    """
    Apply advanced ISL grammatical transformation:
      - TIME words move to the Absolute Front (e.g., "Tomorrow I go").
      - SUBJECT moves to the start (after TIME).
      - OBJECT moves to the middle.
      - VERB moves to the end (SOV).
      - QUESTION words move to the Absolute End.
      - NEGATION (no, not) moves after the verb.
    """
    if not tokens: return []
    
    time_tokens = [t for t in tokens if t in TIME_WORDS]
    question_tokens = [t for t in tokens if t in QUESTION_WORDS]
    negation_words = {'no', 'not', 'never', 'don\'t', 'cannot'}
    negation_tokens = [t for t in tokens if t in negation_words]
    
    # Remaining core words
    others = [
        t for t in tokens 
        if t not in TIME_WORDS and t not in QUESTION_WORDS and t not in negation_words
    ]
    
    # Simple Heuristic for SOV:
    # If we have 3 words left, assume Subject-Object-Verb
    # E.g., "I eat apple" -> "I apple eat"
    if len(others) >= 3:
        # Subject-Object-Verb
        subj = others[0]
        vrb = others[-1]
        objs = [others[i] for i in range(1, len(others)-1)]
        sov_ordered = [subj] + objs + [vrb]
    else:
        sov_ordered = others

    return time_tokens + sov_ordered + negation_tokens + question_tokens


def preprocess_text(text: str) -> List[str]:
    """Full NLP pipeline."""
    # Tokenize
    words = re.findall(r"\b[a-zA-Z']+\b", text)
    # Lowercase and clean
    words = [w.lower().strip("'") for w in words]
    # Lemmatize
    lemmatized = [simple_lemmatize(w) for w in words]
    # Remove stop words
    filtered = [w for w in lemmatized if w not in STOPWORDS_ISL and len(w) > 0]
    # ISL grammar transformation
    return transform_to_isl(filtered)


def translate(text: str) -> Dict:
    """Full IntelliSign translation pipeline."""
    start = time.time()
    text = text.strip()
    if not text:
        return {
            'raw_input': '', 'isl_tokens': [], 'isl_string': '', 'context': 'general',
            'context_confidence': 0.0, 'emotion': 'neutral', 'emotion_confidence': 0.0,
            'processing_ms': 0, 'confidence': 0.0,
        }

    context, ctx_conf = detect_context(text)
    emotion, em_conf = detect_emotion(text)
    isl_tokens = preprocess_text(text)
    isl_string = ' '.join(isl_tokens).lower()
    
    elapsed_ms = int((time.time() - start) * 1000)
    overall_confidence = round(float((ctx_conf + em_conf) / 2), 2)

    return {
        'raw_input': text,
        'isl_tokens': isl_tokens,
        'isl_string': isl_string,
        'context': context,
        'context_confidence': ctx_conf,
        'emotion': emotion,
        'emotion_confidence': em_conf,
        'processing_ms': elapsed_ms,
        'confidence': overall_confidence,
    }


def resolve_sigml_sequence(isl_tokens: List[str], available_signs: List[str]) -> List[Dict]:
    """Map ISL tokens to available .mp4 files."""
    # Create a mapping of lowercase word (without .mp4) to actual filename
    # We strip .mp4 and any suffixes like .AUS or _1 to get the base word
    available_mapping = {}
    for filename in available_signs:
        name_stem = filename.lower().replace('.mp4', '').split('.')[0].split('_')[0]
        available_mapping[name_stem] = filename
        # Also map the full stem just in case
        stem_full = filename.lower().replace('.mp4', '')
        if stem_full not in available_mapping:
            available_mapping[stem_full] = filename

    sequence = []
    for token in isl_tokens:
        token_clean = token.lower().strip('.,!?')
        # Check if the word exists as a sign
        if token_clean in available_mapping:
            sequence.append({
                'word': token_clean,
                'file': f"{available_mapping[token_clean]}",  # Return just filename
                'type': 'word'
            })
        else:
            for letter in token_clean:
                letter_upper = letter.upper()
                sequence.append({
                    'word': letter,
                    'file': f"{letter_upper}.mp4",  # Return just filename
                    'type': 'letter'
                })
    return sequence


def adjust_keywords_from_feedback(text: str, context: str, rating: int):
    """Adaptive Learning: Adjust context keyword weights based on user feedback."""
    if rating < 4: return
    words = re.findall(r'\b\w+\b', text.lower())
    if not words: return
    try:
        ContextKeyword = apps.get_model('core', 'ContextKeyword')
        from django.db.models import F
        for word in words:
            if len(word) < 4 or word in STOPWORDS_ISL: continue
            obj, created = ContextKeyword.objects.get_or_create(
                keyword=word,
                defaults={'context': context, 'weight': 1.0}
            )
            if not created and obj.context == context:
                obj.weight = F('weight') + 0.1
                obj.save()
    except Exception as e:
        print(f"Adaptive learning error: {e}")
