from django.shortcuts import render
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
    from apps.programs.models import AdmissionPlan

    all_subjects = Subject.objects.all().order_by('name')

    # 4 слота: предмет + балл
    slots = []
    for i in range(1, 5):
        sid = request.GET.get(f's{i}', '')
        raw_score = request.GET.get(f'score{i}', '')
        try:
            sid = int(sid)
        except (ValueError, TypeError):
            sid = None
        try:
            score = max(0, min(100, int(raw_score)))
        except (ValueError, TypeError):
            score = 0
        slots.append({'sid': sid, 'score': score, 'raw_score': raw_score})

    selected_ids = [s['sid'] for s in slots if s['sid']]
    study_form = request.GET.get('study_form', '')
    searched = bool(selected_ids or study_form)
    total_score = sum(s['score'] for s in slots if s['sid'])

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
        if selected_ids and total_score > 0:
            latest_min_score = AdmissionPlan.objects.filter(
                program=OuterRef('pk')
            ).order_by('-year').values('min_score')[:1]
            ege_programs = (
                ege_programs
                .annotate(latest_min_score=Subquery(latest_min_score))
                .filter(latest_min_score__lte=total_score)
            )
        ege_programs = ege_programs.order_by('university__name', 'name')

    n = len(selected_ids)
    score_min = (40 + 39 * (n - 1)) if n > 0 else 0
    score_max = 100 * n if n > 0 else 0

    return render(request, 'core/home.html', {
        'deadlines':          AdmissionDeadline.objects.all()[:6],
        'faq':                FAQ.objects.filter(section='home'),
        'all_subjects':       all_subjects,
        'slots':              slots,
        'selected_ids':       selected_ids,
        'study_form':         study_form,
        'searched':           searched,
        'ege_programs':       ege_programs,
        'total_score':        total_score,
        'study_form_choices': Program.STUDY_FORM_CHOICES,
        'score_min':          score_min,
        'score_max':          score_max,
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


