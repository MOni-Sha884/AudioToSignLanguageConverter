from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class TranslationSession(models.Model):
    """Records each translation request with full context."""

    CONTEXT_CHOICES = [
        ('medical', 'Medical'),
        ('educational', 'Educational'),
        ('casual', 'Casual'),
        ('emergency', 'Emergency'),
        ('legal', 'Legal'),
        ('general', 'General'),
    ]

    EMOTION_CHOICES = [
        ('neutral', 'Neutral'),
        ('happy', 'Happy'),
        ('sad', 'Sad'),
        ('urgent', 'Urgent'),
        ('questioning', 'Questioning'),
        ('angry', 'Angry'),
        ('fearful', 'Fearful'),
    ]

    INPUT_TYPE_CHOICES = [
        ('speech', 'Live Speech'),
        ('audio_file', 'Audio File'),
        ('text', 'Text Input'),
    ]

    raw_input = models.TextField(help_text="Original spoken/typed text")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='translations')
    detected_context = models.CharField(max_length=20, choices=CONTEXT_CHOICES, default='general')
    detected_emotion = models.CharField(max_length=20, choices=EMOTION_CHOICES, default='neutral')
    isl_tokens = models.TextField(help_text="Comma-separated ISL tokens after grammar transformation")
    sigml_sequence = models.TextField(blank=True, help_text="Ordered list of .sigml filenames")
    input_type = models.CharField(max_length=20, choices=INPUT_TYPE_CHOICES, default='speech')
    confidence_score = models.FloatField(default=0.0, help_text="Translation confidence 0-1")
    processing_time_ms = models.IntegerField(default=0, help_text="Time taken in milliseconds")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Translation Session'
        verbose_name_plural = 'Translation Sessions'

    def __str__(self):
        return f"[{self.input_type}] {self.raw_input[:50]} @ {self.created_at:%Y-%m-%d %H:%M}"


class FeedbackEntry(models.Model):
    """User feedback for adaptive learning."""

    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    session = models.OneToOneField(TranslationSession, on_delete=models.CASCADE, related_name='feedback')
    rating = models.IntegerField(choices=RATING_CHOICES, help_text="1 (poor) to 5 (excellent)")
    correction = models.TextField(blank=True, help_text="User's corrected ISL output")
    comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Feedback Entry'
        verbose_name_plural = 'Feedback Entries'

    def __str__(self):
        return f"Rating {self.rating}/5 for session {self.session_id}"


class ContextKeyword(models.Model):
    """Context detection keyword mapping."""
    keyword = models.CharField(max_length=100, unique=True)
    context = models.CharField(max_length=20)
    weight = models.FloatField(default=1.0)

    class Meta:
        verbose_name = 'Context Keyword'

    def __str__(self):
        return f"{self.keyword} → {self.context}"
