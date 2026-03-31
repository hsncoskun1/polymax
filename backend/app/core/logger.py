import logging
from .config import load_config


def setup_logger(name: str = "polymax") -> logging.Logger:
    cfg = load_config()
    log_cfg = cfg.get("logging", {})

    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(log_cfg.get("format", "%(message)s")))
        logger.addHandler(handler)
    logger.setLevel(log_cfg.get("level", "INFO"))
    return logger
