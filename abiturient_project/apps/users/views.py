import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import ExamResult, Favorite
from apps.programs.models import Subject, Program
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.username}! Аккаунт создан.')
            return redirect('users:profile')
    else:
        form = UserCreationForm()
    return render(request, 'users/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect(request.GET.get('next', 'users:profile'))
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.html', {'form': form})


@login_required
def profile(request):
    subjects = Subject.objects.all()
    exam_results = request.user.exam_results.select_related('subject').all()
    results = {er.subject_id: er.score for er in exam_results}

    if request.method == 'POST':
        for subject in subjects:
            score = request.POST.get(f'score_{subject.id}')
            if score and score.isdigit():
                score_int = int(score)
                if 0 <= score_int <= 100:
                    ExamResult.objects.update_or_create(
                        user=request.user, subject=subject,
                        defaults={'score': score_int}
                    )
            else:
                ExamResult.objects.filter(
                    user=request.user, subject=subject
                ).delete()
        messages.success(request, 'Баллы ЕГЭ успешно сохранены!')
        return redirect('users:profile')

    # Подсчёт статистики
    scores = list(results.values())
    total_score = sum(scores)
    avg_score = round(total_score / len(scores), 1) if scores else 0
    favorites_count = request.user.favorites.count()

    return render(request, 'users/profile.html', {
        'subjects': subjects,
        'results': results,
        'total_score': total_score,
        'avg_score': avg_score,
        'favorites_count': favorites_count,
    })

@login_required
@require_POST
def toggle_favorite(request):
    data = json.loads(request.body)
    program = get_object_or_404(Program, pk=data.get('program_id'))
    fav, created = Favorite.objects.get_or_create(user=request.user, program=program)
    if not created:
        fav.delete()
        return JsonResponse({'status': 'removed', 'message': 'Удалено из избранного'})
    return JsonResponse({'status': 'added', 'message': 'Добавлено в избранное'})

@login_required
def favorites(request):
    favs = request.user.favorites.select_related('program__university')
    return render(request, 'users/favorites.html', {'favorites': favs})