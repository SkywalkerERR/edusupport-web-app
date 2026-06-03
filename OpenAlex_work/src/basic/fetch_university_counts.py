from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential


BASE_URL = "https://api.openalex.org"
DEFAULT_TIMEOUT = 30.0


# --- Префиксы официальных названий, которые мешают поиску в OpenAlex.
# Логика повторяет старый convert_csv.py — теперь это часть основного скрипта,
# чтобы можно было кормить ему vuz_contacts.csv напрямую (без convert_csv.py).
PREFIX_PATTERNS = [
    r"федеральное государственное автономное образовательное учреждение высшего (профессионального )?образования\s*",
    r"федеральное государственное бюджетное образовательное учреждение высшего (профессионального )?образования\s*",
    r"федеральное государственное казенное образовательное учреждение высшего (профессионального )?образования\s*",
    r"федеральное государственное бюджетное военное образовательное учреждение высшего образования\s*",
    r"федеральное государственное казенное военное образовательное учреждение высшего образования\s*",
    r"федеральное государственное автономное учреждение высшего образования\s*",
    r"федеральное государственное бюджетное учреждение (науки\s+)?\s*",
    r"государственное бюджетное образовательное учреждение высшего (профессионального )?образования\s*",
    r"государственное автономное образовательное учреждение высшего образования\s*",
    r"автономная некоммерческая организация высшего (профессионального )?образования\s*",
    r"негосударственное (некоммерческое )?образовательное (частное )?учреждение высшего (профессионального )?образования\s*",
    r"негосударственное образовательное учреждение высшего (профессионального )?образования\s*",
    r"частное образовательное учреждение высшего (профессионального )?образования\s*",
    r"частное учреждение высшего образования\s*",
    r"образовательное частное учреждение высшего образования\s*",
    r"образовательное учреждение высшего образования\s*",
]


@dataclass
class InstitutionMatch:
    query_name: str
    country_code: str | None
    matched_name: str | None
    openalex_id: str | None
    ror: str | None
    works_count_from_institution: int | None
    works_count_from_filter: int | None
    cited_by_count: int | None
    country: str | None
    type: str | None
    homepage_url: str | None
    match_status: str
    note: str | None
    # --- summary_stats из OpenAlex (индексы цитируемости)
    h_index: int | None = None
    i10_index: int | None = None
    mean_citedness_2yr: float | None = None
    # --- Идентификаторы вуза из исходного vuz_contacts.csv.
    # Нужны, чтобы веб-приложение смогло однозначно сматчить строку
    # universities_with_counts.csv обратно к вузу (по ИНН/ОГРН/полному названию).
    full_name: str | None = None
    inn: str | None = None
    ogrn: str | None = None


