import os

from setuptools import setup, find_packages


def _get_version():
    """Retrieve version from current install directory."""
    env = {}
    with open(os.path.join("pasx_savvy_sync", "__init__.py")) as handle:
        exec(handle.read(), env)

    return env["__version__"]


def _get_requirements():
    lines = []
    with open("requirements.txt") as handle:
        for line in handle:
            line = line.strip()
            if line:
                lines.append(line)

    return lines


setup(
    name="pasx_savvy_sync",
    version=_get_version(),
    packages=find_packages(),
    install_requires=_get_requirements(),
    entry_points={"console_scripts": ["pasx_savvy_sync=pasx_savvy_sync.main:entry_point"]},
    zip_safe=False,
    include_package_data=True,
)
