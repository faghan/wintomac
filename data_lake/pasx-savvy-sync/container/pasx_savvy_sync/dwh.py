import datetime
import json
import logging
import time
import uuid

import psycopg2
from psycopg2 import extras

_SUCCESS = 2
_FAILED = 3

# Maximum number of queries to bundle for an 'executemany' operation
_MAX_BULK_QUERIES = 100

_STG_SCHEMA = "stg_pasx_savvy"

class Client:
    """
    DWH client implementing bulk processing of identical SQL queries.
    """

    def __init__(self, server, database, username, password):
        self._cnxn = None
        self._cursor = None
        self.run_id = None
        self.pipeline = None

        self.server = server
        self.database = database
        self.username = username
        self.password = password

        self._log = logging.getLogger(__name__)

    def update_users(self, users):
        with _LogLoad(self, f"{_STG_SCHEMA}.\"user\"") as table:
            table.truncate()

            for user in users:
                table.insert(
                    id=user["id"],
                    username=user["username"],
                    first_name=user["firstName"],
                    last_name=user["lastName"],
                    dw_pipeline_run_id=self.run_id,
                )

        self._log.info("finalizing table load %r", table.table)
        self._execute(f"CALL {_STG_SCHEMA}.load_user('{self.pipeline}','{self.run_id}', FALSE);")

    def update_unit_operations(self, unit_operations):
        with _LogLoad(self, f"{_STG_SCHEMA}.unit_operation") as table:
            table.truncate()

            for unit_operation in unit_operations:
                table.insert(
                    id=unit_operation["id"],
                    type=unit_operation["type"],
                    name=unit_operation["name"],
                    created_by=unit_operation["createdBy"],
                    dw_pipeline_run_id=self.run_id,
                )

        self._log.info("finalizing table load %r", table.table)
        self._execute(f"CALL {_STG_SCHEMA}.load_unit_operation('{self.pipeline}','{self.run_id}', FALSE);")

    def update_batches(self, batches):
        with _LogLoad(self, f"{_STG_SCHEMA}.batch") as table:
            table.truncate()

            for batch in batches:
                table.insert(
                    id=batch["id"],
                    name=batch["name"],
                    description=batch["description"],
                    realtime=batch["realtime"],
                    meta=batch["meta"],
                    creation_time=_isodatetime(batch["creationTime"]),
                    modification_time=_isodatetime(batch["modificationTime"]),
                    batch_start=_isodatetime(batch["batchStart"]),
                    batch_end=_isodatetime(batch["batchEnd"]),
                    first_timestamp_for_plotting=_isodatetime(
                        batch["firstTimestampForPlotting"]
                    ),
                    first_timestamp=_isodatetime(batch["firstTimestamp"]),
                    last_timestamp=_isodatetime(batch["lastTimestamp"]),
                    recipe=batch["recipe"],
                    created_by=batch["createdBy"],
                    recipe_id=batch["recipeId"],
                    precursors=batch["precursors"],
                    unit_operation=batch["unitOperation"],
                    events=batch["events"],
                    phases=batch["phases"],
                    start_of=batch["startOf"],
                    sharable=batch["sharable"],
                    deletable=batch["deletable"],
                    dw_pipeline_run_id=self.run_id,
                )

        self._log.info("finalizing table load %r", table.table)
        self._execute(f"CALL {_STG_SCHEMA}.load_batch('{self.pipeline}','{self.run_id}', FALSE);")
        self._execute(f"CALL {_STG_SCHEMA}.load_batch_phase('{self.pipeline}','{self.run_id}', FALSE);")
        self._execute(f"CALL {_STG_SCHEMA}.load_batch_event('{self.pipeline}','{self.run_id}', FALSE);")

    def update_variable_details(self, variable_details):
        with _LogLoad(self, f"{_STG_SCHEMA}.\"variable\"") as table:
            table.truncate()

            for details in variable_details:
                table.insert(
                    id=details["id"],
                    batch_id=details["batch"],
                    data=details["data"],
                    timestamps=details["timestamps"],
                    errors=details["errors"],
                    image=details["image"],
                    columns_name=details["columnsName"],
                    columns_unit=details["columnsUnit"],
                    columns=details["columns"],
                    index_name=details["indexName"],
                    index_unit=details["indexUnit"],
                    index=details["index"],
                    data_name=details["dataName"],
                    data_unit=details["dataUnit"],
                    replicate_measure=details["replicateMeasure"],
                    name=details["name"],
                    unit=details["unit"],
                    data_format=details["dataFormat"],
                    description=details["description"],
                    creation_time=_isodatetime(details["creationTime"]),
                    modification_time=_isodatetime(details["modificationTime"]),
                    data_file=details["dataFile"],
                    raw_data=details["rawData"],
                    online_data=details["onlineData"],
                    source=details["source"],
                    meta=details["meta"],
                    is_setpoint=details["isSetpoint"],
                    setpoint_sent=details["setpointSent"],
                    dw_pipeline_run_id=self.run_id,
                )

        self._log.info("finalizing table load %r", table.table)
        self._execute(f"CALL {_STG_SCHEMA}.load_variable('{self.pipeline}','{self.run_id}', FALSE);")

    def _execute(self, query, *args):
        stripped_query = " ".join(line.strip() for line in query.split("\n"))
        log = logging.getLogger(__name__)
        log.debug("executing %r with args %r", stripped_query, args)

        try:
            self._cursor.execute(query, *args)
        except Exception as error:
            log.error("error %r while executing query %r", error, stripped_query)
            raise

    def _executemany(self, query, args):
        stripped_query = " ".join(line.strip() for line in query.split("\n"))
        log = logging.getLogger(__name__)
        log.debug("executing %r for %i sets of args", stripped_query, len(args))

        try:
            start = time.time()
            psycopg2.extras.execute_batch(self._cursor, query, args, page_size=100)
            log.debug("executebatch took %.2f seconds", time.time() - start)
        except Exception as error:
            log.error("error %r while executing query %r", error, stripped_query)
            raise

    def _connect(self):
        log = logging.getLogger(__name__)
        log.info(
            f"connecting to server={self.server}, database={self.database}, username={self.username}, password={{password}}"
        )

        self._cnxn = psycopg2.connect(
            host=self.server,
            database=self.database,
            user=self.username,
            password=self.password,
            sslmode="require",
        )

        self._cnxn.autocommit = True

        self._cursor = self._cnxn.cursor()

    def __enter__(self):
        self.run_id = str(uuid.uuid4())
        self.pipeline = "pasx-savvy-data-sync"

        self._connect()

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._cnxn.close()


