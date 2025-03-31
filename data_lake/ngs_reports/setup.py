import os

from setuptools import setup, find_packages


def _get_version():
    """Retrieve version from current install directory."""
    env = {}
    with open(os.path.join("ngsreports", "__init__.py")) as handle:
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
    name="ngs_reports",
    version=_get_version(),
    packages=find_packages(),
    install_requires=_get_requirements(),
    entry_points={"console_scripts": ["ngs_reports=ngsreports.main:entry_point"]},
    zip_safe=False,
    include_package_data=True,
)
