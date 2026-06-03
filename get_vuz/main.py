"""
Извлечение контактов ВУЗов из XML Рособрнадзора (реестр лицензий).
"""

import xml.etree.ElementTree as ET
import pandas as pd
import os
import re
import sys

XML_PATH    = "data-20260403-structure-20160713.xml"
OUTPUT_PATH = "vuz_contacts.csv"

VUZ_EDU_LEVELS = [
    "во - ",
    "высшее",
    "послевузовское",
    "дополнительное к высшему",
]

# ──────────────────────────────────────────────────────────────────
# Чистка названий
# ──────────────────────────────────────────────────────────────────
# Юридические префиксы (форма собственности), которые регулятор сам
# приклеивает к каждому варианту. Их нужно срезать, чтобы выделить
# собственно «брендовое» название/аббревиатуру.
LEGAL_FORM_PREFIXES = [
    r"ФГ[АБК]ВОУ\s+ВО",          # ФГБВОУ ВО, ФГКВОУ ВО (военные)
    r"ФГ[АБК]ОУ\s+ВПО",          # ФГБОУ ВПО, ФГАОУ ВПО, ФГКОУ ВПО
    r"ФГ[АБК]ОУ\s+ВО",           # ФГБОУ ВО, ФГАОУ ВО, ФГКОУ ВО
    r"ФГОУ\s+ВПО", r"ФГОУ\s+ВО", # старая форма (до реформы 2013)
    r"ФГБУН",                    # ФГБУН (бюджетное учреждение науки)
    r"ОЧУ\s+ВПО", r"ОЧУ\s+ВО",
    r"НОЧУ\s+ВПО", r"НОЧУ\s+ВО",
    r"НОУ\s+ВПО",  r"НОУ\s+ВО",
    r"ЧОУ\s+ВПО",  r"ЧОУ\s+ВО",
    r"ГБОУ\s+ВПО", r"ГБОУ\s+ВО",
    r"ГАОУ\s+ВПО", r"ГАОУ\s+ВО",
    r"БОУ\s+ВПО",  r"БОУ\s+ВО",
    r"АОУ\s+ВПО",  r"АОУ\s+ВО",
    r"АНО\s+ВПО",  r"АНО\s+ВО",
]
_LEGAL_PREFIX_RE = re.compile(
    r"^(?:" + "|".join(LEGAL_FORM_PREFIXES) + r")\s+",
    re.IGNORECASE,
)
# Текст внутри « », “ ”, " " — каноническое название без юр. префикса.
_QUOTED_RE = re.compile(r"[«“\"]([^«»“”\"]+)[»”\"]")


def extract_canonical_name(full_name: str) -> str:
    """
    Возвращает одно понятное название университета.

    Стратегия: достать первый текст в кавычках («…», "…", “…”) — именно
    там регулятор хранит собственно название. Если кавычек нет
    (как у военных училищ КАПСОМ), возвращаем строку как есть.
    """
    if not full_name:
        return ""
    m = _QUOTED_RE.search(full_name)
    if m:
        return m.group(1).strip()
    return full_name.strip()


def extract_abbreviation(short_name: str, canonical: str = "") -> str:
    """
    Возвращает одно компактное сокращение (например, «КФУ», «МГУ», «СПбГУ»).

    Алгоритм:
      1) split по запятой → варианты сокращения от регулятора;
      2) выкидываем варианты с кавычками (это «ФГАОУ ВО «Полное название»» —
         там нет короткой аббревиатуры, дублирует каноническое имя);
      3) у оставшихся срезаем юр. префикс (ФГБОУ ВО, ОЧУ ВО и т.п.);
      4) выбираем самый короткий кандидат — обычно это и есть «КФУ»/«МГУ»;
      5) если ничего не осталось — пусто.
    """
    if not short_name:
        return ""

    variants = [v.strip() for v in short_name.split(",") if v.strip()]
    candidates = []
    for v in variants:
        # Варианты вида «ФГАОУ ВО «Казанский …»» — пропускаем,
        # они дублируют canonical name.
        if any(q in v for q in ("«", "»", "“", "”", '"')):
            continue
        cleaned = _LEGAL_PREFIX_RE.sub("", v).strip()
        if cleaned and cleaned.lower() != (canonical or "").lower():
            candidates.append(cleaned)

    if not candidates:
        return ""

    # Самый короткий кандидат = почти всегда искомая аббревиатура.
    return min(candidates, key=len)


