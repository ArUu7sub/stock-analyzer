import logging
import re
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter

from src.models.analysis_result import build_result_from_spec
from src.parsers.irbank_parser import (
    compute_eps_growth,
    find_growth_near_keyword,
    find_value_after_label,
)

USER_AGENT = "Mozilla/5.0 (compatible; stock-analyzer/1.0)"
LOGGER = logging.getLogger(__name__)


class MissingFieldError(Exception):
    pass


class InvalidExtractorConfigError(Exception):
    pass


class NetworkResolutionError(Exception):
    pass


def _fetch_soup(session: requests.Session, url: str) -> BeautifulSoup:
    try:
        response = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    except requests.exceptions.ConnectionError as exc:
        message = str(exc)
        if "NameResolutionError" in message or "Failed to resolve" in message:
            raise NetworkResolutionError(
                "irbank.net のDNS解決に失敗しました。"
                "ネットワーク/DNS/VPN設定を確認してください。"
            ) from exc
        raise
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def _extract_metric_series_from_performance_page(
    performance_soup: BeautifulSoup,
    metric: str,
    limit: int,
) -> list[dict[str, str]]:
    for box in performance_soup.select("div#graph > div"):
        h2 = box.find("h2")
        if not h2:
            continue
        title = h2.get_text("", strip=True)
        if not (title == metric or title.startswith(metric)):
            continue

        dl = box.find("dl")
        if not dl:
            continue

        dts = dl.find_all("dt", recursive=False)
        dds = dl.find_all("dd", recursive=False)
        series: list[dict[str, str]] = []
        for dt, dd in reversed(list(zip(dts, dds, strict=False))):
            dt_text = dt.get_text("", strip=True)
            year_match = re.search(r"\d{4}年\d{1,2}月", dt_text)
            if not year_match:
                continue
            value_node = dd.select_one("span.text")
            if not value_node:
                continue
            value_text = value_node.get_text(strip=True)
            if value_text == "-":
                continue
            series.append(
                {
                    "年度": year_match.group(),
                    "区分": "予想" if "予" in dt_text else "実績",
                    "値": value_text,
                }
            )
            if len(series) >= limit:
                return series
        return series
    return []


# out定義(辞書/配列/文字列)から、実際に必要な項目名を再帰的に収集する。
def _collect_requested_fields(spec: object) -> set[str]:
    fields: set[str] = set()
    if isinstance(spec, dict):
        for value in spec.values():
            fields.update(_collect_requested_fields(value))
    elif isinstance(spec, list):
        for item in spec:
            if isinstance(item, str):
                fields.add(item)
    elif isinstance(spec, str):
        fields.add(spec)
    return fields


# 1項目の値をextractor定義に従って解決する（循環参照・型不正も検証）。
def _resolve_field_value(
    field_name: str,
    lines: list[str],
    extractors: dict[str, Any],
    cache: dict[str, Any],
    visiting: set[str],
    context: dict[str, Any],
) -> Any:
    if field_name in cache:
        return cache[field_name]
    if field_name in visiting:
        raise InvalidExtractorConfigError(
            f"extractors に循環参照があります: {field_name}"
        )
    if field_name not in extractors:
        cache[field_name] = None
        return None

    visiting.add(field_name)
    rule = extractors[field_name]
    if not isinstance(rule, dict):
        visiting.remove(field_name)
        raise InvalidExtractorConfigError(
            f"extractors.{field_name} は object で指定してください。"
        )

    rule_type = rule.get("type")
    value: Any
    if rule_type == "label":
        labels = rule.get("labels", [])
        if not isinstance(labels, list):
            visiting.remove(field_name)
            raise InvalidExtractorConfigError(
                f"extractors.{field_name}.labels は list で指定してください。"
            )
        value = find_value_after_label(lines, [str(label) for label in labels])
    elif rule_type == "keyword_percent":
        keyword = rule.get("keyword")
        if not isinstance(keyword, str):
            visiting.remove(field_name)
            raise InvalidExtractorConfigError(
                f"extractors.{field_name}.keyword は string で指定してください。"
            )
        value = find_growth_near_keyword(lines, keyword)
    elif rule_type == "eps_growth":
        eps_field = str(rule.get("eps_field", "EPS"))
        forecast_field = str(rule.get("eps_forecast_field", "EPS予"))
        eps_text = _resolve_field_value(eps_field, lines, extractors, cache, visiting)
        forecast_text = _resolve_field_value(
            forecast_field, lines, extractors, cache, visiting
        )
        value = compute_eps_growth(eps_text, forecast_text)
    elif rule_type == "constant":
        constant_value = rule.get("value")
        value = None if constant_value is None else str(constant_value)
    elif rule_type == "performance_series":
        metric = rule.get("metric")
        if not isinstance(metric, str) or not metric:
            visiting.remove(field_name)
            raise InvalidExtractorConfigError(
                f"extractors.{field_name}.metric は string で指定してください。"
            )
        years = rule.get("years", 3)
        if not isinstance(years, int) or years <= 0:
            visiting.remove(field_name)
            raise InvalidExtractorConfigError(
                f"extractors.{field_name}.years は 1 以上の整数で指定してください。"
            )
        performance_soup = context.get("performance_soup")
        if performance_soup is None:
            value = None
        else:
            series = _extract_metric_series_from_performance_page(
                performance_soup=performance_soup, metric=metric, limit=years
            )
            value = series if series else None
    else:
        visiting.remove(field_name)
        raise InvalidExtractorConfigError(
            f"extractors.{field_name}.type が不正です: {rule_type}"
        )

    cache[field_name] = value
    visiting.remove(field_name)
    LOGGER.info("extract field=%s type=%s value=%s", field_name, rule_type, value)
    return value


