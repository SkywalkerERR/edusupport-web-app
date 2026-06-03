from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Count, Q
from .models import Program, Subject, Faculty
from .services import match_programs, get_chance


def program_list(request):
    from apps.universities.models import University

    programs = Program.objects.select_related('university').prefetch_related('program_subjects__subject', 'entrance_exams').order_by('id')

    query         = request.GET.get('q', '')
    degree        = request.GET.get('degree', '')
    study_form    = request.GET.get('study_form', '')
    university_id = request.GET.get('university', '')
    has_dormitory = request.GET.get('has_dormitory', '')
    has_military  = request.GET.get('has_military', '')
    faculty_id    = request.GET.get('faculty', '')

    if query:
        programs = programs.filter(name__icontains=query)
    if degree:
        programs = programs.filter(degree=degree)
    if study_form:
        programs = programs.filter(study_form=study_form)
    if university_id:
        programs = programs.filter(university__pk=university_id)
    if has_dormitory:
        programs = programs.filter(university__has_dormitory=True)
    if has_military:
        programs = programs.filter(university__has_military=True)
    if faculty_id:
        programs = programs.filter(direction__department__faculty__pk=faculty_id)

    favorite_ids = set()
    if request.user.is_authenticated:
        favorite_ids = set(
            request.user.favorites.values_list('program_id', flat=True)
        )

    universities = University.objects.all()

    paginator = Paginator(programs, 5)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'programs/list.html', {
        'programs':      page_obj,
        'page_obj':      page_obj,
        'query':         query,
        'degree':        degree,
        'study_form':    study_form,
        'university_id': university_id,
        'has_dormitory': has_dormitory,
        'has_military':  has_military,
        'faculty_id':    faculty_id,
        'faculties':     Faculty.objects.select_related('university').order_by('name'),
        'universities':  universities,
        'favorite_ids':  favorite_ids,
    })

def program_detail(request, pk):
    program = get_object_or_404(
        Program.objects.select_related('university')
                       .prefetch_related('program_subjects__subject'),
        pk=pk
    )
    all_ps = list(program.program_subjects.select_related('subject').order_by('subject__name'))
    required_subjects  = [ps for ps in all_ps if ps.is_required]
    elective_subjects  = [ps for ps in all_ps if not ps.is_required]

    # Шансы поступления если пользователь авторизован и ввёл баллы
    chance = None
    user_total = 0
    gap = 0
    is_favorite = False

    if request.user.is_authenticated:
        # Проверяем избранное
        is_favorite = request.user.favorites.filter(program=program).exists()

        # Считаем баллы по предметам программы
        score_map = {
            er.subject_id: er.score
            for er in request.user.exam_results.select_related('subject').all()
        }
        relevant_scores = [
            score_map[s.id]
            for s in program.subjects.all()
            if s.id in score_map
        ]
        if relevant_scores:
            user_total = sum(relevant_scores)
            chance = get_chance(user_total, program)
            gap = user_total - (program.min_score or 0)

    return render(request, 'programs/detail.html', {
        'program':            program,
        'chance':             chance,
        'user_total':         user_total,
        'gap':                gap,
        'is_favorite':        is_favorite,
        'required_subjects':  required_subjects,
        'elective_subjects':  elective_subjects,
    })


@require_POST
def compare_toggle(request):
    """Добавить / убрать программу из сравнения (хранится в сессии)."""
    program_id = int(request.POST.get('program_id', 0))
    compare = request.session.get('compare', [])
    if program_id in compare:
        compare.remove(program_id)
        status = 'removed'
    elif len(compare) < 3:
        compare.append(program_id)
        status = 'added'
    else:
        return JsonResponse({'status': 'limit', 'count': len(compare)})
    request.session['compare'] = compare
    return JsonResponse({'status': status, 'count': len(compare)})


def compare_clear(request):
    """Очистить список сравнения."""
    request.session['compare'] = []
    return redirect('programs:compare')


