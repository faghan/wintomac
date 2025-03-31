import datetime
import os

from .base import *

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

DEBUG = False

ALLOWED_HOSTS = ["cfbdatabroker.northeurope.cloudapp.azure.com"]

# Probably not needed, but just in case
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True


_DEFAULT_LOGGER = {
    "handlers": ["console", "file"],
    "level": "INFO",
    "propagate": True,
}

LOGGING["handlers"] = {
    "console": {
        "level": "INFO",
        "class": "logging.StreamHandler",
        "formatter": "verbose",
    },
    "file": {
        "level": "INFO",
        "class": "logging.FileHandler",
        "filename": datetime.datetime.now().strftime("/var/log/django/%Y%m%d.log"),
        "formatter": "verbose",
    },
}

LOGGING["loggers"] = {
    "data_broker": _DEFAULT_LOGGER,
    "django": _DEFAULT_LOGGER,
}