# IR Bankの銘柄ページを1回だけ取得して、解析しやすい行配列へ整形する。
def fetch_page_lines(code: str) -> list[str]:
    base_url = f"https://irbank.net/{code}"
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=0))
    session.mount("http://", HTTPAdapter(max_retries=0))

    try:
        soup = _fetch_soup(session, base_url)
        lines = [line.strip() for line in soup.get_text("\n").splitlines() if line.strip()]
        LOGGER.info("fetched base page lines count=%s code=%s", len(lines), code)

        performance_url: str | None = None
        for link in soup.select("a[href]"):
            href = str(link.get("href", "")).strip()
            title = str(link.get("title", "")).strip()
            text = link.get_text(strip=True)
            if not href:
                continue
            if title == "会社業績" or text == "業績" or href.endswith("/pl"):
                performance_url = urljoin("https://irbank.net", href)
                break

        if not performance_url:
            LOGGER.info("no performance link found on base page code=%s", code)
            return lines

        performance_soup = _fetch_soup(session, performance_url)
        performance_lines = [
            line.strip()
            for line in performance_soup.get_text("\n").splitlines()
            if line.strip()
        ]
        LOGGER.info(
            "fetched performance page url=%s lines count=%s code=%s",
            performance_url,
            len(performance_lines),
            code,
        )
        return lines + performance_lines
    finally:
        session.close()


def fetch_performance_soup(code: str) -> BeautifulSoup | None:
    base_url = f"https://irbank.net/{code}"
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=0))
    session.mount("http://", HTTPAdapter(max_retries=0))
    try:
        base_soup = _fetch_soup(session, base_url)
        performance_url: str | None = None
        for link in base_soup.select("a[href]"):
            href = str(link.get("href", "")).strip()
            title = str(link.get("title", "")).strip()
            text = link.get_text(strip=True)
            if not href:
                continue
            if title == "会社業績" or text == "業績" or href.endswith("/pl"):
                performance_url = urljoin("https://irbank.net", href)
                break
        if not performance_url:
            LOGGER.info("performance page link not found code=%s", code)
            return None
        soup = _fetch_soup(session, performance_url)
        LOGGER.info("fetched performance soup url=%s code=%s", performance_url, code)
        return soup
    finally:
        session.close()


def _find_lines_containing_tokens(lines: list[str], tokens: list[str]) -> list[str]:
    hits: list[str] = []
    normalized_tokens = [token.replace(" ", "") for token in tokens]
    for line in lines:
        normalized_line = line.replace(" ", "")
        for token in normalized_tokens:
            if token and token in normalized_line:
                hits.append(line)
                break
        if len(hits) >= 5:
            break
    return hits


def _log_missing_field_diagnostics(
    lines: list[str],
    missing_fields: list[str],
    extractors: dict[str, Any],
) -> None:
    for field in missing_fields:
        rule = extractors.get(field)
        if not isinstance(rule, dict):
            LOGGER.warning("missing field=%s reason=no extractor rule", field)
            continue
        rule_type = rule.get("type")
        if rule_type == "label":
            labels = [str(label) for label in rule.get("labels", [])]
            hits = _find_lines_containing_tokens(lines, labels)
            LOGGER.warning(
                "missing field=%s type=label labels=%s matching_lines=%s",
                field,
                labels,
                hits,
            )
        elif rule_type == "constant":
            LOGGER.warning(
                "missing field=%s type=constant value=%s", field, rule.get("value")
            )
        else:
            LOGGER.warning("missing field=%s type=%s rule=%s", field, rule_type, rule)


# 設定定義に基づいて必要項目を抽出し、欠損チェック後に出力構造を組み立てる。
def scrape_irbank(
    code: str,
    out_spec: dict,
    extractors: dict[str, Any],
    allow_null_fields: set[str] | None = None,
) -> dict:
    effective_spec = out_spec
    allow_null = allow_null_fields or set()
    LOGGER.info("scrape start code=%s allow_null=%s", code, sorted(allow_null))

    lines = fetch_page_lines(code)
    values: dict[str, Any] = {}
    context: dict[str, Any] = {}
    if any(
        isinstance(rule, dict) and rule.get("type") == "performance_series"
        for rule in extractors.values()
    ):
        context["performance_soup"] = fetch_performance_soup(code)
    for field_name in extractors:
        _resolve_field_value(
            field_name=field_name,
            lines=lines,
            extractors=extractors,
            cache=values,
            visiting=set(),
            context=context,
        )

    requested_fields = _collect_requested_fields(effective_spec)
    LOGGER.info("requested fields=%s", sorted(requested_fields))
    missing_fields = sorted(
        field
        for field in requested_fields
        if field not in allow_null and values.get(field) is None
    )
    if missing_fields:
        LOGGER.error("missing fields=%s", missing_fields)
        _log_missing_field_diagnostics(lines, missing_fields, extractors)
        raise MissingFieldError(
            f"取得できない項目があり停止しました: {', '.join(missing_fields)}"
        )

    LOGGER.info("scrape success code=%s", code)
    return build_result_from_spec(effective_spec, values)
