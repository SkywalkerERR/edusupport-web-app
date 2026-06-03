from django.contrib import admin
from .models import (
    Program, Subject, ProgramSubject, AdmissionPlan,
    Faculty, Department, Direction, EntranceExam,
)


class DepartmentInline(admin.TabularInline):
    model = Department
    extra = 1


class DirectionInline(admin.TabularInline):
    model = Direction
    extra = 1


class ProgramSubjectInline(admin.TabularInline):
    model = ProgramSubject
    extra = 0


class EntranceExamInline(admin.TabularInline):
    model = EntranceExam
    extra = 1
    fields = ('name', 'min_score', 'description')


class AdmissionPlanInline(admin.TabularInline):
    model = AdmissionPlan
    extra = 1
    fields = (
        'year', 'min_score',
        'passing_score_budget', 'passing_score_paid',
        'budget_places', 'paid_places', 'cost_per_year',
    )


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'type', 'university')
    list_filter  = ('type', 'university')
    search_fields = ('name', 'short_name')
    inlines = [DepartmentInline]


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display  = ('name', 'faculty')
    list_filter   = ('faculty__university', 'faculty')
    search_fields = ('name',)
    inlines = [DirectionInline]


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display  = ('code', 'name', 'faculty', 'department')
    list_filter   = ('faculty__university', 'department__faculty__university')
    search_fields = ('name', 'code')
    fields        = ('faculty', 'department', 'name', 'code')


@admin.register(AdmissionPlan)
class AdmissionPlanAdmin(admin.ModelAdmin):
    list_display  = ('program', 'year', 'min_score', 'budget_places')
    list_filter   = ('year', 'program__university')
    search_fields = ('program__name',)


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display  = ('name', 'university', 'direction', 'degree')
    list_filter   = ('degree', 'university')
    search_fields = ('name', 'code')
    inlines = [AdmissionPlanInline, ProgramSubjectInline, EntranceExamInline]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name',)