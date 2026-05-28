from django.contrib import admin
from .models import Program, Subject, ProgramSubject, AdmissionPlan


# 🔹 Inline для предметов программы
class ProgramSubjectInline(admin.TabularInline):
    model = ProgramSubject
    extra = 1


@admin.register(AdmissionPlan)
class AdmissionPlanAdmin(admin.ModelAdmin):
    list_display = ('program', 'year', 'min_score', 'budget_places')
    list_filter = ('year', 'program__university')
    search_fields = ('program__name',)

# 🔹 Inline для планов приёма
class AdmissionPlanInline(admin.TabularInline):
    model = AdmissionPlan
    extra = 1


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'faculty', 'university')
    list_filter = ('profile', 'university')
    search_fields = ('name', 'code')

    # 🔥 вот это главное
    inlines = [AdmissionPlanInline, ProgramSubjectInline]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name',)