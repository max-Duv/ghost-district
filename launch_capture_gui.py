from __future__ import annotations

from pathlib import Path

from ghost_district.gui import launch_capture_gui


def main() -> int:
    project_root = Path(__file__).resolve().parent
    return launch_capture_gui(project_root)


if __name__ == "__main__":
    raise SystemExit(main())