class OpenAlexClient:
    def __init__(self, api_key: str | None = None, mailto: str | None = None) -> None:
        self.api_key = api_key
        self.mailto = mailto
        headers = {"User-Agent": "university-openalex-counter/1.0"}
        self.client = httpx.Client(timeout=DEFAULT_TIMEOUT, headers=headers)

    def _params(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if self.api_key:
            params["api_key"] = self.api_key
        if self.mailto:
            params["mailto"] = self.mailto
        if extra:
            params.update(extra)
        return params

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, RuntimeError)),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    def get_json(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        response = self.client.get(url, params=self._params(params))
        if response.status_code == 429:
            raise RuntimeError("Rate limited by OpenAlex (HTTP 429)")
        response.raise_for_status()
        return response.json()

    def search_institution(self, name: str, country_code: str | None = None) -> list[dict[str, Any]]:
        filters: list[str] = []
        if country_code:
            filters.append(f"country_code:{country_code}")

        params: dict[str, Any] = {
            "search": name,
            "per_page": 10,
        }
        if filters:
            params["filter"] = ",".join(filters)

        data = self.get_json("/institutions", params=params)
        results = data.get("results", [])
        if results:
            return results

        # --- Fallback: autocomplete (им пользуется сайт openalex.org).
        # Более терпимый fuzzy-поиск по display_name_alternatives,
        # лучше находит длинные/нестандартные русские названия.
        return self._autocomplete_institutions(name, country_code)

    def _autocomplete_institutions(
        self, name: str, country_code: str | None = None
    ) -> list[dict[str, Any]]:
        try:
            ac = self.get_json("/autocomplete/institutions", params={"q": name})
        except Exception:
            return []
        ac_results = ac.get("results", [])[:5]
        full: list[dict[str, Any]] = []
        for item in ac_results:
            inst_id = normalize_openalex_id(item.get("id"))
            if not inst_id:
                continue
            try:
                inst = self.get_json(f"/institutions/{inst_id}")
            except Exception:
                continue
            if country_code and (inst.get("country_code") or "").upper() != country_code.upper():
                continue
            full.append(inst)
        return full

    def get_works_count_by_filter(self, institution_id: str) -> int:
        # نطلب عنصرًا واحدًا فقط، ثم نقرأ meta.count
        data = self.get_json(
            "/works",
            params={
                "filter": f"authorships.institutions.id:{institution_id}",
                "per_page": 1,
                "select": "id",
            },
        )
        meta = data.get("meta", {})
        return int(meta.get("count", 0))

    def close(self) -> None:
        self.client.close()


def normalize_openalex_id(raw_id: str | None) -> str | None:
    if not raw_id:
        return None
    # مثال: https://openalex.org/I97018004 -> I97018004
    return raw_id.rstrip("/").split("/")[-1]


def clean_name(full_name: str) -> str:
    """Приводит официальное русское название вуза к короткой форме,
    близкой к тому, как вуз записан в OpenAlex (без юр. префикса,
    без 'национальный исследовательский', без 'имени ...' и т.п.).

    Логика перенесена из convert_csv.py, чтобы основной скрипт мог
    есть vuz_contacts.csv напрямую — без промежуточной конвертации.
    """
    name = (full_name or "").strip()
    if not name:
        return ""

    # 1. Юридический префикс (регистронезависимо)
    for pat in PREFIX_PATTERNS:
        new = re.sub(pat, "", name, count=1, flags=re.IGNORECASE)
        if new != name:
            name = new
            break
    name = name.strip()

    # 2. Убираем «ёлочки» вокруг всего названия целиком
    m = re.match(r'^[«"](.+)[»"]$', name)
    if m:
        name = m.group(1).strip()

    # 3. Срезаем хвостовые добавки «имени ...», «им. ...», «Министерства ...»
    name = re.sub(r"\s*имени\s+[^,»\"]+$", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"\s*им\.\s*[^,»\"]+$", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"\s+министерства\s+[^,»\"]+$", "", name, flags=re.IGNORECASE).strip()

    # «национальный исследовательский» — удаляем, в OpenAlex его обычно нет в алиасах
    name = re.sub(r"\bнациональный\s+исследовательский\s+", "", name, flags=re.IGNORECASE)
    # уточнения в скобках вида «(Приволжский)»
    name = re.sub(r"\s*\([^)]{1,40}\)\s*", " ", name)

    # Сжимаем пробелы и обрезаем мусор по краям
    name = re.sub(r"\s+", " ", name).strip(" ,-—–")
    return name or full_name.strip()


def parse_aliases(short_field: str | None) -> list[str]:
    """Раскладывает поле «Название (краткое)» на список алиасов.

    В исходном CSV алиасы перечислены через запятую или точку с запятой,
    могут быть в кавычках/«ёлочках». Возвращаем чистый список без пустых строк.
    Эти алиасы пригодятся для поиска и для скоринга кандидатов OpenAlex.
    """
    if not short_field:
        return []
    s = str(short_field).strip()
    if not s:
        return []
    # Разделители: запятая или точка с запятой
    parts = re.split(r"[;,]", s)
    out: list[str] = []
    for p in parts:
        v = p.strip().strip('«»"\'')
        if v:
            out.append(v)
    # Убираем дубликаты, сохраняем порядок
    seen: set[str] = set()
    uniq: list[str] = []
    for v in out:
        key = v.lower()
        if key not in seen:
            seen.add(key)
            uniq.append(v)
    return uniq


def _tokenize(s: str) -> set[str]:
    """Разбивает строку на множество слов (латиница/кириллица/цифры, lowercase)."""
    return set(re.findall(r"\w+", s.lower()))


def _name_similarity(name: str, query: str) -> int:
    """Сходство имени кандидата и запроса в диапазоне 0..100.

    - 100 — точное совпадение строк.
    - Иначе — взвешенная сумма coverage (сколько слов запроса нашлось
      в имени кандидата) и Jaccard-сходства множеств слов. Jaccard
      штрафует «раздутых» кандидатов, у которых на несколько слов
      больше, чем в запросе (именно это разводит настоящий ТГУ от ТУСУРа:
      «Томский государственный университет» полностью входит в оба,
      но у ТУСУРа ещё 4 лишних слова — значит Jaccard ниже).
    """
    n = (name or "").strip().lower()
    q = (query or "").strip().lower()
    if not n or not q:
        return 0
    if n == q:
        return 100
    q_tokens = _tokenize(q)
    n_tokens = _tokenize(n)
    if not q_tokens or not n_tokens:
        return 0
    intersection = q_tokens & n_tokens
    if not intersection:
        return 0
    union = q_tokens | n_tokens
    coverage = len(intersection) / len(q_tokens)
    jaccard = len(intersection) / len(union)
    return int(round(50 * coverage + 50 * jaccard))


def score_candidate(candidate: dict[str, Any], query_names: list[str]) -> tuple[int, str]:
    # Все имена кандидата: основное + альтернативные (русские формы, акронимы).
    names: list[str] = []
    dn = (candidate.get("display_name") or "").strip()
    if dn:
        names.append(dn)
    for alt in candidate.get("display_name_alternatives") or []:
        if alt:
            names.append(str(alt).strip())

    # Лучшее совпадение по перекрёстному произведению:
    # (все варианты запроса) × (все имена кандидата).
    # Это позволяет матчить вуз и по полному названию, и по короткому
    # алиасу (МГУ, НГУ, ВШЭ и т.п.), что особенно важно когда полное
    # официальное название слишком длинное и зашумлённое.
    best_name_sim = 0
    for q in query_names:
        for n in names:
            sim = _name_similarity(n, q)
            if sim > best_name_sim:
                best_name_sim = sim

    score = best_name_sim
    reason_parts: list[str] = []
    if best_name_sim == 100:
        reason_parts.append("exact_name")
    elif best_name_sim >= 60:
        reason_parts.append("strong_partial")
    elif best_name_sim > 0:
        reason_parts.append("weak_partial")

    # Бонус за масштаб (до +20). При равном имени крупный вуз выигрывает у мелкого.
    works_count = int(candidate.get("works_count") or 0)
    score += min(works_count // 1000, 20)

    # Штраф, если тип института точно не учебный/научный.
    inst_type = (candidate.get("type") or "").lower()
    if inst_type and inst_type not in ("education", "facility", "funder"):
        score -= 30
        reason_parts.append(f"type={inst_type}")

    country = candidate.get("country_code")
    if country:
        reason_parts.append(f"country={country}")

    return score, ";".join(reason_parts)


def choose_best_match(
    results: list[dict[str, Any]], query_names: list[str]
) -> tuple[dict[str, Any] | None, str]:
    if not results:
        return None, "no_results"

    scored: list[tuple[int, str, dict[str, Any]]] = []
    for item in results:
        score, why = score_candidate(item, query_names)
        scored.append((score, why, item))

    # Сортировка по скору; tie-break — works_count, чтобы при равенстве
    # имён побеждал крупный вуз (это тоже работает против ТГУ→ТУСУР).
    scored.sort(
        key=lambda x: (x[0], int(x[2].get("works_count") or 0)),
        reverse=True,
    )
    best_score, why, best = scored[0]

    if best_score < 40:
        return best, f"low_confidence:{why}"

    return best, f"matched:{why}"


def process_row(
    client: OpenAlexClient,
    university_name: str,
    country_code: str | None,
    aliases: list[str] | None = None,
    full_name: str | None = None,
    inn: str | None = None,
    ogrn: str | None = None,
) -> InstitutionMatch:
    aliases = aliases or []
    # Все варианты запроса для скоринга: основной + алиасы (без пустых/дублей).
    query_variants: list[str] = []
    seen: set[str] = set()
    for v in [university_name, *aliases]:
        v = (v or "").strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            query_variants.append(v)

    try:
        results = client.search_institution(university_name, country_code)
        # Если по основному запросу OpenAlex ничего не вернул — пробуем
        # короткие алиасы (МГУ, НГУ, ВШЭ и т.п.) до первого непустого ответа.
        if not results:
            for alias in aliases:
                alias = alias.strip()
                if not alias:
                    continue
                results = client.search_institution(alias, country_code)
                if results:
                    break

        best, status = choose_best_match(results, query_variants)

        if not best:
            return InstitutionMatch(
                query_name=university_name,
                country_code=country_code,
                matched_name=None,
                openalex_id=None,
                ror=None,
                works_count_from_institution=None,
                works_count_from_filter=None,
                cited_by_count=None,
                country=None,
                type=None,
                homepage_url=None,
                match_status="not_found",
                note="No institution match returned from OpenAlex",
                full_name=full_name,
                inn=inn,
                ogrn=ogrn,
            )

        openalex_id = normalize_openalex_id(best.get("id"))
        works_count_from_institution = best.get("works_count")
        works_count_from_filter = client.get_works_count_by_filter(openalex_id) if openalex_id else None

        ids_obj = best.get("ids") or {}
        geo = best.get("geo") or {}

        # --- Индексы цитируемости из summary_stats
        stats = best.get("summary_stats") or {}
        h_index_raw = stats.get("h_index")
        i10_index_raw = stats.get("i10_index")
        mean_cit_raw = stats.get("2yr_mean_citedness")

        return InstitutionMatch(
            query_name=university_name,
            country_code=country_code,
            matched_name=best.get("display_name"),
            openalex_id=openalex_id,
            ror=ids_obj.get("ror"),
            works_count_from_institution=int(works_count_from_institution) if works_count_from_institution is not None else None,
            works_count_from_filter=int(works_count_from_filter) if works_count_from_filter is not None else None,
            cited_by_count=int(best.get("cited_by_count") or 0),
            country=geo.get("country"),
            type=best.get("type"),
            homepage_url=best.get("homepage_url"),
            match_status=status,
            note=None,
            h_index=int(h_index_raw) if h_index_raw is not None else None,
            i10_index=int(i10_index_raw) if i10_index_raw is not None else None,
            mean_citedness_2yr=float(mean_cit_raw) if mean_cit_raw is not None else None,
            full_name=full_name,
            inn=inn,
            ogrn=ogrn,
        )
    except Exception as exc:
        return InstitutionMatch(
            query_name=university_name,
            country_code=country_code,
            matched_name=None,
            openalex_id=None,
            ror=None,
            works_count_from_institution=None,
            works_count_from_filter=None,
            cited_by_count=None,
            country=None,
            type=None,
            homepage_url=None,
            match_status="error",
            note=str(exc),
            full_name=full_name,
            inn=inn,
            ogrn=ogrn,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch OpenAlex work counts for universities.")
    parser.add_argument(
        "--input",
        default="data/vuz_contacts_test.csv",
        help=(
            "Path to input CSV. Поддерживаются два формата: "
            "(1) старый — колонки university_name,country_code; "
            "(2) формат веб-приложения — vuz_contacts.csv с колонками "
            "'Название (полное)','Название (краткое)',ИНН,ОГРН и т.п."
        ),
    )
    parser.add_argument(
        "--output",
        default="data/universities_with_counts.csv",
        help="Path to output CSV file",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Sleep time between universities to be polite with the API",
    )
    return parser.parse_args()


def _get_first(row: pd.Series, *keys: str) -> str:
    """Возвращает первое непустое строковое значение по списку имён колонок.

    Нужно, чтобы поддержать сразу две версии формата vuz_contacts.csv:
      - старая: 'Название (полное)' / 'Название (краткое)'
      - новая:  'Название' / 'Аббревиатура'
    """
    for k in keys:
        if k in row.index:
            v = row.get(k)
            if pd.isna(v):
                continue
            s = str(v).strip()
            if s:
                return s
    return ""


def _row_from_vuz_contacts(row: pd.Series) -> dict[str, Any]:
    """Готовит из строки vuz_contacts.csv словарь с полями для process_row.

    Поддерживает обе версии формата веб-приложения:
      - 'Название (полное)' + 'Название (краткое)'
      - 'Название' + 'Аббревиатура'

    Что забираем:
      - query_name  — короткое имя для поиска (через clean_name).
      - aliases     — список кратких алиасов (МГУ, НГУ, ВШЭ и т.п.).
      - full_name   — оригинальное название из CSV (для матчинга в вебе).
      - inn / ogrn  — налоговые идентификаторы (главные ключи для веба).
    """
    full_name_raw = _get_first(row, "Название (полное)", "Название")
    short_field = _get_first(row, "Название (краткое)", "Аббревиатура")

    # clean_name безопасен и для уже короткого «Название» — он просто срежет
    # «национальный исследовательский», скобочные уточнения и «имени ...».
    query_name = clean_name(full_name_raw)
    aliases = parse_aliases(short_field)

    inn = _get_first(row, "ИНН") or None
    ogrn = _get_first(row, "ОГРН") or None

    return {
        "university_name": query_name,
        "aliases": aliases,
        "full_name": full_name_raw or None,
        "inn": inn,
        "ogrn": ogrn,
    }


def main() -> int:
    args = parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    api_key = os.getenv("OPENALEX_API_KEY")
    mailto = os.getenv("OPENALEX_MAILTO")

    # Поддерживаем оба возможных кодирования заголовков (utf-8 / utf-8 с BOM).
    df = pd.read_csv(input_path, encoding="utf-8-sig")

    # --- Определяем формат входного файла.
    # vuz_contacts.csv (формат веб-приложения) — содержит ИНН/ОГРН и одну из
    # двух пар колонок названий:
    #   * 'Название (полное)' + 'Название (краткое)'  (старая версия экспорта)
    #   * 'Название' + 'Аббревиатура'                  (текущая версия экспорта)
    is_vuz_contacts = ("Название (полное)" in df.columns) or ("Название" in df.columns)

    if not is_vuz_contacts and "university_name" not in df.columns:
        print(
            "CSV must contain either 'university_name' column (старый формат) "
            "или 'Название'/'Название (полное)' (формат vuz_contacts.csv)",
            file=sys.stderr,
        )
        return 1

    if not is_vuz_contacts and "country_code" not in df.columns:
        df["country_code"] = None

    client = OpenAlexClient(api_key=api_key, mailto=mailto)

    # Поля в порядке записи в CSV (берём из dataclass, чтобы порядок был стабилен).
    fieldnames = list(InstitutionMatch.__dataclass_fields__.keys())
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    try:
        with output_path.open("w", encoding="utf-8-sig", newline="") as fout:
            writer = csv.DictWriter(fout, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            fout.flush()

            total = len(df)
            for idx, row in df.iterrows():
                if is_vuz_contacts:
                    info = _row_from_vuz_contacts(row)
                    university_name = info["university_name"]
                    aliases = info["aliases"]
                    full_name = info["full_name"]
                    inn = info["inn"]
                    ogrn = info["ogrn"]
                    # У vuz_contacts.csv нет столбца страны — все вузы из РФ.
                    country_code = "RU"
                    if not university_name:
                        # Пустое полное название — фиксируем как not_found, но строку всё равно пишем,
                        # чтобы веб-приложение увидело: «по этому ИНН данных нет».
                        result = InstitutionMatch(
                            query_name="",
                            country_code=country_code,
                            matched_name=None,
                            openalex_id=None,
                            ror=None,
                            works_count_from_institution=None,
                            works_count_from_filter=None,
                            cited_by_count=None,
                            country=None,
                            type=None,
                            homepage_url=None,
                            match_status="not_found",
                            note="Empty 'Название (полное)' in input row",
                            full_name=full_name,
                            inn=inn,
                            ogrn=ogrn,
                        )
                        print(f"[{idx + 1}/{total}] Skipped (empty name), inn={inn}")
                        writer.writerow(result.__dict__)
                        fout.flush()
                        written += 1
                        continue
                else:
                    university_name = str(row["university_name"]).strip()
                    country_code = (
                        None if pd.isna(row["country_code"]) else str(row["country_code"]).strip().upper()
                    )
                    aliases = []
                    full_name = None
                    inn = None
                    ogrn = None

                tag = inn or full_name or "-"
                print(
                    f"[{idx + 1}/{total}] Processing: {university_name} "
                    f"({country_code or '-'}) [key={tag}]"
                )
                result = process_row(
                    client,
                    university_name,
                    country_code,
                    aliases=aliases,
                    full_name=full_name,
                    inn=inn,
                    ogrn=ogrn,
                )
                # Пишем строку сразу, чтобы при падении/Ctrl-C не потерять прогресс.
                writer.writerow(result.__dict__)
                fout.flush()
                written += 1

                time.sleep(args.sleep)
    finally:
        client.close()

    print(f"\nDone. {written} rows saved to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())