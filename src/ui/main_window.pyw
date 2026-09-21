"""Main tkinter window for the Bug Investigator."""

from __future__ import annotations

import tkinter as tk
import sys
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from ..core.diff_engine import DiffEngine
    from ..core.divergence import ContextWindow, FirstDivergence, DivergenceDetector
    from ..core.log_loader import LogLoadError, LogLoader
    from ..core.normalizer import Normalizer, NormalizationConfigError, NormalizedLine
except ImportError:
    # Support launching this .pyw directly by double-clicking it in Windows.
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from src.core.diff_engine import DiffEngine
    from src.core.divergence import ContextWindow, FirstDivergence, DivergenceDetector
    from src.core.log_loader import LogLoadError, LogLoader
    from src.core.normalizer import Normalizer, NormalizationConfigError, NormalizedLine


class MainWindow:
    """Own the widgets and connect them to the core analysis pipeline."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Bug Investigator")
        self.root.minsize(900, 600)

        self.normal_path = tk.StringVar()
        self.abnormal_path = tk.StringVar()
        self.status_text = tk.StringVar(value="正常ログと異常ログを指定してください")

        self.normal_text: tk.Text
        self.abnormal_text: tk.Text
        self.summary_text = tk.StringVar(value="FIRST DIVERGENCE\n未解析")
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

        summary = ttk.LabelFrame(container, text="最初の相違点（FIRST DIVERGENCE）", padding=8)
        summary.pack(fill=tk.X)
        ttk.Label(
            summary,
            textvariable=self.summary_text,
            justify=tk.LEFT,
            anchor=tk.W,
        ).pack(fill=tk.X)

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)
        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(label="使い方", command=self._show_help)
        help_menu.add_command(label="このツールについて", command=self._show_about)
        menu_bar.add_cascade(label="ヘルプ", menu=help_menu)
        self.root.config(menu=menu_bar)

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

    @staticmethod
    def _choose_file(variable: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="ログファイルを選択",
            filetypes=[("Log files", "*.log *.txt"), ("All files", "*.*")],
        )
        if path:
            variable.set(path)

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

        self._render_context(self.normal_text, divergence.normal_context, divergence, "normal")
        self._render_context(
            self.abnormal_text, divergence.abnormal_context, divergence, "abnormal"
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
    ) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        marker_index = None
        if context.focus_index is None and side == "abnormal" and divergence.observed is None:
            if divergence.next is not None:
                marker_index = next(
                    (
                        index
                        for index, line in enumerate(context.lines)
                        if line.line_number == divergence.next.line_number
                    ),
                    len(context.lines),
                )
            else:
                marker_index = len(context.lines)
        for index, line in enumerate(context.lines):
            if marker_index == index:
                marker_start = widget.index("end-1c")
                widget.insert(tk.END, "← ここが最初の相違点です（本来の行が見つかりません）\n")
                marker_end = widget.index("end-1c")
                widget.tag_add("marker", marker_start, marker_end)
            text = f"{line.line_number:>6}: {line.raw_text}\n"
            start = widget.index("end-1c")
            widget.insert(tk.END, text)
            end = widget.index("end-1c")
            if context.focus_index == index:
                widget.tag_add("focus", start, end)
        if marker_index == len(context.lines):
            marker_start = widget.index("end-1c")
            widget.insert(tk.END, "← ここが最初の相違点です（本来の行が見つかりません）\n")
            marker_end = widget.index("end-1c")
            widget.tag_add("marker", marker_start, marker_end)
        widget.configure(state=tk.DISABLED)

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
