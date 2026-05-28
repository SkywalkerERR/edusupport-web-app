from django.urls import path
from . import views

app_name = 'programs'

urlpatterns = [
    path('', views.program_list, name='list'),
    path('<int:pk>/', views.program_detail, name='detail'),
    path('calculator/', views.calculator, name='calculator'),
    path('compare/', views.compare, name='compare'),
    path('compare/toggle/', views.compare_toggle, name='compare_toggle'),
    path('compare/clear/', views.compare_clear, name='compare_clear'),
]