import html
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def _render_overview_page(rows: list[dict[str, str]]) -> str:
    generated_at = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S %Z")
    row_html = ""
    for row in rows:
        row_html += (
            "<tr>"
            f"<td>{html.escape(row['code'])}</td>"
            f"<td>{html.escape(row['updated'])}</td>"
            f"<td><a href=\"{html.escape(row['href'])}\">ページを開く</a></td>"
            "</tr>"
        )
    if not row_html:
        row_html = '<tr><td colspan="3">まだページがありません</td></tr>'

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Stock Analyzer Docs</title>
  <style>
    :root {{
      --bg: #f4f7fb;
      --card: #ffffff;
      --text: #13202f;
      --muted: #56708b;
      --line: #d8e2ee;
      --accent: #0a5fa8;
    }}
    body {{
      margin: 0;
      font-family: "Hiragino Sans", "Noto Sans JP", sans-serif;
      background: linear-gradient(180deg, #eef4fb 0%, #f8fbff 100%);
      color: var(--text);
    }}
    .wrap {{
      max-width: 960px;
      margin: 20px auto;
      padding: 0 14px 20px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 14px;
      box-shadow: 0 6px 16px rgba(9, 30, 66, 0.06);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 24px;
    }}
    p {{
      margin: 0;
      color: var(--muted);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 14px;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
    }}
    th {{
      background: #f7faff;
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .hint {{
      margin-top: 12px;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <h1>Stock Analyzer Reports</h1>
      <p>銘柄ごとの最新レポートページ一覧です。</p>
      <p class="hint">最終更新: {html.escape(generated_at)}</p>
    </section>
    <section class="card">
      <table>
        <thead>
          <tr>
            <th>銘柄コード</th>
            <th>更新日時 (JST)</th>
            <th>リンク</th>
          </tr>
        </thead>
        <tbody>
          {row_html}
        </tbody>
      </table>
    </section>
  </div>
</body>
</html>
"""


def publish_report_to_docs(code: str, report_path: Path) -> Path:
    docs_root = Path("docs")
    code_dir = docs_root / "codes" / code
    code_dir.mkdir(parents=True, exist_ok=True)

    target_path = code_dir / "index.html"
    shutil.copyfile(report_path, target_path)

    rows: list[dict[str, str]] = []
    codes_root = docs_root / "codes"
    if codes_root.exists():
        for child in sorted(codes_root.iterdir(), reverse=True):
            if not child.is_dir():
                continue
            index_file = child / "index.html"
            if not index_file.exists():
                continue
            updated = datetime.fromtimestamp(index_file.stat().st_mtime, tz=ZoneInfo("Asia/Tokyo"))
            rows.append(
                {
                    "code": child.name,
                    "updated": updated.strftime("%Y-%m-%d %H:%M:%S"),
                    "href": f"./codes/{child.name}/",
                }
            )

    docs_root.mkdir(parents=True, exist_ok=True)
    overview_html = _render_overview_page(rows)
    (docs_root / "index.html").write_text(overview_html, encoding="utf-8")
    return target_path
