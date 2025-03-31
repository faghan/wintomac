import os

from pathlib import Path


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = Path(__file__).absolute().parent.parent.parent


# Application definition
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "data_broker.common",
    "data_broker.ngs",
    "data_broker.data_warehouse",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "data_broker.data_warehouse.authentication.ApiKeyAuthentication",
    ],
    # Disables API browser view, which is not usable due to API Key authentication
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer",],
}

# Environmental variables:
# NGS blob storage
AZURE_NGS_ACCOUNT = os.environ["AZURE_NGS_ACCOUNT"]
AZURE_NGS_CONTAINER = os.environ["AZURE_NGS_CONTAINER"]
AZURE_NGS_SECRET = os.environ["AZURE_NGS_SECRET"]

# Proteomics blob storage
AZURE_PROTEOMICS_ACCOUNT = os.environ["AZURE_PROTEOMICS_ACCOUNT"]
AZURE_PROTEOMICS_CONTAINER = os.environ["AZURE_PROTEOMICS_CONTAINER"]
AZURE_PROTEOMICS_SECRET = os.environ["AZURE_PROTEOMICS_SECRET"]

# Data warehouse
AZURE_DWH_DATABASE = os.environ["AZURE_DWH_DATABASE"]
AZURE_DWH_ACCOUNT = os.environ["AZURE_DWH_ACCOUNT"]
AZURE_DWH_LOGIN = os.environ["AZURE_DWH_LOGIN"]
AZURE_DWH_PASSWORD = os.environ["AZURE_DWH_PASSWORD"]
AZURE_DWH_LOGGING = os.environ.get("AZURE_DWH_LOGGING") != "0"


# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),
    },
    "datawarehouse": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": AZURE_DWH_DATABASE,
        "USER": AZURE_DWH_LOGIN,
        "PASSWORD": AZURE_DWH_PASSWORD,
        "HOST": f"{AZURE_DWH_ACCOUNT}.postgres.database.azure.com",
    },
}

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_USER_MODEL = "data_warehouse.BenchlingUser"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",},
]


# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} [{levelname}] {name} {message}",
            "style": "{",
        },
    },
}
