"""
Management command: импорт научных показателей из CSV-файла (вывод PythonProject1).

Ожидаемые колонки CSV (universities_with_counts.csv):
    query_name              — название вуза, по которому шёл поиск в OpenAlex
    openalex_id             — ID института в OpenAlex
    works_count_from_filter — точное число публикаций
    works_count_from_institution — число публикаций (запасной вариант)
    cited_by_count          — число цитирований
    h_index                 — индекс Хирша
    match_status            — статус совпадения (not_found / error — пропускаются)

Матчинг с базой данных:
    1. Точное совпадение query_name == University.name
    2. query_name является подстрокой University.name
    3. Взвешенное пересечение слов (Jaccard ≥ 0.5)

Использование:
    python manage.py import_openalex_csv data/universities_with_counts.csv
    python manage.py import_openalex_csv data/result.csv --dry-run
    python manage.py import_openalex_csv data/result.csv --threshold 0.4
"""
import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.universities.models import University


# ──────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции матчинга
# ──────────────────────────────────────────────────────────────────────────────

def _tokens(s: str) -> set[str]:
    """Множество значимых слов строки (≥ 3 символа, без предлогов)."""
    stop = {'для', 'при', 'или', 'имя', 'имени', 'дружбы', 'или', 'им'}
    return {w for w in re.findall(r'[а-яёa-z]{3,}', s.lower()) if w not in stop}


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def find_university(query_name: str, universities: list) -> tuple:
    """
    Ищет наиболее подходящий университет в списке.
    Возвращает (University, score, метод) или (None, 0, '').
    """
    # 1. Точное совпадение
    for uni in universities:
        if uni.name == query_name:
            return uni, 1.0, 'exact'

    # 2. query_name — подстрока University.name (с границей слова)
    q_lower = query_name.lower()
    for uni in universities:
        if q_lower in uni.name.lower():
            return uni, 0.9, 'substring'

    # 3. Jaccard по словам
    scored = [(uni, _jaccard(query_name, uni.name)) for uni in universities]
    scored.sort(key=lambda x: x[1], reverse=True)
    if scored and scored[0][1] > 0:
        return scored[0][0], scored[0][1], 'jaccard'

    return None, 0.0, ''


# ──────────────────────────────────────────────────────────────────────────────
# Management command
# ──────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Импортирует данные OpenAlex (публикации, цитирования, h-index) из CSV'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str,
                            help='Путь к CSV-файлу (universities_with_counts.csv)')
        parser.add_argument('--encoding', default='utf-8-sig')
        parser.add_argument('--dry-run', action='store_true',
                            help='Показать что будет обновлено, без записи в БД')
        parser.add_argument('--threshold', type=float, default=0.45,
                            help='Минимальный Jaccard-порог для нечёткого совпадения (default: 0.45)')

    def handle(self, *args, **options):
        path      = Path(options['csv_file'])
        dry_run   = options['dry_run']
        threshold = options['threshold']

        if not path.exists():
            raise CommandError(f'Файл не найден: {path}')

        # Загружаем все вузы один раз
        all_unis = list(University.objects.all())

        updated = skipped = not_found = errors = 0

        try:
            with path.open(encoding=options['encoding'], newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    query_name   = (row.get('query_name')   or '').strip()
                    match_status = (row.get('match_status') or '').strip()

                    # Пропускаем незаматченные OpenAlex строки
                    if 'not_found' in match_status or 'error' in match_status:
                        self.stdout.write(self.style.WARNING(
                            f'  — {query_name}: пропущен OpenAlex ({match_status})'
                        ))
                        skipped += 1
                        continue

                    # Ищем вуз в БД
                    uni, score, method = find_university(query_name, all_unis)

                    if uni is None or (method == 'jaccard' and score < threshold):
                        self.stdout.write(self.style.WARNING(
                            f'  ? {query_name}: не найден в БД'
                            + (f' (лучший Jaccard: {score:.2f})' if score > 0 else '')
                        ))
                        not_found += 1
                        continue

                    # Читаем значения
                    openalex_id = (row.get('openalex_id') or '').strip()
                    works_raw   = (row.get('works_count_from_filter')
                                   or row.get('works_count_from_institution') or '').strip()
                    cited_raw   = (row.get('cited_by_count') or '').strip()
                    h_raw       = (row.get('h_index')        or '').strip()

                    works_count    = int(works_raw) if works_raw.isdigit() else None
                    cited_by_count = int(cited_raw) if cited_raw.isdigit() else None
                    h_index        = int(h_raw)     if h_raw.isdigit()     else None
                    matched_name   = row.get('matched_name') or '—'

                    confidence = f'{score:.0%}' if method == 'jaccard' else method

                    if dry_run:
                        self.stdout.write(
                            f'  ~ [{confidence}] «{query_name}»\n'
                            f'        >> БД: «{uni.name[:60]}»\n'
                            f'        OpenAlex: «{matched_name}» | '
                            f'работ: {works_count}, цит.: {cited_by_count}, h: {h_index}'
                        )
                        updated += 1
                        continue

                    uni.openalex_id    = openalex_id    or uni.openalex_id
                    uni.works_count    = works_count    if works_count    is not None else uni.works_count
                    uni.cited_by_count = cited_by_count if cited_by_count is not None else uni.cited_by_count
                    uni.h_index        = h_index        if h_index        is not None else uni.h_index
                    uni.save(update_fields=['openalex_id', 'works_count', 'cited_by_count', 'h_index'])

                    self.stdout.write(self.style.SUCCESS(
                        f'  [OK] [{confidence}] {query_name}\n'
                        f'        >> {uni.name[:70]}\n'
                        f'        работ: {uni.works_count}, цит.: {uni.cited_by_count}, h-index: {uni.h_index}'
                    ))
                    updated += 1

        except Exception as e:
            raise CommandError(f'Ошибка при чтении файла: {e}')

        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'\n{prefix}Готово: обновлено {updated}, '
            f'не найдено в БД {not_found}, пропущено {skipped}, ошибок {errors}.'
        ))
