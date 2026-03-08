import html
import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


def _render_scalar(value: Any) -> str:
    if value is None:
        return '<span class="na">N/A</span>'
    return html.escape(str(value))


def _render_table_from_list(items: list[Any]) -> str:
    if not items:
        return '<p class="empty">データなし</p>'
    if not all(isinstance(item, dict) for item in items):
        rows = "".join(
            f"<tr><td>{html.escape(str(idx + 1))}</td><td>{_render_scalar(item)}</td></tr>"
            for idx, item in enumerate(items)
        )
        return (
            '<table><thead><tr><th>#</th><th>値</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>"
        )

    keys: list[str] = []
    for item in items:
        for key in item.keys():
            if key not in keys:
                keys.append(key)

    head = "".join(f"<th>{html.escape(key)}</th>" for key in keys)
    body_rows = []
    for item in items:
        cells = "".join(f"<td>{_render_scalar(item.get(key))}</td>" for key in keys)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def _render_group_items(items: Any) -> str:
    if isinstance(items, dict):
        rows = []
        for key, value in items.items():
            if isinstance(value, list):
                rendered = _render_table_from_list(value)
            elif isinstance(value, dict):
                rendered = _render_group_items(value)
            else:
                rendered = _render_scalar(value)
            rows.append(
                f"<tr><th>{html.escape(str(key))}</th><td>{rendered}</td></tr>"
            )
        return f'<table class="kv"><tbody>{"".join(rows)}</tbody></table>'
    if isinstance(items, list):
        return _render_table_from_list(items)
    return _render_scalar(items)


def _render_result_cards(result: dict[str, Any]) -> str:
    sections: list[str] = []
    for section, content in result.items():
        section_parts = [f"<section class='result-section'><h2>{html.escape(str(section))}</h2>"]
        if isinstance(content, dict):
            for group, items in content.items():
                section_parts.append(f"<h3>{html.escape(str(group))}</h3>")
                section_parts.append(_render_group_items(items))
        else:
            section_parts.append(f"<p>{_render_scalar(content)}</p>")
        section_parts.append("</section>")
        sections.append("".join(section_parts))
    return "".join(sections)


# 結果データを見やすいHTMLレポート(整形表示 + Raw JSON)として生成する。
def render_html_report(code: str, result: dict, company_name: str | None = None) -> str:
    rendered_cards = _render_result_cards(result)
    escaped_json = html.escape(json.dumps(result, ensure_ascii=False, indent=2))
    generated_at = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M:%S %Z")
    title_target = (
        f"{html.escape(code)} - {html.escape(company_name)}"
        if company_name
        else html.escape(code)
    )

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>IR Bank Analysis Report ({title_target})</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --card: #ffffff;
      --text: #16202a;
      --muted: #5c6b7a;
      --border: #d8e0ea;
      --header: #0f4c81;
      --subtle: #f8fafc;
    }}
    body {{
      margin: 0;
      font-family: "Hiragino Sans", "Noto Sans JP", sans-serif;
      background: linear-gradient(180deg, #eef3f9 0%, #f8fafc 100%);
      color: var(--text);
    }}
    .wrap {{
      max-width: 960px;
      margin: 24px auto;
      padding: 0 16px 24px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 16px;
      box-shadow: 0 6px 18px rgba(14, 29, 52, 0.06);
    }}
    h1 {{
      margin: 0 0 4px;
      font-size: 22px;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 20px;
      color: var(--header);
      border-left: 4px solid var(--header);
      padding-left: 8px;
    }}
    h3 {{
      margin: 16px 0 8px;
      font-size: 16px;
    }}
    .result-section {{
      margin-bottom: 20px;
    }}
    .result-section:last-child {{
      margin-bottom: 0;
    }}
    .meta {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 0;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 8px;
      font-size: 14px;
    }}
    th, td {{
      border: 1px solid var(--border);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: var(--subtle);
      font-weight: 600;
      white-space: nowrap;
    }}
    .kv th {{
      width: 220px;
    }}
    .na {{
      color: var(--muted);
    }}
    .empty {{
      margin: 0 0 8px;
      color: var(--muted);
      font-size: 14px;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.6;
      font-size: 14px;
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 14px;
      overflow: auto;
    }}
    details summary {{
      cursor: pointer;
      color: var(--muted);
      margin-bottom: 8px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <h1>IR Bank Analysis Report ({title_target})</h1>
      <p class="meta">Generated at: {generated_at}</p>
    </section>
    <section class="card">
      {rendered_cards}
    </section>
    <section class="card">
      <details>
        <summary>Raw JSON</summary>
        <pre>{escaped_json}</pre>
      </details>
    </section>
  </div>
</body>
</html>
"""
