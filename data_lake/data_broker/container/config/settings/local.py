from .base import *


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "u$%oq9g0z$@6qs=f*4!9z9bc%8h$t)mhi!c7*j2t$_k^_5@u#m"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


_DEFAULT_LOGGER = {
    "handlers": ["console"],
    "level": "DEBUG",
    "propagate": True,
}

LOGGING["handlers"] = {
    "console": {
        "level": "DEBUG",
        "class": "logging.StreamHandler",
        "formatter": "colored",
    },
}

LOGGING["loggers"] = {
    "data_broker": _DEFAULT_LOGGER,
    "django": _DEFAULT_LOGGER,
    "azure": _DEFAULT_LOGGER,
}

LOGGING["formatters"]["colored"] = {
    "()": "colorlog.ColoredFormatter",
    "format": "{asctime} [{levelname}] {name} {log_color}{message}",
    "style": "{",
    "log_colors": {
        "DEBUG": "cyan",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold_red",
    },
}
