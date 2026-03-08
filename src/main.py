#!/usr/bin/env python3
import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from src.scrapers.irbank_scraper import (
    InvalidExtractorConfigError,
    MissingFieldError,
    NetworkResolutionError,
    scrape_irbank,
)
from src.utils.docs_publisher import publish_report_to_docs
from src.utils.report_renderer import render_html_report


# 設定ファイル(JSON)を読み込み、存在しなければ空設定を返す。
def load_config(path: str) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


# 保存先ディレクトリと銘柄コードから、日付付きHTML出力パスを決定する。
def resolve_save_path(save_value: str | None, code: str) -> Path:
    date_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d")
    filename = f"irbank_{code}_{date_str}.html"

    if not save_value:
        return Path("data") / filename

    candidate = Path(save_value)
    if candidate.suffix.lower() == ".html":
        return candidate.parent / filename
    return candidate / filename


def setup_file_logger(code: str) -> Path:
    timestamp = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y%m%d_%H%M%S")
    log_path = Path("log") / f"irbank_{code}_{timestamp}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
    )
    root_logger.addHandler(file_handler)
    return log_path


# 引数/設定の解決、スクレイピング実行、HTML保存までを統括する。
def main() -> None:
    parser = argparse.ArgumentParser(description="IR Bank scraping tool")
    parser.add_argument("code", nargs="?", help="Stock code (e.g.)")
    parser.add_argument(
        "--config",
        default="config/irbank.json",
        help="Config file path (default: config/irbank.json)",
    )
    parser.add_argument("--save", help="Save output directory path")
    args = parser.parse_args()

    config = load_config(args.config)
    code = args.code or config.get("in")
    if not code:
        raise ValueError(
            "銘柄コードが未指定です。引数 code または config の in を指定してください。"
        )
    log_path = setup_file_logger(str(code))
    logging.getLogger(__name__).info("start scraping code=%s config=%s", code, args.config)

    out_spec = config.get("out")
    if not out_spec:
        raise ValueError("取得項目定義が未指定です。config の out を指定してください。")
    extractors = config.get("extractors")
    if not extractors:
        raise ValueError("取得ルールが未指定です。config の extractors を指定してください。")
    allow_null_fields = set(config.get("allow_null", []))
    try:
        result = scrape_irbank(
            str(code),
            out_spec=out_spec,
            extractors=extractors,
            allow_null_fields=allow_null_fields,
        )
    except MissingFieldError as exc:
        logging.getLogger(__name__).error("missing required fields: %s", exc)
        print(f"log: {log_path}", file=sys.stderr)
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    except InvalidExtractorConfigError as exc:
        logging.getLogger(__name__).error("invalid extractor config: %s", exc)
        print(f"log: {log_path}", file=sys.stderr)
        print(f"error: 設定ファイル不正: {exc}", file=sys.stderr)
        sys.exit(1)
    except NetworkResolutionError as exc:
        logging.getLogger(__name__).error("network resolution error: %s", exc)
        print(f"log: {log_path}", file=sys.stderr)
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        logging.getLogger(__name__).exception("unexpected scrape failure")
        print(f"log: {log_path}", file=sys.stderr)
        print(f"error: スクレイピングに失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)

    output_path = resolve_save_path(args.save or config.get("save"), str(code))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_report = render_html_report(str(code), result)
    output_path.write_text(html_report, encoding="utf-8")
    docs_page_path = publish_report_to_docs(str(code), output_path)
    logging.getLogger(__name__).info("saved report path=%s", output_path)
    logging.getLogger(__name__).info("published docs path=%s", docs_page_path)
    print(f"log: {log_path}")
    print(f"saved: {output_path}")
    print(f"docs: {docs_page_path}")


if __name__ == "__main__":
    main()
