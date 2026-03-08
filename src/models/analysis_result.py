from typing import Any


# out定義の形に合わせて、抽出済みの値辞書を再帰的に出力形式へ変換する。
def build_result_from_spec(spec: Any, values: dict[str, Any]) -> Any:
    if isinstance(spec, dict):
        return {key: build_result_from_spec(child, values) for key, child in spec.items()}
    if isinstance(spec, list):
        return {item: values.get(item) for item in spec if isinstance(item, str)}
    if isinstance(spec, str):
        return values.get(spec)
    return None
