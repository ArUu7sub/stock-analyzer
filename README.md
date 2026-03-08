# stock-analyzer
銘柄分析ツール

## プロジェクト構成

```text
stock-analyzer/
├── config/
│   └── irbank.json
├── data/
├── log/
├── src/
│   ├── main.py
│   ├── models/
│   │   └── analysis_result.py
│   ├── parsers/
│   │   └── irbank_parser.py
│   ├── scrapers/
│   │   └── irbank_scraper.py
│   └── utils/
│       └── report_renderer.py
├── requirements.txt
├── .flake8
├── setup.cfg
└── README.md
```

## 各ファイルの役割

- `config/irbank.json`: 実行設定。`in`（銘柄コード）、`extractors`（取得ルール）、`out`（取得項目定義）、`allow_null`（null許容項目）、`save`（保存先）を管理。
- `src/main.py`: エントリーポイント。設定読み込み、スクレイピング実行、エラーハンドリング、HTML保存を行う。
- `src/scrapers/irbank_scraper.py`: IR Bankへのアクセスと、必要項目の抽出制御を担当。銘柄ページに加えて業績ページ(`/.../pl`)も取得し、未取得項目チェックと停止判定を行う。
- `src/parsers/irbank_parser.py`: HTMLテキストから値を取り出すための小さな解析関数群（ラベル探索、成長率計算など）。
- `src/models/analysis_result.py`: `out` 定義に合わせて、取得済みデータを最終出力構造に組み立てる。
- `src/utils/report_renderer.py`: 取得結果を見やすいHTML（テーブル表示 + Raw JSON）にレンダリングする。
- `data/`: 生成されたレポートHTMLの保存先（デフォルト）。
- `log/`: 実行ログの保存先。抽出値や欠損項目の診断情報を記録。
- `requirements.txt`: 実行に必要なPython依存パッケージ一覧。
- `.flake8` / `setup.cfg`: Flake8のLint設定（例: 最大行長）を定義。

## IR Bank スクレイピング

入力: 銘柄コード（例: `7203`）  
出力: 指定された財務分析/株価評価の JSON

### セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 実行

```bash
python -m src.main
```

`config/irbank.json` の `in` / `extractors` / `out` を使って実行されます（`extractors` と `out` は必須）。  
`extractors` は「どう取得するか」の定義、`out` は「何を出力するか」の定義です。
`save` は保存先ディレクトリです。ファイル名は自動で `irbank_<銘柄コード>_<実行日>.html` になります。
`log/irbank_<銘柄コード>_<実行日時>.log` に詳細ログを出力します。  
スクレイピングはリトライせず1回のみ実行し、取得できない項目がある場合はその時点で停止します。

```json
{
  "in": "7203",
  "extractors": {
    "売上高_直近3年": {
      "type": "performance_series",
      "metric": "売上高",
      "years": 3
    },
    "営業利益_直近3年": {
      "type": "performance_series",
      "metric": "営業利益",
      "years": 3
    },
    "当期純利益_直近3年": {
      "type": "performance_series",
      "metric": "当期純利益",
      "years": 3
    },
    "ROE": {
      "type": "label",
      "labels": ["ROE（連）"]
    },
    "ROE予想": {
      "type": "label",
      "labels": ["ROE（連）予"]
    },
    "ROA": {
      "type": "label",
      "labels": ["ROA（連）"]
    },
    "ROA予想": {
      "type": "label",
      "labels": ["ROA（連）予"]
    },
    "EPS": {
      "type": "label",
      "labels": ["EPS（連）"]
    },
    "EPS予想": {
      "type": "label",
      "labels": ["EPS（連）予"]
    },
    "PER": {
      "type": "label",
      "labels": ["PER（連）"]
    },
    "PER予想": {
      "type": "label",
      "labels": ["PER（連）予"]
    },
    "PBR": {
      "type": "label",
      "labels": ["PBR（連）"]
    },
    "配当利回り": {
      "type": "label",
      "labels": ["配当利回り予"]
    },
    "自己資本比率": {
      "type": "label",
      "labels": ["株主資本比率（連）"]
    }
  },
  "out": {
    "財務分析": {
      "利益": ["売上高_直近3年", "営業利益_直近3年", "当期純利益_直近3年"],
      "収益性": ["ROE", "ROE予想", "ROA", "ROA予想"],
      "安全性": [],
      "成長性": []
    },
    "株価評価": ["EPS", "EPS予想", "PER", "PER予想", "PBR", "配当利回り", "自己資本比率"]
  },
  "allow_null": [],
  "save": "data"
}
```

引数で上書きも可能です。

```bash
python -m src.main 8306 --save data
python -m src.main --config config/irbank.json
```

### 備考

- `allow_null` に含まれない項目が見つからない場合は、保存せずにエラー終了します。
- `extractors` の `type` は `label` / `keyword_percent` / `eps_growth` / `constant` / `performance_series` を利用できます。
- `performance_series` は業績ページのグラフブロックを `metric`（見出し名）で特定し、直近 `years` 件を `{年度, 区分, 値}` 形式で返します。
- `data/` と `log/` は `.gitignore` に含まれているため、通常は `git push` 対象になりません。
