import logging
import logging.config
import os

_LOGGING_CONFIGURED = False


def setup_logging(force: bool = False) -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED and not force:
        return

    log_level = os.getenv("APP_LOG_LEVEL", "DEBUG").upper()

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": (
                        "%(asctime)s | %(levelname)-8s | %(name)s | " "%(message)s"
                    )
                },
                "detailed": {
                    "format": (
                        "%(asctime)s | %(levelname)-8s | %(name)s | "
                        "%(filename)s:%(lineno)d | %(message)s"
                    )
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "detailed",
                    "level": log_level,
                }
            },
            "root": {
                "handlers": ["console"],
                "level": log_level,
            },
            "loggers": {
                "uvicorn": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
                "uvicorn.error": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
                "uvicorn.access": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
            },
        }
    )
    _LOGGING_CONFIGURED = True
