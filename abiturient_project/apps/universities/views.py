from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Sum, Min
from .models import University
from apps.programs.models import Program


def university_list(request):
    from django.db.models import F
    universities = University.objects.all()
    query = request.GET.get('q', '').strip()
    sort  = request.GET.get('sort', '').strip()

    if query:
        universities = universities.filter(
            Q(name__icontains=query) | Q(city__icontains=query)
        )

    sort_map = {
        'h_index': 'h_index',
        'cited':   'cited_by_count',
        'works':   'works_count',
    }
    if sort in sort_map:
        # Вузы с данными — первые, без данных — в конце
        universities = universities.order_by(F(sort_map[sort]).desc(nulls_last=True))
    else:
        universities = universities.order_by('name')

    return render(request, 'universities/list.html', {
        'universities': universities,
        'query': query,
        'sort': sort,
    })


def university_detail(request, pk):
    university = get_object_or_404(University, pk=pk)

    programs = university.programs.prefetch_related('subjects').all()

    profile = request.GET.get('profile', '')
    degree = request.GET.get('degree', '')
    study_form = request.GET.get('study_form', '')
    q = request.GET.get('q', '').strip()

    if q:
        programs = programs.filter(name__icontains=q)
    if profile:
        programs = programs.filter(profile=profile)
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
        'profile': profile,
        'degree': degree,
        'study_form': study_form,
        'q': q,
        'profiles': Program.PROFILE_CHOICES,
        'stats': stats,
        'programs_count': all_programs.count(),
        'deadlines': deadlines,
    })
