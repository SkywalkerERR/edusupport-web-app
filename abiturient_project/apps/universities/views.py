from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Sum, Min
from .models import University
from apps.programs.models import Program


def university_list(request):
    from django.db.models import F
    universities = University.objects.all()
    query         = request.GET.get('q', '').strip()
    sort          = request.GET.get('sort', '').strip()
    city_filter   = request.GET.get('city', '').strip()
    has_dormitory = request.GET.get('has_dormitory', '')
    has_military  = request.GET.get('has_military', '')

    if query:
        universities = universities.filter(
            Q(name__icontains=query) | Q(city__icontains=query)
        )
    if city_filter:
        universities = universities.filter(city__icontains=city_filter)
    if has_dormitory:
        universities = universities.filter(has_dormitory=True)
    if has_military:
        universities = universities.filter(has_military=True)

    sort_map = {
        'h_index': 'h_index',
        'cited':   'cited_by_count',
        'works':   'works_count',
    }
    if sort in sort_map:
        universities = universities.order_by(F(sort_map[sort]).desc(nulls_last=True))
    else:
        universities = universities.order_by('name')

    cities = University.objects.exclude(city='').values_list('city', flat=True).distinct().order_by('city')

    return render(request, 'universities/list.html', {
        'universities':  universities,
        'query':         query,
        'sort':          sort,
        'city_filter':   city_filter,
        'has_dormitory': has_dormitory,
        'has_military':  has_military,
        'cities':        cities,
    })


def university_detail(request, pk):
    university = get_object_or_404(University, pk=pk)

    programs = university.programs.prefetch_related('subjects').all()

    degree = request.GET.get('degree', '')
    study_form = request.GET.get('study_form', '')
    q = request.GET.get('q', '').strip()

    if q:
        programs = programs.filter(name__icontains=q)
    if degree:
        programs = programs.filter(degree=degree)
    if study_form:
        programs = programs.filter(study_form=study_form)

    all_programs = university.programs.all()
    stats = all_programs.aggregate(
        total_budget=Sum('admission_plans__budget_places'),
        total_paid=Sum('admission_plans__paid_places'),
        min_cost=Min('admission_plans__cost_per_year'),
    )

    deadlines = university.deadlines.all()

    return render(request, 'universities/detail.html', {
        'university': university,
        'programs': programs,
        'degree': degree,
        'study_form': study_form,
        'q': q,
        'stats': stats,
        'programs_count': all_programs.count(),
        'deadlines': deadlines,
    })
