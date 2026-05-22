# SPDX-FileCopyrightText: 2026 TOP Team Combat Control
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression: utils.logging.Logger must accept stdlib-style exc_info / *args
kwargs so that `logger.error(msg, exc_info=True)` does not raise TypeError.

Tracked in WSP/OPEN_ITEMS.md ("EDV-Pipeline-Bug"); the previous custom-logger
signature only accepted `message`, causing 20+ call sites in edv/frontend/
to silently fail and swallow the original exception.
"""
import os
import sys
import tempfile

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from utils.logging.logger import Logger  # noqa: E402


@pytest.fixture
def logger(tmp_path):
    return Logger(log_dir=str(tmp_path))


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def test_error_accepts_exc_info_true_inside_except(logger):
    try:
        raise ValueError("simulated")
    except ValueError:
        # Must not raise; must serialize the traceback.
        logger.error("boom", exc_info=True)
    contents = _read(logger.error_log)
    assert "boom" in contents
    assert "ValueError: simulated" in contents
    assert "Traceback" in contents


def test_error_accepts_exc_info_exception_instance(logger):
    try:
        raise RuntimeError("oops")
    except RuntimeError as e:
        logger.error("bad", exc_info=e)
    contents = _read(logger.error_log)
    assert "RuntimeError: oops" in contents


def test_error_exc_info_outside_except_is_noop(logger):
    # No active exception → exc_info=True must not crash, must not append a TB.
    logger.error("standalone", exc_info=True)
    contents = _read(logger.error_log)
    assert "standalone" in contents
    assert "Traceback" not in contents


def test_warning_info_debug_accept_exc_info(logger):
    try:
        raise KeyError("k")
    except KeyError:
        logger.warning("w", exc_info=True)
        logger.info("i", exc_info=True)
        logger.debug("d", exc_info=True)
    assert "KeyError" in _read(logger.warning_log)
    assert "KeyError" in _read(logger.info_log)
    assert "KeyError" in _read(logger.debug_log)


def test_stdlib_style_args_substitution(logger):
    logger.info("hello %s = %d", "x", 42)
    assert "hello x = 42" in _read(logger.info_log)


def test_malformed_args_does_not_crash(logger):
    # Mismatched %-specifier should fall back to repr instead of raising.
    logger.info("only one %s here", "a", "b")
    assert "only one" in _read(logger.info_log)


def test_unknown_kwargs_are_ignored(logger):
    # stdlib accepts stack_info, stacklevel, extra — we silently ignore them.
    logger.error("compat", stack_info=False, stacklevel=2, extra={"ctx": "x"})
    assert "compat" in _read(logger.error_log)
