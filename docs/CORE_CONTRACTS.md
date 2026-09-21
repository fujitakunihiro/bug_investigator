# Core 間データ契約（V1）

Phase 0 で、UI に依存しない core 間の受け渡しデータを固定する。実装言語は Python 3 の標準ライブラリのみとし、`dataclasses`、`enum`、`typing` を利用できる。

## 基本方針

- 元ログの内容と正規化後の内容を分離して保持する。
- 行番号は UI 表示と調査のため、1始まりで保持する。
- 比較結果は UI 用文字列ではなく、構造化された値で返す。
- core は tkinter やファイルダイアログを参照しない。
- 空ログ、差分なし、片側末尾の差分を表現できるようにする。

## `LogLine`

`LogLoader` が返す1行分のデータ。

| フィールド | 型 | 内容 |
|---|---|---|
| `line_number` | `int` | 元ログ内の1始まりの行番号 |
| `raw_text` | `str` | 改行を除いた元の行 |
| `source` | `Literal["normal", "abnormal"]` | どちらのログか |

## `LogLoadResult` と読み込みエラー

`LogLoader.load(path, source)` は `LogLoadResult` を返す。

| フィールド | 型 | 内容 |
|---|---|---|
| `path` | `Path` | 読み込んだファイルのパス |
| `lines` | `list[LogLine]` | 1始まりの行番号を持つログ行 |
| `warnings` | `list[LoadWarning]` | 読み込み継続可能な警告 |

ファイル不存在、権限不足、読み取り失敗は `LogLoadError` として呼び出し元へ通知する。UTF-8として解釈できないバイトは `U+FFFD` に置換し、置換数を `LoadWarning` に記録する。空ファイルはエラーではなく、空の `lines` を返す。

## `NormalizedLine`

`Normalizer` は `LogLine` の `raw_text` に、設定ファイルで定義された正規表現ルールを記載順に適用する。`line_number`、`raw_text`、`source` は保持し、比較には `normalized_text` を使用する。既定設定は Timestamp と16進アドレスをそれぞれ `<TIMESTAMP>`、`<ADDR>` に置換する。

設定ファイルは次の形式とする。

```json
{
  "rules": [
    {
      "name": "timestamp",
      "pattern": "\\b...\\b",
      "replacement": "<TIMESTAMP>"
    }
  ]
}
```

設定ファイルの構造、キー、正規表現が不正な場合は `NormalizationConfigError` とする。

## `NormalizedLine`

`Normalizer` が `LogLine` から生成するデータ。

| フィールド | 型 | 内容 |
|---|---|---|
| `line_number` | `int` | 元ログの行番号を維持 |
| `raw_text` | `str` | 表示用に元の行を維持 |
| `normalized_text` | `str` | Timestamp 等を置換した比較用文字列 |
| `source` | `Literal["normal", "abnormal"]` | ログの種別 |

## `DiffType`

差分種別は次の3値とする。

- `MISSING`: 正常側に存在するが異常側に対応行がない
- `ADDED`: 異常側に存在するが正常側に対応行がない
- `CHANGED`: 近傍位置に両側の行があるが、正規化後の内容が異なる

`DiffEngine` は `difflib.SequenceMatcher` の時系列対応を利用する。`replace` ブロックでは、両側の重なる行数を近傍行として `CHANGED` にし、余った正常側を `MISSING`、余った異常側を `ADDED` にする。自動判定により原因を断定しない。

## `DiffItem`

`DiffEngine` が返す個々の差分。

| フィールド | 型 | 内容 |
|---|---|---|
| `type` | `DiffType` | 差分種別 |
| `normal_line` | `NormalizedLine \| None` | 正常側の対応行。Added では `None` |
| `abnormal_line` | `NormalizedLine \| None` | 異常側の対応行。Missing では `None` |
| `normal_index` | `int \| None` | 正規化済み正常列での0始まり位置 |
| `abnormal_index` | `int \| None` | 正規化済み異常列での0始まり位置 |

差分はログの時系列順に並べる。`DiffEngine` は最初の差分だけに絞らず、V1の件数表示用に全差分を返す。

## `ContextWindow`

`DivergenceDetector` が FIRST DIVERGENCE の周辺表示用に返すデータ。

| フィールド | 型 | 内容 |
|---|---|---|
| `lines` | `list[NormalizedLine]` | 前後行を含む表示対象 |
| `focus_index` | `int \| None` | `lines` 内の注目行。片側に行がない場合は `None` |
| `start_line_number` | `int \| None` | 元ログ上の開始行番号 |
| `end_line_number` | `int \| None` | 元ログ上の終了行番号 |

前後の目安は20行。端点ではログの範囲内に切り詰める。Missing の異常側のように注目行が存在しない場合でも、対応する位置の周辺行を返す。

## `FirstDivergence`

`DivergenceDetector` が返す最初の差分。

| フィールド | 型 | 内容 |
|---|---|---|
| `found` | `bool` | 差分が存在するか |
| `type` | `DiffType \| None` | 最初の差分種別。一致時は `None` |
| `expected` | `NormalizedLine \| None` | 正常系で期待される行 |
| `observed` | `NormalizedLine \| None` | 異常側で観測された行 |
| `previous` | `NormalizedLine \| None` | 直前の対応行 |
| `next` | `NormalizedLine \| None` | 直後の対応行 |
| `normal_context` | `ContextWindow` | 正常側の前後コンテキスト |
| `abnormal_context` | `ContextWindow` | 異常側の前後コンテキスト |

`found=False` の場合、差分種別・行・前後コンテキストは空値にする。原因の断定や原因コードはこの契約に含めない。コンテキストの既定半径は20行で、ログの端では範囲内に切り詰める。

## Phase 0 の期待結果

`testdata/normal.log` と `testdata/abnormal.log` を Timestamp 正規化した結果、イベント列は次のようになる。

```text
normal:   PowerOn, ClockStart, ClockReady, PanelInit, DisplayStart
abnormal: PowerOn, ClockStart, PanelInit, DisplayStart
```

したがって、最初の差分は次の値になる。

```text
found:    true
type:     MISSING
expected: ClockReady
previous: ClockStart
next:     PanelInit
```

Timestamp の値が異なっていても、正規化後の `PowerOn`、`ClockStart`、`PanelInit`、`DisplayStart` は同一イベントとして扱う。
