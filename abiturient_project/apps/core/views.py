import json
import anthropic
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Count, Q, Subquery, OuterRef
from .models import (
    AdmissionStep, RequiredDocument,
    BudgetCategory, Benefit, FAQ
)
from apps.universities.models import AdmissionDeadline

RULES = [
    {'icon': 'buildings',          'title': 'Количество вузов',          'text': 'Можно одновременно подать документы в 5 вузов, в каждом — не более 5 направлений подготовки.'},
    {'icon': 'calculator',         'title': 'Конкурс по баллам',         'text': 'Зачисление проходит на конкурсной основе по сумме баллов ЕГЭ и индивидуальных достижений.'},
    {'icon': 'trophy',             'title': 'Индивидуальные достижения', 'text': 'За золотой значок ГТО, аттестат с отличием и победы в олимпиадах начисляются дополнительные баллы (до 10).'},
    {'icon': 'arrow-repeat',       'title': 'Волны зачисления',          'text': 'Зачисление проходит в две волны. В первой заполняется 80% мест, во второй — оставшиеся 20%.'},
    {'icon': 'file-earmark-check', 'title': 'Согласие на зачисление',   'text': 'Для зачисления необходимо подать оригинал документа об образовании и согласие на зачисление.'},
    {'icon': 'translate',          'title': 'Целевое обучение',          'text': 'Часть мест выделена для целевого приёма — поступление по договору с работодателем вне общего конкурса.'},
]


def home(request):
    from apps.programs.models import Program, Subject

    all_subjects = Subject.objects.all().order_by('name')

    # Собираем выбранные предметы (до 4 слотов)
    selected_ids = []
    for i in range(1, 5):
        val = request.GET.get(f's{i}', '')
        if val:
            try:
                selected_ids.append(int(val))
            except ValueError:
                pass

    study_form = request.GET.get('study_form', '')
    searched = bool(selected_ids or study_form)

    # Диапазон балла: min = 40 + 39*(n-1), max = 100*n
    n = len(selected_ids)
    score_min = (40 + 39 * (n - 1)) if n > 0 else 40
    score_max = 100 * n if n > 0 else 100

    score_val = request.GET.get('score', '')
    try:
        score_val = int(score_val)
        score_val = max(score_min, min(score_max, score_val))
    except (ValueError, TypeError):
        score_val = score_max

    ege_programs = None
    if searched:
        ege_programs = Program.objects.select_related('university').prefetch_related('subjects')
        if study_form:
            ege_programs = ege_programs.filter(study_form=study_form)
        if selected_ids:
            ege_programs = (
                ege_programs
                .annotate(
                    matched_count=Count(
                        'subjects',
                        filter=Q(subjects__id__in=selected_ids),
                        distinct=True
                    )
                )
                .filter(matched_count=len(selected_ids))
            )
        if n > 0:
            from apps.programs.models import AdmissionPlan
            latest_min_score = AdmissionPlan.objects.filter(
                program=OuterRef('pk')
            ).order_by('-year').values('min_score')[:1]
            ege_programs = (
                ege_programs
                .annotate(latest_min_score=Subquery(latest_min_score))
                .filter(latest_min_score__lte=score_val)
            )
        ege_programs = ege_programs.order_by('university__name', 'name')

    return render(request, 'core/home.html', {
        'deadlines':    AdmissionDeadline.objects.all()[:6],
        'faq':          FAQ.objects.filter(section='home'),
        'all_subjects': all_subjects,
        'selected_ids': selected_ids,
        'study_form':   study_form,
        'searched':     searched,
        'ege_programs': ege_programs,
        'score_min':    score_min,
        'score_max':    score_max,
        'score_val':    score_val,
        'subjects_count': n,
        's1': request.GET.get('s1', ''),
        's2': request.GET.get('s2', ''),
        's3': request.GET.get('s3', ''),
        's4': request.GET.get('s4', ''),
        'study_form_choices': Program.STUDY_FORM_CHOICES,
    })


def guide(request):
    return render(request, 'core/guide.html', {
        'steps': AdmissionStep.objects.all(),
        'required_docs': RequiredDocument.objects.filter(type='required'),
        'optional_docs': RequiredDocument.objects.filter(type='optional'),
        'deadlines': AdmissionDeadline.objects.all(),
        'rules': RULES,
        'budget_categories': BudgetCategory.objects.all(),
        'benefits': Benefit.objects.all(),
        'faq': FAQ.objects.filter(section='guide'),
    })


def ai_chat_page(request):
    return render(request, 'core/ai_chat.html')


@require_POST
def ai_chat(request):
    data = json.loads(request.body)
    user_message = data.get('message', '')
    history = data.get('history', [])

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=1000,
        system='Ты AI-ассистент для абитуриентов ЮУрГУ. Отвечай кратко и по делу на русском языке.',
        messages=history + [{'role': 'user', 'content': user_message}]
    )
    return JsonResponse({'reply': response.content[0].text})