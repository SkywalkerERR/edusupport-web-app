from django.contrib import admin
from .models import (
    AdmissionStep, RequiredDocument,
    BudgetCategory, Benefit, FAQ
)


# @admin.register(AdmissionDeadline)
# class AdmissionDeadlineAdmin(admin.ModelAdmin):
#     list_display = ('date', 'event', 'type', 'order')
#     list_editable = ('order',)


@admin.register(AdmissionStep)
class AdmissionStepAdmin(admin.ModelAdmin):
    list_display = ('title', 'order')
    list_editable = ('order',)


@admin.register(RequiredDocument)
class RequiredDocumentAdmin(admin.ModelAdmin):
    list_display = ('text', 'type', 'order')
    list_editable = ('order',)
    list_filter = ('type',)



@admin.register(BudgetCategory)
class BudgetCategoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'quota', 'order')
    list_editable = ('order',)


@admin.register(Benefit)
class BenefitAdmin(admin.ModelAdmin):
    list_display = ('text', 'order')
    list_editable = ('order',)


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'section', 'order')
    list_editable = ('order',)
    list_filter = ('section',)