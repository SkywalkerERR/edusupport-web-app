import csv
import io
import re

from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.urls import path
from django.utils.html import format_html

from .models import University

from .models import University, AdmissionDeadline




def _extract_city(region: str, address: str) -> str:
    """
    Извлекает город из региона или адреса.
    'г. Москва'             → 'Москва'
    'Тюменская область', адрес 'Г. ТЮМЕНЬ, ...' → 'Тюмень'
    """
    region = region.strip()
    m = re.match(r'^г\.\s*(.+)', region, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r'\bг\.\s*([^,]+)', address, re.IGNORECASE)
    if m:
        return m.group(1).strip().title()
    return region.split()[0] if region else ''


def _import_row(row: dict):
    """
    Разбирает одну строку CSV и сохраняет в БД.
    Возвращает (obj, is_new) или None при ошибке.

    Поддерживает два формата:
      Новый: Название, Аббревиатура, Тип, Сайт, Email, Телефон, Адрес, Регион, ...
      Старый: Название (полное), Название (краткое), Тип, Сайт, Email, Телефон, Адрес, Регион, ...
    """
    # Поддержка обоих форматов
    if 'Название' in row:
        # Новый формат
        name      = (row.get('Название')     or '').strip()
        full_name = (row.get('Название')     or '').strip()  # нет отдельного полного
    else:
        # Старый формат (Рособрнадзор)
        short_name = (row.get('Название (краткое)') or '').strip()
        full_name  = (row.get('Название (полное)')  or '').strip()
        name = short_name or full_name

    if not name:
        return None

    region  = (row.get('Регион')   or '').strip()
    address = (row.get('Адрес')    or '').strip()
    email   = (row.get('Email')    or '').strip()
    phone   = (row.get('Телефон')  or '').strip()
    website = (row.get('Сайт')     or '').strip()

    if website and not website.startswith(('http://', 'https://')):
        website = 'https://' + website

    city = _extract_city(region, address)

    obj, is_new = University.objects.get_or_create(name=name)
    obj.full_name = full_name  or obj.full_name
    obj.city      = city       or obj.city
    obj.region    = region     or obj.region
    obj.address   = address    or obj.address
    obj.email     = email      or obj.email
    obj.phone     = phone      or obj.phone
    obj.website   = website    or obj.website
    obj.save()
    return obj, is_new

class AdmissionDeadlineInline(admin.TabularInline):
    model = AdmissionDeadline
    extra = 1


@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    change_list_template = 'admin/universities/change_list.html'
    list_display  = ('name', 'city', 'region', 'email', 'phone', 'photo_preview')
    search_fields = ('name', 'full_name', 'city', 'region')
    list_filter   = ('region', 'has_dormitory', 'has_military')
    readonly_fields = ('photo_preview',)
    inlines = [AdmissionDeadlineInline]

    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'full_name', 'description')
        }),
        ('Контакты и расположение', {
            'fields': ('region', 'city', 'address', 'website', 'email', 'phone')
        }),
        ('Медиа', {
            'fields': ('photo', 'photo_preview')
        }),
        ('Инфраструктура', {
            'fields': ('has_dormitory', 'has_military')
        }),
        ('Научная активность (OpenAlex)', {
            'fields': ('openalex_id', 'works_count', 'cited_by_count', 'h_index'),
            'classes': ('collapse',),
            'description': 'Заполняется автоматически командой: python manage.py import_openalex_csv',
        }),
    )

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<img src="{}" style="height:60px; border-radius:6px;">',
                obj.photo.url
            )
        return '—'
    photo_preview.short_description = 'Превью'

    # ── Кастомные URL для импорта CSV ─────────────────────────────────
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-csv/',
                 self.admin_site.admin_view(self.import_csv_view),
                 name='universities_university_import_csv'),
        ]
        return custom + urls

    def import_csv_view(self, request):
        """Страница загрузки CSV-файла в admin-панели."""
        if request.method == 'POST':
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                messages.error(request, 'Файл не выбран.')
                return redirect('.')

            if not csv_file.name.endswith('.csv'):
                messages.error(request, 'Загрузите файл в формате .csv')
                return redirect('.')

            decoded = csv_file.read().decode('utf-8-sig')
            reader  = csv.DictReader(io.StringIO(decoded))

            created = updated = errors = 0
            for row in reader:
                try:
                    result = _import_row(row)
                    if result is None:
                        errors += 1
                        continue
                    obj, is_new = result
                    if is_new:
                        created += 1
                    else:
                        updated += 1
                except Exception:
                    errors += 1

            messages.success(
                request,
                f'Импорт завершён: создано {created}, обновлено {updated}, ошибок {errors}.'
            )
            return redirect('../')

        context = {
            **self.admin_site.each_context(request),
            'title': 'Импорт университетов из CSV',
            'opts':  self.model._meta,
        }
        return render(request, 'admin/universities/import_csv.html', context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['import_csv_url'] = 'import-csv/'
        return super().changelist_view(request, extra_context=extra_context)
