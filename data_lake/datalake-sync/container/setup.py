from pathlib import Path
from setuptools import setup, find_packages

SRC_DIR = Path(__file__).parent


def _get_version():
    """Retrieve version from current install directory."""
    env = {}
    with (SRC_DIR / "azsync" / "__init__.py").open() as handle:
        exec(handle.read(), env)

    return env["__version__"]


def _get_requirements():
    lines = []
    with (SRC_DIR / "requirements.txt").open() as handle:
        for line in handle:
            line = line.strip()
            if line:
                lines.append(line)

    return lines


setup(
    name="sync_to_azure",
    version=_get_version(),
    packages=find_packages(),
    install_requires=_get_requirements(),
    entry_points={"console_scripts": ["sync_to_azure=azsync.main:entry_point"]},
    zip_safe=False,
    include_package_data=True,
)
