"""
Одноразовая утилита: переводит существующий vuz_contacts.csv со старой
схемой (две колонки «Название (полное)» / «Название (краткое)») на новую
(«Название» / «Аббревиатура»), не перепарсивая 900 МБ XML.

Логика чистки берётся напрямую из main.py — один источник правды.

Запуск:
    python rewrite_existing_csv.py

Что делает:
  • читает vuz_contacts.csv (utf-8-sig);
  • сохраняет резерв в vuz_contacts.backup.csv;
  • переписывает vuz_contacts.csv с новой схемой;
  • показывает несколько примеров до/после.

После этого можно сразу запускать make_test_sample.py — он уже работает
с новой схемой.
"""

import csv
import shutil
import sys
from pathlib import Path

from main import extract_canonical_name, extract_abbreviation

SRC = Path("vuz_contacts.csv")
BACKUP = Path("vuz_contacts.backup.csv")

OLD_FULL  = "Название (полное)"
OLD_SHORT = "Название (краткое)"

NEW_NAME  = "Название"
NEW_ABBR  = "Аббревиатура"


def main():
    if not SRC.exists():
        sys.exit(f"Нет файла {SRC}. Запустите сначала main.py.")

    with SRC.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if NEW_NAME in fieldnames and OLD_FULL not in fieldnames:
        print(f"{SRC} уже в новой схеме — ничего не делаю.")
        return

    if OLD_FULL not in fieldnames or OLD_SHORT not in fieldnames:
        sys.exit(f"Не нашёл ожидаемых колонок «{OLD_FULL}»/«{OLD_SHORT}» в {SRC}.")

    # бэкап ДО любых изменений
    shutil.copyfile(SRC, BACKUP)
    print(f"Бэкап сохранён: {BACKUP}")

    # новая последовательность колонок: «Название» и «Аббревиатура»
    # вместо двух старых, остальное в том же порядке
    new_fieldnames = []
    inserted = False
    for col in fieldnames:
        if col == OLD_FULL:
            new_fieldnames.extend([NEW_NAME, NEW_ABBR])
            inserted = True
        elif col == OLD_SHORT:
            continue  # уже добавили рядом с OLD_FULL
        else:
            new_fieldnames.append(col)
    if not inserted:
        new_fieldnames = [NEW_NAME, NEW_ABBR] + new_fieldnames

    samples = []
    new_rows = []
    for r in rows:
        full  = r.get(OLD_FULL, "") or ""
        short = r.get(OLD_SHORT, "") or ""
        canon = extract_canonical_name(full)
        abbr  = extract_abbreviation(short, canon)

        new_r = {k: r.get(k, "") for k in new_fieldnames if k not in (NEW_NAME, NEW_ABBR)}
        new_r[NEW_NAME] = canon
        new_r[NEW_ABBR] = abbr
        new_rows.append(new_r)

        # копим примеры с явной чисткой
        if len(samples) < 12 and ("," in short or "«" in full):
            samples.append((full[:90], short[:90], canon[:60], abbr[:30]))

    with SRC.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)

    print(f"Перезаписано {SRC} ({len(new_rows)} строк) с новой схемой.\n")

    print("Примеры до/после:")
    print("─" * 100)
    for full, short, canon, abbr in samples:
        print(f"FULL :  {full}")
        print(f"SHORT:  {short}")
        print(f"  →  Название    : {canon}")
        print(f"  →  Аббревиатура: {abbr}")
        print("─" * 100)


if __name__ == "__main__":
    main()