def get_direct_child_text(elem, tag):
    child = elem.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""

def has_higher_edu(cert_elem):
    for edu_level in cert_elem.iter("EduLevelName"):
        text = (edu_level.text or "").lower()
        if any(kw in text for kw in VUZ_EDU_LEVELS):
            return True
    return False

def parse(xml_path):
    print(f"Читаю XML: {xml_path}")
    print("Для файла 900 МБ это займёт 3–7 минут...\n")

    seen_ogrn = set()
    records = []
    total = 0
    skipped_not_vuz = 0
    skipped_dup = 0

    for event, elem in ET.iterparse(xml_path, events=("end",)):
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag != "Certificate":
            # НЕ чистим дочерние элементы — иначе к моменту закрытия
            # <Certificate> у всех вложенных <EduLevelName>.text == None
            continue

        total += 1

        if not has_higher_edu(elem):
            skipped_not_vuz += 1
            elem.clear()
            continue

        aeo = elem.find("ActualEducationOrganization")
        if aeo is None:
            elem.clear()
            continue

        ogrn = get_direct_child_text(aeo, "OGRN") or get_direct_child_text(elem, "EduOrgOGRN")
        if ogrn and ogrn in seen_ogrn:
            skipped_dup += 1
            elem.clear()
            continue
        if ogrn:
            seen_ogrn.add(ogrn)

        is_branch = get_direct_child_text(aeo, "IsBranch")
        org_type = "филиал" if is_branch and is_branch not in ("", "0", "false") else "головной"

        full_name_raw  = get_direct_child_text(aeo, "FullName")
        short_name_raw = get_direct_child_text(aeo, "ShortName")
        canonical      = extract_canonical_name(full_name_raw)
        abbreviation   = extract_abbreviation(short_name_raw, canonical)

        records.append({
            "Название":               canonical,
            "Аббревиатура":           abbreviation,
            "Тип":                    org_type,
            "Сайт":                   get_direct_child_text(aeo, "WebSite"),
            "Email":                  get_direct_child_text(aeo, "Email"),
            "Телефон":                get_direct_child_text(aeo, "Phone"),
            "Адрес":                  get_direct_child_text(aeo, "PostAddress"),
            "Регион":                 get_direct_child_text(aeo, "RegionName"),
            "Федеральный округ":      get_direct_child_text(aeo, "FederalDistrictName"),
            "Руководитель":           get_direct_child_text(aeo, "HeadName"),
            "Должность руководителя": get_direct_child_text(aeo, "HeadPost"),
            "ОГРН":                   ogrn,
            "ИНН":                    get_direct_child_text(aeo, "INN"),
            "Статус лицензии":        get_direct_child_text(elem, "StatusName"),
        })

        elem.clear()

        if len(records) % 100 == 0:
            print(f"  ВУЗов найдено: {len(records)}  (сертификатов обработано: {total})")

    print(f"\n{'─'*50}")
    print(f"Всего сертификатов в файле:   {total}")
    print(f"Пропущено (не ВУЗы):          {skipped_not_vuz}")
    print(f"Пропущено (дубликаты ОГРН):   {skipped_dup}")
    print(f"Итого уникальных ВУЗов:       {len(records)}")
    print(f"{'─'*50}\n")

    return pd.DataFrame(records)


if __name__ == "__main__":
    if not os.path.exists(XML_PATH):
        print(f"ОШИБКА: файл не найден: {XML_PATH}")
        sys.exit(1)

    df = parse(XML_PATH)

    if df.empty:
        print("Ничего не извлечено.")
        sys.exit(1)

    # СНАЧАЛА сохраняем CSV — чтобы результат точно не потерялся
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"✅ Сохранено: {OUTPUT_PATH}  ({len(df)} строк)\n")

    print("По типу организации:")
    print(df["Тип"].value_counts().to_string())

    print("\nЗаполненность контактных полей:")
    for col in ["Сайт", "Email", "Телефон", "Адрес"]:
        filled = df[col].str.strip().ne("").sum()
        pct = filled / len(df) * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {col:<8} {bar} {filled}/{len(df)} ({pct:.0f}%)")