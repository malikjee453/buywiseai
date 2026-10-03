import logging
import os

def configure_logging(level: str | None = None) -> None:
    selected = (level or os.getenv("BUYWISE_LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(level=getattr(logging, selected, logging.INFO),
                        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
