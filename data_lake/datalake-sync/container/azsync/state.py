import json
import logging
import os
import time
import datetime

from pathlib import Path

from azsync.fileutils import PartialStats, iglob_folder


def _get_value(name):
    def _flag_getter(self):
        value = self._data.get(name)
        if value is None:
            return None

        return datetime.datetime.fromtimestamp(value)

    return property(_flag_getter)


def _get_boolean_value(name):
    def _flag_getter(self):
        return self._data.get(name) is not None

    return property(_flag_getter)


def _update_timestamp(name, overwrite=False):
    def _flag_setter(self):
        if overwrite or self._data.get(name) is None:
            self._data[name] = datetime.datetime.utcnow().timestamp()
            self._parent._dirty = True

    return _flag_setter


class StateError(RuntimeError):
    pass


class _StateBase:
    __slots__ = ["_parent", "_data"]

    def __init__(self, data, parent):
        self._data = data
        self._parent = parent


class _MetabolomicsState(_StateBase):
    observed = _get_value("observed")


class _NGSState(_StateBase):
    observed = _get_value("observed")

    is_flag_synced = _get_boolean_value("flag")
    is_data_synced = _get_boolean_value("data")
    is_sheet_synced = _get_boolean_value("sheet")

    set_flag_synced = _update_timestamp("flag")
    set_data_synced = _update_timestamp("data")
    set_sheet_synced = _update_timestamp("sheet")

    warned = _get_value("warned")
    set_warned = _update_timestamp("warned", overwrite=True)

    @property
    def is_synced(self):
        return self.is_flag_synced and self.is_data_synced and self.is_sheet_synced


class _ProteomicsState(_StateBase):
    observed = _get_value("observed")

    is_flag_synced = _get_boolean_value("flag")
    are_results_synced = _get_boolean_value("results")
    is_metadata_synced = _get_boolean_value("metadata")

    set_flag_synced = _update_timestamp("flag")
    set_results_synced = _update_timestamp("results")
    set_metadata_synced = _update_timestamp("metadata")


class PersistentState:
    def __init__(self, filepath, max_backups=10):
        if not isinstance(max_backups, int) and max_backups >= 0:
            raise ValueError(f"max_backups must be >= 0, not {max_backups!r}")
        self._max_backups = max_backups
        self._dirty = False

        logger = logging.getLogger(__name__)
        logging.debug("reading state from %r", filepath)

        try:
            self._filepath = Path(filepath)
            with self._filepath.open() as handle:
                self._data = json.load(handle)
        except FileNotFoundError:
            logger.info("statefile '%s' not found; creating new state", self._filepath)
            self._data = {}
        except Exception as error:
            logger.error("error while reading statefile: %r", error)
            raise

    def save(self, force=False):
        if self._dirty or force:
            logger = logging.getLogger(__name__)
            logging.info("writing state to %r", self._filepath)

            data = json.dumps(self._data)

            filepath = self._filepath
            folder = filepath.parent
            folder.mkdir(parents=True, exist_ok=True)

            # Create hard-link to current file, allowing safe replacement
            while True:
                backup = _add_timestamp(filepath)
                try:
                    os.link(filepath, backup)
                    break
                except FileExistsError:
                    pass  # Possible race-condition?
                except FileNotFoundError:
                    break  # No previous state file

            # Write current data to temporary file
            while True:
                replacement = _add_timestamp(filepath, "_new")
                try:
                    with replacement.open("x") as handle:
                        handle.write(data)
                        handle.flush()
                        break
                except FileExistsError:
                    pass

            # Finally, replace original file with new content
            replacement.replace(filepath)

            # Clean up old backups
            backups = iglob_folder(filepath.parent, filepath.name + ".[0-9]*")
            for backup in backups[: -self._max_backups]:
                logger.debug("removing backup file %r", backups[0])
                backup.unlink()

            self._dirty = False

    def get_metabolomics_run(self, name):
        runs = self._data.setdefault("metabolomics", {})
        if name not in runs:
            runs[name] = {"observed": datetime.datetime.utcnow().timestamp()}
            self._dirty = True

        return _MetabolomicsState(data=runs[name], parent=self)

    def get_ngs_run(self, name):
        runs = self._data.setdefault("ngs", {})
        if name not in runs:
            runs[name] = {"observed": datetime.datetime.utcnow().timestamp()}
            self._dirty = True

        return _NGSState(data=runs[name], parent=self)

    def get_ngs_runs(self):
        for key, value in self._data.get("ngs", {}).items():
            yield key, _NGSState(data=value, parent=self)

    def get_proteomics_run(self, name):
        runs = self._data.setdefault("proteomics", {})
        if name not in runs:
            runs[name] = {"observed": datetime.datetime.utcnow().timestamp()}
            self._dirty = True

        return _ProteomicsState(data=runs[name], parent=self)

    def get_file_stats(self, filepath):
        if not isinstance(filepath, (Path, str)):
            raise ValueError(f"expected Path or str, not {filepath!r}")

        stats = self._data.get("stats", {})
        item = stats.get(str(filepath))

        return None if item is None else PartialStats.from_json(item)

    def set_file_stats(self, filepath, value):
        if not isinstance(filepath, (Path, str)):
            raise ValueError(f"expected Path or str, not {filepath!r}")
        elif not isinstance(value, PartialStats):
            raise ValueError(f"expected PartialStats, not {value!r}")

        stats = self._data.setdefault("stats", {})
        stats[str(filepath)] = value.to_json()
        self._dirty = True

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.save()


def _add_timestamp(filepath, suffix=""):
    return filepath.parent / f"{filepath.name}.{int(time.time() * 1e6)}{suffix}"
