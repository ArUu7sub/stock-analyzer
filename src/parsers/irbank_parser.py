import re


# 文字列から最初の数値を抽出してfloatへ変換する。
def extract_number(text: str) -> float | None:
    cleaned = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    return float(match.group())


# ラベル候補のいずれかに一致した行の直後から値を探索して返す。
def find_value_after_label(lines: list[str], labels: list[str]) -> str | None:
    normalized_labels = [label.replace(" ", "") for label in labels]

    def _is_forecast_marker(text: str) -> bool:
        token = text.replace(" ", "")
        return token == "予" or token.startswith("予(")

    def _match_label(line_text: str, label_text: str) -> bool:
        return line_text == label_text or line_text.startswith(label_text)

    for idx, line in enumerate(lines):
        normalized_line = line.replace(" ", "")
        for label in normalized_labels:
            start_offset: int | None = None

            # 通常の一致（例: "ROE（連）予" が1行で取れるケース）
            if _match_label(normalized_line, label):
                start_offset = 1
            # <dt>ROE（連）<span>予</span></dt> のように "予" が別行化されるケース
            elif label.endswith("予"):
                base_label = label[:-1]
                if _match_label(normalized_line, base_label):
                    next_idx = idx + 1
                    if next_idx < len(lines) and _is_forecast_marker(lines[next_idx]):
                        start_offset = 2

            if start_offset is not None:
                for offset in range(start_offset, start_offset + 5):
                    next_idx = idx + offset
                    if next_idx < len(lines) and lines[next_idx]:
                        if _is_forecast_marker(lines[next_idx]):
                            continue
                        return lines[next_idx]
    return None


# キーワードを含む行からパーセント値を抽出して返す。
def find_growth_near_keyword(lines: list[str], keyword: str) -> str | None:
    for line in lines:
        if keyword in line and "%" in line:
            match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", line)
            if match:
                return f"{match.group(1)}%"
    return None


# EPS実績と予想から成長率(%)を計算して返す。
def compute_eps_growth(eps_text: str | None, eps_forecast_text: str | None) -> str | None:
    if not eps_text or not eps_forecast_text:
        return None
    eps = extract_number(eps_text)
    eps_forecast = extract_number(eps_forecast_text)
    if eps is None or eps_forecast is None or eps == 0:
        return None
    growth = (eps_forecast - eps) / abs(eps) * 100
    return f"{growth:.2f}%"
