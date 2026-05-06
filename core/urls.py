from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Pages
    path('', views.index, name='index'),
    path('translator/', views.translator, name='translator'),
    path('history/', views.history, name='history'),
    path('about/', views.about, name='about'),

    # Authentication
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # API Endpoints
    path('api/translate/', views.api_translate, name='api_translate'),
    path('api/audio/', views.api_audio_upload, name='api_audio'),
    path('api/feedback/', views.api_feedback, name='api_feedback'),
    path('api/delete-session/<int:session_id>/', views.api_delete_session, name='api_delete_session'),
    path('api/signs/', views.api_sigml_list, name='api_signs'),
    path('api/stats/', views.api_stats, name='api_stats'),

    # Legacy compatibility (for old JS handler.js calling /parser)
    path('parser', views.api_translate, name='legacy_parser'),
]
