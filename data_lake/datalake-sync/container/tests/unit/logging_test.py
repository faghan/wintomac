import logging
import uuid

from azsync.logging import MemoryHandler


def test_log_content(caplog):
    with caplog.at_level(logging.NOTSET):
        handler = MemoryHandler()
        log = logging.getLogger()
        log.addHandler(handler)

        try:
            assert handler.max_level() == logging.NOTSET

            line_1 = str(uuid.uuid4())
            log.info("%s", line_1)
            assert handler.max_level() == logging.INFO
            assert line_1 in handler.log_content()

            line_2 = str(uuid.uuid4())
            log.debug("%s", line_2)
            assert handler.max_level() == logging.INFO
            assert line_2 in handler.log_content()

            line_3 = str(uuid.uuid4())
            log.error("%s", line_3)
            assert handler.max_level() == logging.ERROR
            assert line_3 in handler.log_content()

        finally:
            log.removeHandler(handler)
