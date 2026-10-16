"""Central logging setup.

Production code uses this logger. User-facing dialogs stay short; the log
file keeps the traceback.
"""

from __future__ import annotations

import logging
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(log_dir: Path) -> Path:
    """Attach a file handler and a stderr handler to the root logger.

    Returns the log file path.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "sounddeck.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    logging.getLogger("soundboard").setLevel(logging.INFO)
    return log_path
