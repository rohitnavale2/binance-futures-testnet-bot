"""
Central logging configuration for the trading bot.

Design goals:
- Every API request, response, and error is written to a log file (trading_bot.log)
  so that order activity can be audited later.
- Console output stays clean (INFO+ human-readable messages) while the log file
  captures full detail (DEBUG+, including raw request/response payloads).
- Safe to import multiple times (idempotent) - calling get_logger() repeatedly
  will not duplicate handlers.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_FILE = os.path.join(LOG_DIR, "trading_bot.log")

_LOGGER_NAME = "trading_bot"
_configured = False


def _ensure_log_dir() -> None:
    os.makedirs(LOG_DIR, exist_ok=True)


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    """
    Return a configured logger. First call sets up handlers on the root
    'trading_bot' logger; subsequent calls (with the same or child names)
    simply return a logger that propagates to the already-configured handlers.
    """
    global _configured

    root = logging.getLogger(_LOGGER_NAME)

    if not _configured:
        _ensure_log_dir()
        root.setLevel(logging.DEBUG)

        # Rotating file handler - full detail, used for audit trail of
        # requests/responses/errors as required by the task spec.
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)

        # Console handler - concise, human readable, INFO+ only so it isn't noisy.
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(fmt="%(levelname)-8s | %(message)s")
        console_handler.setFormatter(console_formatter)

        root.addHandler(file_handler)
        root.addHandler(console_handler)
        root.propagate = False

        _configured = True

    if name == _LOGGER_NAME:
        return root
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")
