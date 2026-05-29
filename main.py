# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Direct entry point: ``python main.py`` (from the edv/ repo root).

The actual boot sequence lives in :mod:`utils.cli` so the console-script
``edv-backend`` (defined in ``pyproject.toml``) can share it. Keep this
file thin and delegating — anything new belongs in ``utils/cli.py``.

Note on sys.path: ``python main.py`` from cwd=edv has cwd as sys.path[0]
already, so ``utils.cli`` resolves. If invoked as
``python /abs/path/to/edv/main.py`` from a foreign cwd, Python uses the
script's directory as sys.path[0] — which IS the repo root — so the
import still works. No path tweaking needed here.
"""

from utils.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
