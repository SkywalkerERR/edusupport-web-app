from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('guide/', views.guide, name='guide'),
    path('ai/', views.ai_chat_page, name='ai_chat_page'),
    path('ai/chat/', views.ai_chat, name='ai_chat'),
]