class _LogLoad:
    """
    Class encapulating the task of updating a table from a data-set. The class handles
    bulk inserts by automatically grouping series of idential queries and executing
    those using the `Client.executemany` function.

    The class should always be used in a `with` statement. This ensures that stored
    proceedurs `log_load_start` and `log_load_finish` are called as required and that
    cached quries are flushed on exit.

    Basic usage:

        with _LogLoad(dwh_client, "[my].[table]") as table:
            table.truncate()

            for row in data:
                table.insert(key1=row["keya"], key2=row["keyb"], ...)
    """

    def __init__(self, client, table):
        if client.run_id is None:
            raise RuntimeError("must use __enter__ with client")

        self._log = logging.getLogger(__name__)

        self.client = client
        self.table = table
        self.no_of_inserts = 0
        self.no_of_updates = 0
        self.no_of_deletes = 0

        self._bulk_operation = None
        self._bulk_query = None
        self._bulk_params = []

    def truncate(self):
        """Truncate the target table, removing all existing rows."""
        self._log.debug("truncating table %r", self.table)

        self.client._execute(f"""TRUNCATE TABLE {self.table}""")

    def insert(self, **fields):
        """
        Helper function to insert rows. Automatically generates a query that sets
        fields based on the key/value pairs provided as arguments:

        >>> table.insert(column1=value1, column2=value2, ...)
        """
        keys = ", ".join(f"{name}" for name in fields)
        values = "%" +  ", %".join("s" * len(fields))

        query = f"INSERT INTO {self.table} ({keys}) VALUES ({values});"
        values = [
            json.dumps(value) if isinstance(value, (dict, list)) else value
            for value in fields.values()
        ]
        self._execute(query, values, "INSERT")

    def _execute(self, query, params, operation):
        if operation not in ("INSERT", "UPDATE", "DELETE"):
            raise ValueError(operation)
        elif query != self._bulk_query:
            self.flush(True)

        self._bulk_operation = operation
        self._bulk_query = query
        self._bulk_params.append(params)
        self.flush()

    def flush(self, force=False):
        if (force and self._bulk_params) or len(self._bulk_params) >= _MAX_BULK_QUERIES:
            self.client._executemany(self._bulk_query, self._bulk_params)

            if self._bulk_operation == "INSERT":
                self.no_of_inserts += len(self._bulk_params)
            elif self._bulk_operation == "UPDATE":
                self.no_of_updates += len(self._bulk_params)
            elif self._bulk_operation == "DELETE":
                self.no_of_deletes += len(self._bulk_params)
            else:
                raise NotImplementedError(self._bulk_operation)

            self._bulk_params = []

    def __enter__(self):
        self._log.info("starting to load table %r", self.table)
        self.client._execute(f"CALL log.job_begin('{self.client.run_id}', '{self.client.pipeline}', 'insert_{self.table}', False);")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.flush(True)
        except Exception:
            exc_type = True
            raise
        finally:
            status_code = _FAILED if exc_type else _SUCCESS

            log_func = self._log.error if exc_type else self._log.info
            log_func("finished to loading table %r (%s)", self.table, status_code)
            self.client._execute(f"CALL log.job_end('{self.client.run_id}','insert_{self.table}', {self.no_of_inserts}, {self.no_of_updates}, {self.no_of_deletes});")


def _isodatetime(value):
    """Parse ISO date-time strings for use in `executemany` queries.

    Special handling is needed since values may be None or may use Z (Zulu = UTC) to
    indicate the timezone, which is not supported by `datetime.fromisoformat`.
    """
    if value is None:
        return None
    elif value.endswith("Z"):
        value = value[:-1] + "+00:00"

    return datetime.datetime.fromisoformat(value)
