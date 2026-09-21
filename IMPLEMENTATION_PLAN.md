# 不具合捜査ツール V1 実装計画

## 1. 要件の確認結果

### 目的

正常ログと異常ログを比較し、正常系から最初に挙動が異なった地点を `FIRST DIVERGENCE` として提示する。大量の差分一覧や原因の断定ではなく、調査すべき起点を素早く確認できることを最優先とする。

### V1 の入力と結果

- 正常ログ1ファイル、異常ログ1ファイルをファイル選択で指定する。
- 大きなログを読み込み、文字コードエラー等をアプリ全体の停止につなげない。
- 元ログは変更しない。
- 比較前に Timestamp、16進アドレス、任意正規表現を正規化する。
- 正規化後に Missing / Added / Changed を検出する。
- 最初の差分について種別、期待行、直前行、直後行を提示する。
- 選択した差分の前後約20行を正常・異常の両側で確認できる。

### 非対象

ドラッグ＆ドロップ、複数正常ログ、Timing / Order / Value / Repeat の高度な検出、正常出現率、候補ランキング、AI解析、機械学習、グラフ表示は V1 完成後まで扱わない。

## 2. 想定構成

```text
src/
├─ main.py
├─ ui/main_window.py
├─ core/log_loader.py
├─ core/normalizer.py
├─ core/diff_engine.py
├─ core/divergence.py
└─ config/normalization.json
tests/
├─ test_normalizer.py
├─ test_diff_engine.py
└─ test_divergence.py
testdata/
├─ normal.log
└─ abnormal.log
```

## 3. 段階的な実装計画

### Phase 0: テストデータと契約の準備（完了）

- `testdata/normal.log` と `testdata/abnormal.log` を作成した。
- Timestamp だけが異なる同一イベントとして扱える例を含めた。
- ClockReady が異常ログにないケースで、期待結果が `MISSING / ClockReady` になることを定義した。
- core 間で受け渡すデータ構造を [`docs/CORE_CONTRACTS.md`](docs/CORE_CONTRACTS.md) に固定した。

### Phase 1: LogLoader（完了）

- パスから行を読み取る読み取り専用コンポーネント [`src/core/log_loader.py`](src/core/log_loader.py) を作成した。
- UTF-8 を基本とし、デコード不能バイトは `U+FFFD` に置換し、置換数を警告として返す方針にした。
- ファイル不存在・読み取り失敗は `LogLoadError`、空ファイルは空結果として扱う。
- 元ファイルを変更しないことを [`tests/test_log_loader.py`](tests/test_log_loader.py) で確認する。
- 大規模ログについては、ファイルを行単位で読み込む。契約上は正規化・比較で参照するため行リストを返すが、ファイル全体のバイト列を一括保持しない。

### Phase 2: Normalizer（完了）

- UI や diff engine から独立した変換器 [`src/core/normalizer.py`](src/core/normalizer.py) を作成した。
- Timestamp、16進アドレスを既定ルールで `<TIMESTAMP>`、`<ADDR>` へ置換する設定 [`src/config/normalization.json`](src/config/normalization.json) を追加した。
- `normalization.json` から任意正規表現ルールを読み込めるようにした。
- 元の行と正規化後の行の両方を保持する `NormalizedLine` を追加した。
- ルールの順序適用、不正設定、Timestamp・アドレス置換を [`tests/test_normalizer.py`](tests/test_normalizer.py) で確認する。

### Phase 3: DiffEngine（完了）

- 正規化済み行列を時系列順に比較する [`src/core/diff_engine.py`](src/core/diff_engine.py) を作成した。
- `difflib.SequenceMatcher` を利用し、Missing / Added / Changed を分類する。
- `replace` ブロックでは近傍行を Changed として対応付け、余剰行を Missing / Added として扱う。
- 差分位置と正常・異常それぞれのインデックス・行情報を `DiffItem` に保持する。
- Phase 0の ClockReady Missing、Added、Changed、完全一致、行数差のテストを [`tests/test_diff_engine.py`](tests/test_diff_engine.py) で確認する。

### Phase 4: FIRST DIVERGENCE（完了）

- 比較結果の先頭差分を選び、FIRST DIVERGENCE として返す [`src/core/divergence.py`](src/core/divergence.py) を作成した。
- Missing / Added / Changed ごとに期待行・観測行・Previous・Next を構造化した。
- 正常・異常それぞれから既定で前後20行のコンテキストを抽出する。
- 差分なし、空ログ、先頭・末尾の差分を表現できる結果モデルにした。
- ClockReady Missing、Changed、差分なし、コンテキスト半径を [`tests/test_divergence.py`](tests/test_divergence.py) で確認する。

### Phase 5: Unit Test（完了）

- 正規化: Timestamp、アドレス、任意正規表現、ルール不一致、Timestamp表記差を確認した。
- 差分: Missing、Added、Changed、完全一致、複数差分、カテゴリ別件数を確認した。
- FIRST DIVERGENCE: ClockReady Missing、最初の差分優先、先頭・末尾差分、差分なし、空側、前後コンテキストを確認した。
- 文字コードエラー、空入力、ファイル不存在、元ログ非変更をLogLoaderのテストで確認済み。

### Phase 6: tkinter UI（完了）

- 正常ログ・異常ログのパス入力とファイル選択ボタンを [`src/ui/main_window.py`](src/ui/main_window.py) に配置した。
- 「捜査開始」で loader → normalizer → diff engine → divergence を順に呼び出す。
- UI は解析ロジックを持たず、結果モデルを表示する構成にした。
- NORMAL、ABNORMAL、FIRST DIVERGENCE を区別したレイアウトにした。
- FIRST DIVERGENCE を強調し、前後ログと Missing / Added / Changed の件数を表示する。
- 読み込み警告はステータスに、エラーはダイアログに表示し、アプリを終了させない。
- [`src/main.py`](src/main.py) をGUI起動エントリーポイントとした。

### Phase 7: 実ログ確認（サンプル実ファイルで完了／ユーザー実ログ待ち）

- `testdata/normal.log` と `testdata/abnormal.log` を実ファイルとして、loader → normalizer → diff engine → divergence の一連の処理を確認した。
- `MISSING=1 / Added=0 / Changed=0`、FIRST DIVERGENCEが `ClockReady`、Previousが `ClockStart`、Nextが `PanelInit` になることを確認した。
- 読み込み警告は正常ログ・異常ログとも0件だった。
- 実行前後のSHA-256が一致し、元ログが変更されないことを確認した。
- 現在リポジトリ内にはユーザー提供の大規模ログ・文字化けログはないため、それらの検証は実ログ受領後に行う。誤検出調整や正規化ルール追加は未実施。

## 4. V1 Done 判定

正常ログと異常ログを指定して「捜査開始」を押すと、読み込み、正規化、比較、最初の差分検出、FIRST DIVERGENCE の強調表示、正常・異常の前後ログ比較が一連で動作すること。テストデータでは `ClockReady` の Missing が最初の差分として自動テストと UI の双方で確認できること。

## 5. 未決事項（実装開始前に確認する設計判断）

- 文字コードの既定値と、デコード不能バイトを置換するか警告扱いにするか。
- `Changed` の「同じ位置付近」を決める対応付けルール。
- 正規化 JSON の具体的なスキーマ（名前、正規表現、置換文字列、適用順）。
- 前後20行の基準を正常側・異常側のどちらのインデックスから決めるか。
- 差分がない場合や入力が空の場合の UI 表示文言。
