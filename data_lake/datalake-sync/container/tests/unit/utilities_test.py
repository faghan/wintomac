from pathlib import Path

from azsync.utilities import urljoin, urlquote


def test_urljoin():
    assert urljoin() == ""
    assert urljoin("www.foo.com", "bar") == "www.foo.com/bar"
    assert urljoin("www.foo.com/", "bar") == "www.foo.com/bar"
    assert urljoin("www.foo.com/", "/bar") == "www.foo.com/bar"
    assert urljoin("www.foo.com", "/bar") == "www.foo.com/bar"
    assert urljoin("www.foo.com//", "bar") == "www.foo.com/bar"
    assert urljoin("www.foo.com", "bar", "zod") == "www.foo.com/bar/zod"
    assert urljoin("/", "") == "/"


def test_urljoin__paths():
    assert urljoin(Path("www.foo.com"), "bar") == "www.foo.com/bar"
    assert urljoin("www.foo.com", Path("bar")) == "www.foo.com/bar"
    assert urljoin(Path("www.foo.com"), Path("bar")) == "www.foo.com/bar"


def test_urlquote__simple_values():
    assert urlquote("1234") == "1234"
    assert urlquote(b"1234") == "1234"
    assert urlquote(Path("1234")) == "1234"


def test_urlquote__paths():
    assert urlquote("1234/foobar.txt") == "1234/foobar.txt"
    assert urlquote(b"1234/foobar.txt") == "1234/foobar.txt"
    assert urlquote(Path("1234/foobar.txt")) == "1234/foobar.txt"


def test_urlquote__unsafe_characters():
    assert urlquote("1234/#foobar?txt") == "1234/%23foobar%3Ftxt"
    assert urlquote(b"1234/#foobar?txt") == "1234/%23foobar%3Ftxt"
    assert urlquote(Path("1234/#foobar?txt")) == "1234/%23foobar%3Ftxt"
