from __future__ import annotations

import sys
from pathlib import Path
from tkinter import Tk

if __package__:
    from .window import MainWindow
else:
    # Permite executar este arquivo diretamente de dentro de bolsa_app/.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from bolsa_app.window import MainWindow


def run() -> int:
    root = Tk()
    MainWindow(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
