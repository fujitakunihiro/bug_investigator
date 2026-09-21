"""Application entry point."""

try:
    from .ui.main_window import create_app
except ImportError:  # pragma: no cover - supports direct ``python src/main.py``
    from src.ui.main_window import create_app


def main() -> None:
    app = create_app()
    app.mainloop()


if __name__ == "__main__":
    main()