def compare(request):
    """Страница сравнения программ."""
    ids = request.session.get('compare', [])
    programs = (
        Program.objects
        .filter(pk__in=ids)
        .select_related('university', 'direction__faculty', 'direction__department__faculty')
        .prefetch_related(
            'program_subjects__subject',
            'entrance_exams',
        )
    )
    programs = sorted(programs, key=lambda p: ids.index(p.pk))

    # Предметы — разбиваем на обязательные и необязательные
    for p in programs:
        p.required_subjects_list  = [ps for ps in p.program_subjects.all() if ps.is_required]
        p.elective_subjects_list  = [ps for ps in p.program_subjects.all() if not ps.is_required]
        p.entrance_exams_list     = list(p.entrance_exams.all())

    # Предупреждение о разных уровнях подготовки
    degrees = {p.degree for p in programs}
    degree_mismatch = len(degrees) > 1

    # Шансы для авторизованного пользователя
    if request.user.is_authenticated:
        score_map = {
            er.subject_id: er.score
            for er in request.user.exam_results.all()
        }
        for p in programs:
            scores = [ps.subject_id for ps in p.program_subjects.all() if ps.subject_id in score_map]
            scores = [score_map[sid] for sid in scores]
            if scores:
                total = sum(scores)
                p.user_total = total
                p.user_chance = get_chance(total, p)
            else:
                p.user_total = None
                p.user_chance = None

    return render(request, 'programs/compare.html', {
        'programs':        programs,
        'degree_mismatch': degree_mismatch,
    })


@login_required
def calculator(request):
    from apps.universities.models import University

    programs = Program.objects.prefetch_related('subjects').select_related('university')
    matched = match_programs(request.user, programs)

    total_user_score = sum(
        er.score for er in request.user.exam_results.all()
    )

    # Фильтр по шансам
    chance_filter = request.GET.get('chance', 'all')
    if chance_filter == 'high':
        matched = [m for m in matched if m['chance'] and m['chance']['css'] in ('success', 'good')]
    elif chance_filter == 'possible':
        matched = [m for m in matched if m['chance'] and m['chance']['css'] != 'fail']

    # Фильтр по университету
    university_id = request.GET.get('university', '')
    if university_id:
        matched = [m for m in matched if str(m['program'].university.pk) == university_id]

    # Фильтр по проходному баллу
    min_score_filter = request.GET.get('min_score', '')
    max_score_filter = request.GET.get('max_score', '')
    if min_score_filter:
        matched = [m for m in matched if m['program'].min_score >= int(min_score_filter)]
    if max_score_filter:
        matched = [m for m in matched if m['program'].min_score <= int(max_score_filter)]

    # Фильтр по бюджетным местам
    min_budget = request.GET.get('min_budget', '')
    if min_budget:
        matched = [m for m in matched if m['program'].budget_places >= int(min_budget)]

    # Фильтр по общежитию и военной кафедре
    has_dormitory = request.GET.get('has_dormitory', '')
    has_military = request.GET.get('has_military', '')
    if has_dormitory:
        matched = [m for m in matched if m['program'].university.has_dormitory]
    if has_military:
        matched = [m for m in matched if m['program'].university.has_military]

    # Сортировка
    sort = request.GET.get('sort', 'chance')
    if sort == 'score':
        matched = sorted(matched, key=lambda m: m['user_total'], reverse=True)
    elif sort == 'cost':
        matched = sorted(matched, key=lambda m: m['program'].cost_per_year)
    elif sort == 'budget':
        matched = sorted(matched, key=lambda m: m['program'].budget_places, reverse=True)
    elif sort == 'min_score':
        matched = sorted(matched, key=lambda m: m['program'].min_score)
    else:
        matched = sorted(matched, key=lambda m: m['chance']['pct'] if m['chance'] else 0, reverse=True)

    universities = University.objects.all()

    return render(request, 'programs/calculator.html', {
        'matched':          matched,
        'chance_filter':    chance_filter,
        'sort':             sort,
        'total_user_score': total_user_score,
        'universities':     universities,
        'university_id':    university_id,
        'min_score_filter': min_score_filter,
        'max_score_filter': max_score_filter,
        'min_budget':       min_budget,
        'has_dormitory':    has_dormitory,
        'has_military':     has_military,
    })
