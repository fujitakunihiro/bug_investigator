"""Main tkinter window for the Bug Investigator."""

from __future__ import annotations

import tkinter as tk
import sys
import json
import os
import shutil
import subprocess
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from ..core.diff_engine import DiffEngine, DiffItem, DiffResult, DiffType
    from ..core.divergence import ContextWindow, FirstDivergence, DivergenceDetector
    from ..core.log_loader import LogLoadError, LogLoader
    from ..core.normalizer import (
        Normalizer,
        NormalizationConfigError,
        NormalizationRule,
        NormalizedLine,
    )
except ImportError:
    # Support launching this .pyw directly by double-clicking it in Windows.
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src.core.diff_engine import DiffEngine, DiffItem, DiffResult, DiffType
    from src.core.divergence import ContextWindow, FirstDivergence, DivergenceDetector
    from src.core.log_loader import LogLoadError, LogLoader
    from src.core.normalizer import (
        Normalizer,
        NormalizationConfigError,
        NormalizationRule,
        NormalizedLine,
    )


class MainWindow:
    """Own the widgets and connect them to the core analysis pipeline."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Bug Investigator")
        self.root.minsize(900, 600)

        self.normal_path = tk.StringVar()
        self.abnormal_path = tk.StringVar()
        self.status_text = tk.StringVar(value="正常ログと異常ログを指定してください")
        self._load_last_paths()
        self.show_normalized = tk.BooleanVar(value=False)
        self._last_divergence: FirstDivergence | None = None
        self._last_diff_result: DiffResult | None = None
        self._last_normal_lines: list[NormalizedLine] = []
        self._last_abnormal_lines: list[NormalizedLine] = []
        self._selected_diff_item: DiffItem | None = None

        self.normal_text: tk.Text
        self.abnormal_text: tk.Text
        self.summary_title = tk.StringVar(value="最初の相違点（FIRST DIVERGENCE）")
        self.summary_text = tk.StringVar(value="未解析")
        self._build()

    def _build(self) -> None:
        self._build_menu()
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Bug Investigator", font=("Segoe UI", 16, "bold")).pack(
            anchor=tk.W, pady=(0, 12)
        )

        input_frame = ttk.Frame(container)
        input_frame.pack(fill=tk.X, pady=(0, 10))
        self._path_row(input_frame, 0, "Normal Log", self.normal_path)
        self._path_row(input_frame, 1, "Abnormal Log", self.abnormal_path)

        action_frame = ttk.Frame(container)
        action_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(action_frame, text="捜査開始", command=self.run_investigation).pack(
            ipadx=18, ipady=4
        )
        ttk.Label(action_frame, textvariable=self.status_text).pack(
            side=tk.LEFT, padx=(14, 0)
        )

        panes = ttk.Panedwindow(container, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        normal_frame = ttk.LabelFrame(panes, text="NORMAL")
        abnormal_frame = ttk.LabelFrame(panes, text="ABNORMAL")
        panes.add(normal_frame, weight=1)
        panes.add(abnormal_frame, weight=1)
        self.normal_text = self._create_log_view(normal_frame)
        self.abnormal_text = self._create_log_view(abnormal_frame)
        self.normal_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.abnormal_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._add_scrollbar(normal_frame, self.normal_text)
        self._add_scrollbar(abnormal_frame, self.abnormal_text)

        legend = ttk.LabelFrame(container, text="行の色の意味", padding=(8, 4))
        legend.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(legend, text="黄色:").pack(side=tk.LEFT)
        tk.Label(legend, text=" 最初の相違点 ", background="#fff2a8").pack(
            side=tk.LEFT, padx=(2, 14)
        )
        ttk.Label(legend, text="橙色:").pack(side=tk.LEFT)
        tk.Label(legend, text=" 後続の相違点 ", background="#ffe0b2").pack(
            side=tk.LEFT, padx=(2, 14)
        )
        ttk.Label(legend, text="赤色:").pack(side=tk.LEFT)
        tk.Label(legend, text=" 欠落位置の案内 ", background="#ffd6d6", foreground="#b00020").pack(
            side=tk.LEFT, padx=2
        )

        summary = ttk.LabelFrame(
            container,
            text="相違点の詳細",
            padding=8,
        )
        summary.pack(fill=tk.X)
        ttk.Label(
            summary,
            textvariable=self.summary_title,
            font=("Segoe UI", 10, "bold"),
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(0, 4))
        ttk.Label(
            summary,
            textvariable=self.summary_text,
            justify=tk.LEFT,
            anchor=tk.W,
        ).pack(fill=tk.X)
        ttk.Button(
            summary,
            text="全相違点を表示",
            command=self._show_all_diffs,
        ).pack(anchor=tk.E, pady=(8, 0))

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="正規化ログを保存", command=self._export_normalized_logs)
        file_menu.add_command(
            label="正規化ログを保存してWinMergeで開く",
            command=self._export_and_open_winmerge,
        )
        menu_bar.add_cascade(label="ファイル", menu=file_menu)
        view_menu = tk.Menu(menu_bar, tearoff=False)
        view_menu.add_checkbutton(
            label="正規化後のログを表示",
            variable=self.show_normalized,
            command=self._refresh_views,
        )
        view_menu.add_separator()
        view_menu.add_command(label="全相違点を表示", command=self._show_all_diffs)
        menu_bar.add_cascade(label="表示", menu=view_menu)
        settings_menu = tk.Menu(menu_bar, tearoff=False)
        settings_menu.add_command(label="正規化ルール設定", command=self._show_normalization_settings)
        menu_bar.add_cascade(label="設定", menu=settings_menu)
        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(label="使い方", command=self._show_help)
        help_menu.add_command(label="このツールについて", command=self._show_about)
        menu_bar.add_cascade(label="ヘルプ", menu=help_menu)
        self.root.config(menu=menu_bar)

    def _export_normalized_logs(self) -> None:
        self._export_normalized_logs_impl(open_winmerge=False)

    def _export_and_open_winmerge(self) -> None:
        self._export_normalized_logs_impl(open_winmerge=True)

    def _export_normalized_logs_impl(self, open_winmerge: bool) -> None:
        if not self._last_normal_lines and not self._last_abnormal_lines:
            messagebox.showinfo("正規化ログの保存", "先に解析を実行してください。")
            return

        directory = filedialog.askdirectory(
            title="正規化ログの保存先フォルダを選択"
        )
        if not directory:
            return

        output_dir = Path(directory)
        normal_path = output_dir / "normal.normalized.log"
        abnormal_path = output_dir / "abnormal.normalized.log"
        try:
            self._write_normalized_log(normal_path, self._last_normal_lines)
            self._write_normalized_log(abnormal_path, self._last_abnormal_lines)
        except OSError as exc:
            messagebox.showerror("保存エラー", str(exc))
            return

        if open_winmerge:
            winmerge = self._find_winmerge()
            if winmerge is None:
                messagebox.showinfo(
                    "WinMergeが見つかりません",
                    "正規化ログは保存しましたが、WinMergeを見つけられませんでした。\n\n"
                    f"正常: {normal_path}\n"
                    f"異常: {abnormal_path}",
                )
                return
            try:
                subprocess.Popen([str(winmerge), str(normal_path), str(abnormal_path)])
            except OSError as exc:
                messagebox.showerror("WinMerge起動エラー", str(exc))
                return

        messagebox.showinfo(
            "保存完了",
            (
                "正規化ログを保存し、WinMergeを起動しました。"
                if open_winmerge
                else "正規化ログを保存しました。"
            )
            + "\n\n"
            f"正常: {normal_path}\n"
            f"異常: {abnormal_path}",
        )

    @staticmethod
    def _find_winmerge() -> Path | None:
        executable = shutil.which("WinMergeU.exe") or shutil.which("WinMerge.exe")
        if executable:
            return Path(executable)
        candidates = (
            Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
            / "WinMerge"
            / "WinMergeU.exe",
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"))
            / "WinMerge"
            / "WinMergeU.exe",
        )
        return next((path for path in candidates if path.exists()), None)

    @staticmethod
    def _write_normalized_log(path: Path, lines: list[NormalizedLine]) -> None:
        content = "\r\n".join(line.normalized_text for line in lines)
        if lines:
            content += "\r\n"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            handle.write(content)

    @staticmethod
    def _normalization_config_path() -> Path:
        return Path(__file__).resolve().parents[1] / "config" / "normalization.json"

    def _show_normalization_settings(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("正規化ルール設定")
        window.geometry("980x560")
        window.minsize(780, 440)
        window.transient(self.root)

        rules = self._load_normalization_rules()
        selected_item: list[str | None] = [None]

        outer = ttk.Frame(window, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            outer,
            text=(
                "比較前にログから置き換える値を設定します。"
                "ルールは上から順番に適用されます。"
            ),
            wraplength=900,
        ).pack(anchor=tk.W, pady=(0, 8))

        columns = ("name", "pattern", "replacement")
        tree = ttk.Treeview(outer, columns=columns, show="headings", selectmode="browse")
        tree.heading("name", text="ルール名")
        tree.heading("pattern", text="正規表現")
        tree.heading("replacement", text="置換文字列")
        tree.column("name", width=160, stretch=False)
        tree.column("pattern", width=500)
        tree.column("replacement", width=220)
        tree.pack(fill=tk.BOTH, expand=True)

        for rule in rules:
            tree.insert("", tk.END, values=(rule["name"], rule["pattern"], rule["replacement"]))

        editor = ttk.LabelFrame(outer, text="ルール編集", padding=8)
        editor.pack(fill=tk.X, pady=(10, 0))
        name_var = tk.StringVar()
        pattern_var = tk.StringVar()
        replacement_var = tk.StringVar()
        self._rule_entry(editor, 0, "ルール名", name_var)
        self._rule_entry(editor, 1, "正規表現", pattern_var)
        self._rule_entry(editor, 2, "置換文字列", replacement_var)

        preview = ttk.LabelFrame(outer, text="正規化ルールのプレビュー", padding=8)
        preview.pack(fill=tk.X, pady=(10, 0))
        preview_input = tk.StringVar(value="10:00:00.123 PanelOpen addr=0x1234")
        preview_result = tk.StringVar(value="")
        ttk.Label(preview, text="入力例", width=14).grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(preview, textvariable=preview_input).grid(
            row=0, column=1, sticky=tk.EW, padx=(0, 8), pady=3
        )
        ttk.Button(
            preview,
            text="プレビュー",
            command=lambda: preview_rules(),
        ).grid(row=0, column=2, pady=3)
        ttk.Label(preview, text="変換後", width=14).grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Label(
            preview,
            textvariable=preview_result,
            anchor=tk.W,
            relief=tk.SUNKEN,
        ).grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=3)
        preview.columnconfigure(1, weight=1)

        def select_rule(_event: object) -> None:
            selection = tree.selection()
            if not selection:
                selected_item[0] = None
                return
            selected_item[0] = selection[0]
            values = tree.item(selection[0], "values")
            name_var.set(values[0])
            pattern_var.set(values[1])
            replacement_var.set(values[2])

        def clear_editor() -> None:
            selected_item[0] = None
            name_var.set("")
            pattern_var.set("")
            replacement_var.set("")
            tree.selection_remove(tree.selection())

        def add_or_update() -> None:
            name = name_var.get().strip()
            pattern = pattern_var.get()
            replacement = replacement_var.get()
            try:
                NormalizationRule.create(name, pattern, replacement)
            except ValueError as exc:
                messagebox.showerror("ルールエラー", str(exc), parent=window)
                return
            values = (name, pattern, replacement)
            if selected_item[0] is None:
                tree.insert("", tk.END, values=values)
            else:
                tree.item(selected_item[0], values=values)
            clear_editor()

        def delete_selected() -> None:
            if selected_item[0] is not None:
                tree.delete(selected_item[0])
                clear_editor()

        def preview_rules() -> None:
            text = preview_input.get()
            try:
                for item_id in tree.get_children():
                    values = tree.item(item_id, "values")
                    rule = NormalizationRule.create(values[0], values[1], values[2])
                    text = rule.apply(text)
            except ValueError as exc:
                preview_result.set(f"ルールエラー: {exc}")
                return
            preview_result.set(text)

        def save_rules() -> None:
            payload = {
                "rules": [
                    {
                        "name": tree.item(item, "values")[0],
                        "pattern": tree.item(item, "values")[1],
                        "replacement": tree.item(item, "values")[2],
                    }
                    for item in tree.get_children()
                ]
            }
            try:
                for rule in payload["rules"]:
                    NormalizationRule.create(
                        rule["name"], rule["pattern"], rule["replacement"]
                    )
                config_path = self._normalization_config_path()
                config_path.parent.mkdir(parents=True, exist_ok=True)
                with config_path.open("w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
            except (OSError, ValueError) as exc:
                messagebox.showerror("保存エラー", str(exc), parent=window)
                return
            messagebox.showinfo(
                "保存完了",
                "正規化ルールを保存しました。次回の解析から反映されます。",
                parent=window,
            )

        tree.bind("<<TreeviewSelect>>", select_rule)
        buttons = ttk.Frame(editor)
        buttons.grid(row=3, column=1, columnspan=2, sticky=tk.E, pady=(8, 0))
        ttk.Button(buttons, text="追加／更新", command=add_or_update).pack(side=tk.LEFT, padx=3)
        ttk.Button(buttons, text="選択行を削除", command=delete_selected).pack(side=tk.LEFT, padx=3)
        ttk.Button(buttons, text="入力をクリア", command=clear_editor).pack(side=tk.LEFT, padx=3)
        ttk.Button(buttons, text="保存", command=save_rules).pack(side=tk.LEFT, padx=3)
        ttk.Button(buttons, text="閉じる", command=window.destroy).pack(side=tk.LEFT, padx=3)
        preview_rules()

    @staticmethod
    def _rule_entry(parent: ttk.LabelFrame, row: int, label: str, variable: tk.StringVar) -> None:
        ttk.Label(parent, text=label, width=14).grid(row=row, column=0, sticky=tk.W, pady=3)
        ttk.Entry(parent, textvariable=variable).grid(
            row=row, column=1, columnspan=2, sticky=tk.EW, padx=(0, 8), pady=3
        )
        parent.columnconfigure(1, weight=1)

    def _load_normalization_rules(self) -> list[dict[str, str]]:
        try:
            with self._normalization_config_path().open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            rules = payload.get("rules", []) if isinstance(payload, dict) else []
            if isinstance(rules, list):
                return [
                    {
                        "name": str(rule.get("name", "")),
                        "pattern": str(rule.get("pattern", "")),
                        "replacement": str(rule.get("replacement", "")),
                    }
                    for rule in rules
                    if isinstance(rule, dict)
                ]
        except (OSError, json.JSONDecodeError, AttributeError, TypeError):
            pass
        return []

    def _refresh_views(self) -> None:
        if self._last_divergence is None:
            return
        self._render_context(
            self.normal_text,
            self._last_divergence.normal_context,
            self._last_divergence,
            "normal",
            self.show_normalized.get(),
            self._last_diff_result,
            self._selected_diff_item,
        )
        self._render_context(
            self.abnormal_text,
            self._last_divergence.abnormal_context,
            self._last_divergence,
            "abnormal",
            self.show_normalized.get(),
            self._last_diff_result,
            self._selected_diff_item,
        )

    def _show_all_diffs(self) -> None:
        if self._last_diff_result is None:
            messagebox.showinfo("全相違点", "先に解析を実行してください。")
            return

        window = tk.Toplevel(self.root)
        window.title("全相違点")
        window.geometry("1180x520")
        window.minsize(900, 400)
        window.transient(self.root)

        frame = ttk.Frame(window, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame,
            text=(
                "全相違点一覧（後続の差分を含む）\n"
                "一覧の行を選択すると、正常側・異常側の内容を確認できます。"
            ),
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 8))

        columns = (
            "number",
            "type",
            "normal_line",
            "abnormal_line",
            "normal",
            "abnormal",
        )
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        tree.heading("number", text="No.")
        tree.heading("type", text="種別")
        tree.heading("normal_line", text="正常行")
        tree.heading("abnormal_line", text="異常行")
        tree.heading("normal", text="正常ログ")
        tree.heading("abnormal", text="異常ログ")
        tree.column("number", width=55, anchor=tk.CENTER, stretch=False)
        tree.column("type", width=100, anchor=tk.CENTER, stretch=False)
        tree.column("normal_line", width=70, anchor=tk.CENTER, stretch=False)
        tree.column("abnormal_line", width=70, anchor=tk.CENTER, stretch=False)
        tree.column("normal", width=360)
        tree.column("abnormal", width=360)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)

        type_names = {
            DiffType.MISSING: "欠落 (MISSING)",
            DiffType.ADDED: "追加 (ADDED)",
            DiffType.CHANGED: "変更 (CHANGED)",
        }
        diff_items: dict[str, DiffItem] = {}
        for number, item in enumerate(self._last_diff_result.items, start=1):
            item_id = f"diff-{number}"
            diff_items[item_id] = item
            tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(
                    number,
                    type_names[item.type],
                    item.normal_line.line_number if item.normal_line else "—",
                    item.abnormal_line.line_number if item.abnormal_line else "—",
                    self._diff_line_text(item.normal_line),
                    self._diff_line_text(item.abnormal_line),
                ),
            )
        tree.bind(
            "<<TreeviewSelect>>",
            lambda _event: self._jump_to_selected_diff(tree, diff_items),
        )

        ttk.Label(
            window,
            text=(
                f"欠落: {self._last_diff_result.missing_count} / "
                f"追加: {self._last_diff_result.added_count} / "
                f"変更: {self._last_diff_result.changed_count}"
            ),
        ).pack(anchor=tk.W, padx=12, pady=(8, 12))

    def _jump_to_selected_diff(self, tree: ttk.Treeview, diff_items: dict[str, DiffItem]) -> None:
        selection = tree.selection()
        if not selection:
            return
        item = diff_items.get(selection[0])
        if item is None:
            return
        selected_divergence = DivergenceDetector().detect_item(
            item, self._last_normal_lines, self._last_abnormal_lines
        )
        self._selected_diff_item = item
        self._last_divergence = selected_divergence
        self.summary_title.set("選択中の相違点")
        self._render_summary(
            selected_divergence,
            self._last_diff_result.missing_count if self._last_diff_result else 0,
            self._last_diff_result.added_count if self._last_diff_result else 0,
            self._last_diff_result.changed_count if self._last_diff_result else 0,
        )
        self._render_context(
            self.normal_text,
            selected_divergence.normal_context,
            selected_divergence,
            "normal",
            self.show_normalized.get(),
            self._last_diff_result,
            self._selected_diff_item,
        )
        self._render_context(
            self.abnormal_text,
            selected_divergence.abnormal_context,
            selected_divergence,
            "abnormal",
            self.show_normalized.get(),
            self._last_diff_result,
            self._selected_diff_item,
        )
        self.status_text.set("選択した相違点の位置を表示中")

    def _diff_line_text(self, line: NormalizedLine | None) -> str:
        if line is None:
            return "—"
        return line.normalized_text if self.show_normalized.get() else line.raw_text

    def _show_help(self) -> None:
        help_window = tk.Toplevel(self.root)
        help_window.title("Bug Investigator - 使い方")
        help_window.geometry("720x560")
        help_window.minsize(600, 440)
        help_window.transient(self.root)

        frame = ttk.Frame(help_window, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame,
            text="Bug Investigator の使い方",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor=tk.W, pady=(0, 10))

        text = tk.Text(frame, wrap=tk.WORD, font=("Segoe UI", 10), height=24)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.configure(yscrollcommand=scrollbar.set)
        text.insert(tk.END, self._help_text())
        text.configure(state=tk.DISABLED)

        ttk.Button(help_window, text="閉じる", command=help_window.destroy).pack(
            pady=(0, 12)
        )

    @staticmethod
    def _help_text() -> str:
        return (
            "■ 基本操作\n"
            "1. 「Normal Log」の「選択」を押し、正常時のログファイルを指定します。\n"
            "2. 「Abnormal Log」の「選択」を押し、異常時のログファイルを指定します。\n"
            "3. 「捜査開始」を押すと、ログの読み込み・正規化・比較を実行します。\n\n"
            "■ 画面の見方\n"
            "左側の NORMAL は正常ログ、右側の ABNORMAL は異常ログです。\n"
            "黄色で強調された行、または赤色の相違点マーカーが、最初に挙動が異なった地点です。\n"
            "その前後にあるログを確認し、調査を開始する位置を判断してください。\n\n"
            "■ 行の色の意味\n"
            "黄色: 最初の相違点です。今回の調査で最も優先して確認する場所です。\n"
            "橙色: 最初の相違点より後に見つかった相違点です。\n"
            "赤色: 欠落した行が入るはずだった位置を示します。\n\n"
            "■ 正規化後のログを見る\n"
            "上部メニューの「表示」→「正規化後のログを表示」を選ぶと、比較に使った文字列を表示できます。\n"
            "もう一度選ぶと元ログ表示に戻ります。\n\n"
            "■ 全相違点から該当箇所へ移動する\n"
            "解析後に「全相違点を表示」を開き、一覧の行を選ぶと、その差分の前後ログへ移動します。\n\n"
            "■ 正規化ログを保存する\n"
            "解析後に「ファイル」→「正規化ログを保存」を選び、保存先フォルダを指定します。\n"
            "次の2ファイルが作成されます。\n"
            "  normal.normalized.log（正常ログの正規化結果）\n"
            "  abnormal.normalized.log（異常ログの正規化結果）\n"
            "保存した2ファイルはWinMergeなどで開いて、全体の差分を確認できます。\n"
            "元ログは変更されません。\n\n"
            "「ファイル」→「正規化ログを保存してWinMergeで開く」を選ぶと、保存後にWinMergeを起動できます。\n"
            "WinMergeがインストールされていない場合は、ログ保存のみ実行されます。\n\n"
            "■ 正規化ルールを設定する\n"
            "「設定」→「正規化ルール設定」を選びます。\n"
            "各ルールには、ルール名・正規表現・置換文字列を指定します。\n"
            "例: 正規表現「id=\\d+」、置換文字列「id=<ID>」\n"
            "「追加／更新」で一覧に反映し、「保存」で設定ファイルに保存します。\n"
            "画面下部のプレビュー欄に入力例を入れて「プレビュー」を押すと、現在のルールによる変換結果を確認できます。\n"
            "ルールは一覧の上から順番に適用され、保存後の次回解析から反映されます。\n"
            "Timestampと16進アドレスのルールは初期設定されています。\n"
            "正規表現が不正な場合は保存できません。\n\n"
            "■ 差分の種類\n"
            "MISSING（欠落）\n"
            "  正常ログには存在する行が、異常ログで見つかりません。\n"
            "ADDED（追加）\n"
            "  異常ログにだけ存在する行です。\n"
            "CHANGED（変更）\n"
            "  同じ位置付近で、正常ログと異常ログの内容が異なります。\n\n"
            "■ 正規化について\n"
            "比較前にTimestampや16進アドレスなど、ログごとに変化する値を置き換えます。\n"
            "そのため、表示されるExpectedなどの値には <TIMESTAMP> や <ADDR> が含まれることがあります。\n\n"
            "■ 注意事項\n"
            "このツールは原因を断定するものではありません。FIRST DIVERGENCEは、調査を始める候補地点を示します。\n"
            "元ログは読み取り専用で扱い、変更しません。"
        )

    def _show_about(self) -> None:
        messagebox.showinfo(
            "このツールについて",
            "Bug Investigator\n\n"
            "正常ログと異常ログを比較し、最初の相違点を調査するためのツールです。\n"
            "V1 / Python標準ライブラリ・tkinter",
        )

    def _path_row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        ttk.Label(parent, text=label, width=14).grid(row=row, column=0, sticky=tk.W, pady=3)
        ttk.Entry(parent, textvariable=variable).grid(
            row=row, column=1, sticky=tk.EW, padx=(0, 8), pady=3
        )
        ttk.Button(
            parent,
            text="選択",
            command=lambda: self._choose_file(variable),
        ).grid(row=row, column=2, pady=3)
        parent.columnconfigure(1, weight=1)

    def _choose_file(self, variable: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="ログファイルを選択",
            filetypes=[("Log files", "*.log *.txt"), ("All files", "*.*")],
        )
        if path:
            variable.set(path)
            self._save_last_paths()

    @staticmethod
    def _settings_path() -> Path:
        app_data = os.environ.get("APPDATA")
        base_dir = Path(app_data) if app_data else Path.home() / "AppData" / "Roaming"
        return base_dir / "BugInvestigator" / "settings.json"

    def _load_last_paths(self) -> None:
        try:
            with self._settings_path().open("r", encoding="utf-8") as handle:
                settings = json.load(handle)
            if isinstance(settings, dict):
                normal = settings.get("normal_log")
                abnormal = settings.get("abnormal_log")
                if isinstance(normal, str):
                    self.normal_path.set(normal)
                if isinstance(abnormal, str):
                    self.abnormal_path.set(abnormal)
        except (OSError, json.JSONDecodeError, TypeError):
            # Initial launch or unreadable settings must not block the UI.
            return

    def _save_last_paths(self) -> None:
        try:
            settings_path = self._settings_path()
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            with settings_path.open("w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "normal_log": self.normal_path.get(),
                        "abnormal_log": self.abnormal_path.get(),
                    },
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError:
            # Remembering paths is optional; analysis must continue if it fails.
            return

    @staticmethod
    def _create_log_view(parent: tk.Misc) -> tk.Text:
        widget = tk.Text(
            parent,
            height=12,
            width=45,
            state=tk.DISABLED,
            wrap=tk.NONE,
            font=("Consolas", 10),
        )
        widget.tag_configure("focus", background="#fff2a8", foreground="#000000")
        widget.tag_configure("selected", underline=True)
        widget.tag_configure("difference", background="#ffe0b2", foreground="#7a3e00")
        widget.tag_configure(
            "marker",
            background="#ffd6d6",
            foreground="#b00020",
            font=("Consolas", 10, "bold"),
        )
        return widget

    @staticmethod
    def _add_scrollbar(parent: ttk.Frame, widget: tk.Text) -> None:
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        widget.configure(yscrollcommand=scrollbar.set)

    def run_investigation(self) -> None:
        normal_path = self.normal_path.get().strip()
        abnormal_path = self.abnormal_path.get().strip()
        if not normal_path or not abnormal_path:
            messagebox.showwarning("入力不足", "正常ログと異常ログの両方を指定してください。")
            return
        self._save_last_paths()

        try:
            loader = LogLoader()
            normal_result = loader.load(Path(normal_path), "normal")
            abnormal_result = loader.load(Path(abnormal_path), "abnormal")
            normalizer = Normalizer.default()
            normal_lines = normalizer.normalize(normal_result.lines)
            abnormal_lines = normalizer.normalize(abnormal_result.lines)
            diff_result = DiffEngine().compare(normal_lines, abnormal_lines)
            divergence = DivergenceDetector().detect(
                diff_result, normal_lines, abnormal_lines
            )
        except (LogLoadError, NormalizationConfigError, OSError, ValueError) as exc:
            self.status_text.set("解析に失敗しました")
            messagebox.showerror("解析エラー", str(exc))
            return

        self._last_divergence = divergence
        self.summary_title.set("最初の相違点（FIRST DIVERGENCE）")
        self._last_diff_result = diff_result
        self._last_normal_lines = normal_lines
        self._last_abnormal_lines = abnormal_lines
        self._selected_diff_item = diff_result.items[0] if diff_result.items else None
        self._render_context(
            self.normal_text,
            divergence.normal_context,
            divergence,
            "normal",
            self.show_normalized.get(),
            diff_result,
            self._selected_diff_item,
        )
        self._render_context(
            self.abnormal_text,
            divergence.abnormal_context,
            divergence,
            "abnormal",
            self.show_normalized.get(),
            diff_result,
            self._selected_diff_item,
        )
        self._render_summary(divergence, diff_result.missing_count, diff_result.added_count, diff_result.changed_count)
        warning_count = len(normal_result.warnings) + len(abnormal_result.warnings)
        self.status_text.set(
            "解析完了" + (f"（読み込み警告: {warning_count}件）" if warning_count else "")
        )

    @staticmethod
    def _render_context(
        widget: tk.Text,
        context: ContextWindow,
        divergence: FirstDivergence,
        side: str,
        show_normalized: bool,
        diff_result: DiffResult | None,
        selected_item: DiffItem | None,
    ) -> None:
        first_item = diff_result.items[0] if diff_result and diff_result.items else None
        first_line_numbers = MainWindow._item_line_numbers(first_item, side)
        selected_line_numbers = MainWindow._item_line_numbers(selected_item, side)
        difference_line_numbers = {
            line.line_number
            for item in (diff_result.items if diff_result else [])
            for line in (
                [item.normal_line]
                if side == "normal"
                else [item.abnormal_line]
            )
            if line is not None
        }
        missing_markers: dict[int, tuple[str, bool]] = {}
        if side == "abnormal" and diff_result is not None:
            for item in diff_result.items:
                if item.type is not DiffType.MISSING or item.normal_line is None:
                    continue
                anchor = item.abnormal_index
                if anchor is None:
                    anchor = item.normal_index
                marker_index = next(
                    (
                        index
                        for index, line in enumerate(context.lines)
                        if line.line_number >= (anchor + 1 if anchor is not None else 1)
                    ),
                    len(context.lines),
                )
                missing_markers[marker_index] = (
                    "← 欠落: "
                    + (item.normal_line.normalized_text if show_normalized else item.normal_line.raw_text)
                    + "\n",
                    item == selected_item,
                )
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        for index, line in enumerate(context.lines):
            if index in missing_markers:
                marker_start = widget.index("end-1c")
                marker_text, is_selected = missing_markers[index]
                widget.insert(tk.END, marker_text)
                marker_end = widget.index("end-1c")
                widget.tag_add("marker", marker_start, marker_end)
                if is_selected:
                    widget.tag_add("selected", marker_start, marker_end)
            displayed_text = line.normalized_text if show_normalized else line.raw_text
            text = f"{line.line_number:>6}: {displayed_text}\n"
            start = widget.index("end-1c")
            widget.insert(tk.END, text)
            end = widget.index("end-1c")
            if line.line_number in first_line_numbers:
                widget.tag_add("focus", start, end)
            if line.line_number in selected_line_numbers:
                widget.tag_add("selected", start, end)
            elif line.line_number not in first_line_numbers and line.line_number in difference_line_numbers:
                widget.tag_add("difference", start, end)
        if len(context.lines) in missing_markers:
            marker_start = widget.index("end-1c")
            marker_text, is_selected = missing_markers[len(context.lines)]
            widget.insert(tk.END, marker_text)
            marker_end = widget.index("end-1c")
            widget.tag_add("marker", marker_start, marker_end)
            if is_selected:
                widget.tag_add("selected", marker_start, marker_end)
        widget.configure(state=tk.DISABLED)

    @staticmethod
    def _item_line_numbers(item: DiffItem | None, side: str) -> set[int]:
        if item is None:
            return set()
        line = item.normal_line if side == "normal" else item.abnormal_line
        return {line.line_number} if line is not None else set()

    def _render_summary(self, divergence: FirstDivergence, missing: int, added: int, changed: int) -> None:
        if not divergence.found:
            detail = "判定: 差分なし\n正常ログと異常ログは、正規化後の内容が一致しています。"
        else:
            explanations = {
                "MISSING": "正常ログにある行が、異常ログでは見つかりません。",
                "ADDED": "異常ログにだけ存在する行です。",
                "CHANGED": "同じ位置付近で、正常ログと異常ログの内容が異なります。",
            }
            kind = divergence.type.value
            expected = divergence.expected.raw_text if divergence.expected else "—"
            observed = divergence.observed.raw_text if divergence.observed else "—"
            previous = divergence.previous.raw_text if divergence.previous else "—"
            following = divergence.next.raw_text if divergence.next else "—"
            detail = (
                f"判定: {kind}\n"
                f"{explanations[kind]}\n\n"
                f"正常側で期待される行: {expected}\n"
                f"異常側で見つかった行: {observed}\n"
                f"直前の共通行: {previous}\n"
                f"直後の共通行: {following}\n\n"
                "この結果は原因を断定するものではなく、調査を開始する位置を示します。"
            )
        self.summary_text.set(
            f"{detail}\n\n差分件数　欠落: {missing} / 追加: {added} / 変更: {changed}"
        )


def create_app() -> tk.Tk:
    root = tk.Tk()
    MainWindow(root)
    return root


if __name__ == "__main__":
    create_app().mainloop()
