"""
Выводит несколько ВУЗов из vuz_contacts.csv в читабельном формате.

Использование:
    python show_vuz.py            # покажет первые 3
    python show_vuz.py 5          # покажет первые 5
    python show_vuz.py 5 --random # 5 случайных
"""

import csv
import sys
import random

CSV_PATH = "vuz_contacts.csv"


def format_vuz(row: dict) -> str:
    def field(label: str, key: str) -> str:
        value = (row.get(key) or "").strip()
        return f"  {label:<22} {value}" if value else f"  {label:<22} —"

    name = (row.get("Название (краткое)") or row.get("Название (полное)") or "Без названия").strip()
    header = f"  {name}"
    full = (row.get("Название (полное)") or "").strip()

    lines = [
        "╔" + "═" * 78,
        "║" + header,
        "╚" + "═" * 78,
    ]
    if full and full != name:
        lines.append(field("Полное название:", "Название (полное)"))
    lines.extend([
        field("Тип:",           "Тип"),
        field("Сайт:",          "Сайт"),
        field("Email:",         "Email"),
        field("Телефон:",       "Телефон"),
        field("Адрес:",         "Адрес"),
        field("Регион:",        "Регион"),
        field("Руководитель:",  "Руководитель"),
        field("Должность:",     "Должность руководителя"),
        field("ОГРН:",          "ОГРН"),
        field("ИНН:",           "ИНН"),
        field("Статус лицензии:", "Статус лицензии"),
    ])
    return "\n".join(lines)


def main() -> None:
    # Разбор аргументов
    count = 3
    pick_random = False
    for arg in sys.argv[1:]:
        if arg == "--random":
            pick_random = True
        elif arg.isdigit():
            count = int(arg)

    try:
        with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        print(f"Не найден файл: {CSV_PATH}")
        print("Сначала запустите main.py, чтобы сгенерировать его.")
        sys.exit(1)

    if not rows:
        print("CSV пустой.")
        sys.exit(1)

    count = min(count, len(rows))
    sample = random.sample(rows, count) if pick_random else rows[:count]

    print(f"\nВсего ВУЗов в файле: {len(rows)}")
    print(f"Показываю: {count}{' (случайные)' if pick_random else ' (первые)'}\n")

    for row in sample:
        print(format_vuz(row))
        print()


if __name__ == "__main__":
    main()
