"""
Management command: импорт университетов из CSV-файла.

Заголовки ожидаемого файла:
    Название (полное), Название (краткое), Тип, Сайт,
    Email, Телефон, Адрес, Регион, Федеральный округ,
    Руководитель, Должность руководителя, ОГРН, ИНН, Статус лицензии

Использование:
    python manage.py import_universities data.csv
    python manage.py import_universities data.csv --encoding cp1251
    python manage.py import_universities data.csv --update    # обновлять существующие
    python manage.py import_universities data.csv --dry-run   # только проверить
"""
import csv

from django.core.management.base import BaseCommand, CommandError

from apps.universities.admin import _import_row
from apps.universities.models import University


class Command(BaseCommand):
    help = 'Импортирует университеты из CSV-файла (формат Рособрнадзора)'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Путь к CSV-файлу')
        parser.add_argument(
            '--encoding', default='utf-8-sig',
            help='Кодировка файла (по умолчанию: utf-8-sig). Для Windows-файлов: cp1251'
        )
        parser.add_argument(
            '--update', action='store_true',
            help='Обновлять данные уже существующих университетов'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Только показать что будет импортировано, без записи в БД'
        )

    def handle(self, *args, **options):
        path     = options['csv_file']
        encoding = options['encoding']
        update   = options['update']
        dry_run  = options['dry_run']

        try:
            with open(path, encoding=encoding, newline='') as f:
                reader = csv.DictReader(f)

                created = updated = skipped = errors = 0

                for line, row in enumerate(reader, start=2):
                    # Поддержка обоих форматов
                    if 'Название' in row:
                        name = (row.get('Название') or '').strip()
                    else:
                        short_name = (row.get('Название (краткое)') or '').strip()
                        full_name  = (row.get('Название (полное)')  or '').strip()
                        name = short_name or full_name

                    if not name:
                        self.stderr.write(f'  Строка {line}: пропущена (нет названия)')
                        errors += 1
                        continue

                    exists = University.objects.filter(name=name).exists()

                    if exists and not update:
                        skipped += 1
                        continue

                    if dry_run:
                        action = 'обновить' if exists else 'создать'
                        self.stdout.write(f'  [{action}] {name}')
                        if exists:
                            updated += 1
                        else:
                            created += 1
                        continue

                    result = _import_row(row)
                    if result is None:
                        errors += 1
                        self.stderr.write(self.style.WARNING(f'  Строка {line}: ошибка парсинга'))
                        continue

                    obj, is_new = result
                    if is_new:
                        created += 1
                        self.stdout.write(self.style.SUCCESS(f'  [+] {obj.name}'))
                    else:
                        updated += 1
                        self.stdout.write(f'  [~] {obj.name}')

        except FileNotFoundError:
            raise CommandError(f'Файл не найден: {path}')
        except Exception as e:
            raise CommandError(f'Ошибка при чтении файла: {e}')

        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'\n{prefix}Готово: создано {created}, обновлено {updated}, '
            f'пропущено {skipped}, ошибок {errors}.'
        ))
