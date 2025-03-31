import struct
from datetime import datetime, timedelta, timezone

from django.dispatch import receiver
from django.db.backends.signals import connection_created


# @receiver(connection_created)
# def on_connection_created(sender, connection, **kwargs):
#     if connection.alias == "datawarehouse":
#         connection.connection.add_output_converter(-155, _handle_datetimeoffset)


# def _handle_datetimeoffset(value):
#     # Based on https://winterlimelight.com/2018/07/27/django-ms-sql-datetimeoffset/
#     year, month, day, hour, minute, second, fsecond, tzhour, tzminute = struct.unpack(
#         "<6hI2h", value
#     )

#     return datetime(
#         year=year,
#         month=month,
#         day=day,
#         hour=hour,
#         minute=minute,
#         second=second,
#         # Convert fractional seconds to microseconds (0..999999)
#         microsecond=fsecond // 1000,
#         # UTC offset converted to tzinfo
#         tzinfo=timezone(timedelta(hours=tzhour, minutes=tzminute)),
#     )
