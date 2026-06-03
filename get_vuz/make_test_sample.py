"""
Генерирует vuz_contacts_test.csv — маленький тестовый срез из vuz_contacts.csv
с ~15 крупными известными ВУЗами (МГУ, СПбГУ, ВШЭ, МИФИ, МФТИ, Бауман,
ИТМО, МГИМО и т.д.).

Зачем: проверять работоспособность download_vuz_photos.py на заведомо
узнаваемых запросах. В датасете многие топовые вузы идут со статусом
"Недействующее" (из-за переоформления лицензий), поэтому фильтр по
статусу тут НЕ применяется — берём из всего датасета.

Запуск:
    python make_test_sample.py

Результат:
    vuz_contacts_test.csv — та же схема колонок, что в vuz_contacts.csv.
"""

import csv
import re
import sys
from pathlib import Path

SRC = Path("vuz_contacts.csv")
DST = Path("vuz_contacts_test.csv")

# Префиксы: "name:" — поиск по колонке «Название»,
#           "abbr:" — поиск по колонке «Аббревиатура».
TARGETS = [
    ("МГУ им. Ломоносова",
        ["name:Московский государственный университет имени М.В.Ломоносов"]),
    ("СПбГУ (головной)",
        ["name:Санкт-Петербургский государственный университет"]),
    ("ВШЭ (НИУ ВШЭ)",
        ["name:Высшая школа экономики"]),
    ("МФТИ",
        ["name:Московский физико-технический институт (национальный"]),
    ("МИФИ (только филиал ИАТЭ)",
        ["abbr:НИЯУ МИФИ",
         "name:Национальный исследовательский ядерный университет"]),
    ("МГТУ им. Баумана",
        ["name:Московский государственный технический университет им"]),
    ("ИТМО",
        ["abbr:Университет ИТМО",
         "name:Университет ИТМО"]),
    ("МГИМО",
        ["name:Московский государственный институт международных отношений"]),
    ("РАНХиГС",
        ["name:Российская академия народного хозяйства и государственной службы"]),
    ("МИСИС (НИТУ МИСИС)",
        ["abbr:НИТУ МИСИС"]),
    ("РУДН",
        ["name:Российский университет дружбы народов имени Патриса"]),
    ("НГУ (Новосибирск)",
        ["name:Новосибирский национальный исследовательский"]),
    ("ТГУ (Томск)",
        ["name:Национальный исследовательский Томский государственный университет"]),
    ("УрФУ",
        ["name:Уральский федеральный университет имени"]),
    ("КФУ (Казань)",
        ["name:Казанский (Приволжский) федеральный университет"]),
]


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def find_match(rows, markers):
    candidates = []
    for marker in markers:
        if marker.startswith("name:"):
            key, needle = "Название", marker[5:]
        elif marker.startswith("abbr:"):
            key, needle = "Аббревиатура", marker[5:]
        else:
            key, needle = None, marker
        needle_n = _norm(needle)
        for r in rows:
            if key is None:
                hay = _norm((r.get("Название") or "") + " " +
                            (r.get("Аббревиатура") or ""))
            else:
                hay = _norm(r.get(key) or "")
            if needle_n in hay and r not in candidates:
                candidates.append(r)
        if candidates:
            break
    if not candidates:
        return None
    rank = {"Действующее": 0, "Прекращено": 1, "Недействующее": 2}
    candidates.sort(key=lambda r: (
        rank.get((r.get("Статус лицензии") or "").strip(), 9),
        0 if r.get("Тип") == "головной" else 1,
    ))
    return candidates[0]


def main():
    if not SRC.exists():
        sys.exit(f"Нет файла {SRC}. Сначала запустите main.py.")

    with SRC.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    selected, missing = [], []
    for label, markers in TARGETS:
        row = find_match(rows, markers)
        if row:
            selected.append(row)
            short = (row.get("Аббревиатура") or
                     row.get("Название") or "")[:70]
            status = row.get("Статус лицензии") or "—"
            print(f"  + {label:<28} -> {short}  [{status}]")
        else:
            missing.append(label)
            print(f"  - {label:<28} -> не найден")

    seen, unique = set(), []
    for r in selected:
        k = r.get("ОГРН") or r.get("ИНН") or r.get("Название")
        if k in seen:
            continue
        seen.add(k)
        unique.append(r)

    with DST.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(unique)

    print("")
    print(f"Записано {len(unique)} строк в {DST}")
    if missing:
        print(f"Не найдено: {', '.join(missing)}")
    print("")
    print("Запустить поиск картинок:")
    print("    python download_vuz_photos.py --csv vuz_contacts_test.csv")


if __name__ == "__main__":
    main()
