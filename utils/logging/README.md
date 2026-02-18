# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
#
# SPDX-License-Identifier: CC0-1.0

# logging package

This is a tiny project-local logging package.

Usage:

```python
from libraries.logging import get_logger
logger = get_logger('mycomponent')
logger.info('Started')
```

Notes:
- `get_logger(name)` returns a per-name logger that writes logs to `logs/<name>/` by default.
- To run tests or scripts that import `libraries` as a top-level package, run them from the project root (the `TOP` folder) using the module form:

  ```powershell
  cd c:\UNI\TOP
  python -m edv_backend.test_bracket_utils
  ```

- In VS Code, create a launch configuration that sets `cwd` to `${workspaceFolder}` and uses the `module` field if you want module-style execution.
