from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from flask import g, has_request_context, request


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = "-"
        record.remote_addr = "-"
        record.request_path = "-"
        record.request_method = "-"
        record.actor = "-"

        if has_request_context():
            record.request_id = getattr(g, "request_id", "-")
            record.remote_addr = request.remote_addr or "-"
            record.request_path = request.path or "-"
            record.request_method = request.method or "-"
            user = getattr(g, "user", None)
            record.actor = user["username"] if user else "anonymous"
        return True


def configure_logging(app) -> None:
    level_name = app.config.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    if app.config.get("TESTING"):
        app.logger.setLevel(level)
        return

    log_dir = app.config["LOG_DIR"]
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "noc-console.log"

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | request_id=%(request_id)s | actor=%(actor)s | "
        "%(request_method)s %(request_path)s | remote=%(remote_addr)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    context_filter = RequestContextFilter()

    if not any(isinstance(handler, RotatingFileHandler) for handler in app.logger.handlers):
        file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        file_handler.addFilter(context_filter)
        app.logger.addHandler(file_handler)

    for handler in app.logger.handlers:
        handler.addFilter(context_filter)

    app.logger.setLevel(level)
    app.logger.propagate = False
