"""Standard logging configured with UTC timestamps."""

import logging
import time


def configure_logging(level: str = "INFO") -> None:
    """Install the application's UTC console formatter."""
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    formatter.converter = time.gmtime
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logging.basicConfig(level=level, handlers=[handler])
