from django.contrib import admin
from .models import TranslationSession, FeedbackEntry, ContextKeyword


@admin.register(TranslationSession)
class TranslationSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'raw_input_short', 'input_type', 'detected_context',
                    'detected_emotion', 'confidence_score', 'processing_time_ms', 'created_at']
    list_filter = ['user', 'input_type', 'detected_context', 'detected_emotion']
    search_fields = ['user__username', 'raw_input', 'isl_tokens']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

    def raw_input_short(self, obj):
        return obj.raw_input[:40] + '...' if len(obj.raw_input) > 40 else obj.raw_input
    raw_input_short.short_description = 'Input'


@admin.register(FeedbackEntry)
class FeedbackEntryAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'rating', 'comment', 'submitted_at']
    list_filter = ['rating']
    search_fields = ['comment', 'correction']
    readonly_fields = ['submitted_at']


@admin.register(ContextKeyword)
class ContextKeywordAdmin(admin.ModelAdmin):
    list_display = ['keyword', 'context', 'weight']
    list_filter = ['context']
    search_fields = ['keyword']
