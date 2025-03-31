from marshmallow import Schema, fields


class AclChangeRecursiveResponseCounters(Schema):
    directories_successful = fields.Int()
    files_successful = fields.Int()
    failure_count = fields.Int()


class AclChangeRecursiveResponse(Schema):
    continuation = fields.Str(allow_none=True)
    counters = fields.Nested(AclChangeRecursiveResponseCounters())


class AclChangeResponse(Schema):
    date = fields.Date()
    etag = fields.Str()
    last_modified = fields.Date()
    client_request_id = fields.Str()
    request_id = fields.Str()
    version = fields.Str()
