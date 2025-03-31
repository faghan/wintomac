#!/usr/bin/env python3
import logging
import re

from django.core.management.base import BaseCommand
from django.db import connections


def _pop_bool(row, key):
    return row.pop(key) == "YES"


class Field:
    def __init__(self, row, klass="Unknown"):
        table = []
        table.extend(field.title() for field in row.pop("TABLE_SCHEMA").split("_"))
        table.extend(field.title() for field in row.pop("TABLE_NAME").split("_"))
        row.pop("TABLE_CATALOG")  # Not used

        self.table = "".join(table)
        self.name = row.pop("COLUMN_NAME")
        self.position = int(row.pop("ORDINAL_POSITION"))
        self.klass = klass
        self.args = []
        self.kwargs = {}

        if _pop_bool(row, "IS_NULLABLE"):
            self.kwargs["null"] = True

        if "__" in self.name:
            # Django requires that fields do not contain '__'
            self.kwargs["db_column"] = self.name
            self.name = self.name.replace("__", "_")

    def __repr__(self):
        args = ", ".join(map(repr, self.args))
        kwargs = ", ".join(f"{key}={value!r}" for key, value in self.kwargs.items())
        sep = ", " if (args and kwargs) else ""

        return f"{self.name} = models.{self.klass}({args}{sep}{kwargs})"


class NVarCharField(Field):
    def __init__(self, row):
        super().__init__(row, "CharField")

        self.kwargs["max_length"] = int(row.pop("CHARACTER_MAXIMUM_LENGTH"))
        if self.kwargs["max_length"] == -1:
            self.kwargs.pop("max_length")
            self.klass = "TextField"

        row.pop("CHARACTER_OCTET_LENGTH")  # Not used
        row.pop("CHARACTER_SET_NAME")  # Not used
        row.pop("COLLATION_NAME")  # Not used


class IntField(Field):
    def __init__(self, row):
        super().__init__(row, "IntegerField")

        row.pop("NUMERIC_PRECISION")  # Not used
        row.pop("NUMERIC_PRECISION_RADIX")  # Not used
        row.pop("NUMERIC_SCALE")  # Not used


class BitField(Field):
    def __init__(self, row):
        super().__init__(row, "BooleanField")


class FloatField(Field):
    def __init__(self, row):
        super().__init__(row, "FloatField")

        row.pop("NUMERIC_PRECISION")  # Not used
        row.pop("NUMERIC_PRECISION_RADIX")  # Not used


class DateTime2Field(Field):
    def __init__(self, row):
        super().__init__(row, "DateTimeField")

        row.pop("DATETIME_PRECISION")  # Not used


class DateField(Field):
    def __init__(self, row):
        super().__init__(row, "DateField")

        row.pop("DATETIME_PRECISION")  # Not used


class PrimaryKeyField(IntField):
    def __init__(self, row):
        super().__init__(row)

        self.kwargs["primary_key"] = True


_FIELD_TYPES = {
    "[primary_key]": PrimaryKeyField,
    "bit": BitField,
    "date": DateField,
    "datetime2": DateTime2Field,
    "float": FloatField,
    "int": IntField,
    "nvarchar": NVarCharField,
    "smallint": IntField,
}


def row_to_field(row):
    log = logging.getLogger(__name__)
    data_type = row.pop("DATA_TYPE")
    if data_type == "int" and row.get("COLUMN_NAME") == "dw_id":
        data_type = "[primary_key]"

    field_type = _FIELD_TYPES.get(data_type)
    if field_type is None:
        log.warning("Unknown data_type %r for %r", data_type, row["COLUMN_NAME"])
        field_type = Field

    field = field_type(row)
    for key, value in sorted(row.items()):
        log.warning("Unused property for field %s: %s=%r", field.name, key, value)

    return field


_SCHEMA_QUERY = (
    "SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s;"
)


class Command(BaseCommand):
    help = "Construct Django model for data-warehouse tabel"

    def add_arguments(self, parser):
        parser.add_argument("schema", help="Table schema, e.g. 'lims_biosustain_raw'")
        parser.add_argument(
            "name", help="Table name, e.g. 'sequencing_submission_sample'"
        )

    def handle(self, schema, name, **options):
        model_name = []
        model_name.extend(schema.split("_"))
        model_name.extend(name.split("_"))
        model_name = "".join(field.title() for field in model_name)

        with connections["datawarehouse"].cursor() as cursor:
            cursor.execute(_SCHEMA_QUERY, [schema, name])

            fields = []
            columns = [info[0] for info in cursor.description]

            for row in cursor.fetchall():
                fields.append(
                    row_to_field(
                        {
                            key: value
                            for key, value in zip(columns, row)
                            if value is not None
                        }
                    )
                )

        print(f"class {model_name}(DataWarehouseModel):")
        print("    class Meta:")
        print(f'        db_table = "[{schema}].[{name}]"')
        print()

        fields_names = set(field.name for field in fields)
        for field in sorted(fields, key=lambda it: it.position):
            name = field.name
            comment = ""
            # ID columns are disabled by default; to be enabled manually via ForeignKeys
            if f"dw_{name}" in fields_names or re.match("^dw_.+_id$", name):
                comment = "# "

            print(f"    {comment}{field}")

        print()

        return 0
