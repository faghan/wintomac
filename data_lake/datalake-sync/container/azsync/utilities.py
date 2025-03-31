import urllib.parse
import pathlib


def urljoin(*args):
    """Simple join for URL components, stripping excess '/'s"""
    result = "/".join(filter(None, (str(value).strip("/") for value in args)))
    if not result and any(("/" in value) for value in args):
        return "/"

    return result


def urlquote(value):
    if isinstance(value, pathlib.Path):
        value = str(value)

    return urllib.parse.quote(value)
