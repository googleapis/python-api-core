import json
import logging
from unittest import mock

from google.api_core.client_logging import (
    setup_logging,
    initialize_logging,
    StructuredLogFormatter,
)


def reset_logger(scope):
    logger = logging.getLogger(scope)
    logger.handlers = []
    logger.setLevel(logging.NOTSET)
    logger.propagate = True


def test_setup_logging_w_no_scopes():
    with mock.patch("google.api_core.client_logging._BASE_LOGGER_NAME", "foo"):
        setup_logging()
        base_logger = logging.getLogger("foo")
        assert base_logger.handlers == []
        assert not base_logger.propagate
        assert base_logger.level == logging.NOTSET

    reset_logger("foo")


def test_setup_logging_w_base_scope():
    with mock.patch("google.api_core.client_logging._BASE_LOGGER_NAME", "foo"):
        setup_logging("foo")
        base_logger = logging.getLogger("foo")
        assert isinstance(base_logger.handlers[0], logging.StreamHandler)
        assert not base_logger.propagate
        assert base_logger.level == logging.DEBUG

    reset_logger("foo")


def test_setup_logging_w_configured_scope():
    with mock.patch("google.api_core.client_logging._BASE_LOGGER_NAME", "foo"):
        base_logger = logging.getLogger("foo")
        base_logger.propagate = False
        setup_logging("foo")
        assert base_logger.handlers == []
        assert not base_logger.propagate
        assert base_logger.level == logging.NOTSET

    reset_logger("foo")


def test_setup_logging_w_module_scope():
    with mock.patch("google.api_core.client_logging._BASE_LOGGER_NAME", "foo"):
        setup_logging("foo.bar")

        base_logger = logging.getLogger("foo")
        assert base_logger.handlers == []
        assert not base_logger.propagate
        assert base_logger.level == logging.NOTSET

        module_logger = logging.getLogger("foo.bar")
        assert isinstance(module_logger.handlers[0], logging.StreamHandler)
        assert not module_logger.propagate
        assert module_logger.level == logging.DEBUG

    reset_logger("foo")
    reset_logger("foo.bar")


def test_setup_logging_w_incorrect_scope():
    with mock.patch("google.api_core.client_logging._BASE_LOGGER_NAME", "foo"):
        setup_logging("abc")

        base_logger = logging.getLogger("foo")
        assert base_logger.handlers == []
        assert not base_logger.propagate
        assert base_logger.level == logging.NOTSET

        # TODO(https://github.com/googleapis/python-api-core/issues/759): update test once we add logic to ignore an incorrect scope.
        logger = logging.getLogger("abc")
        assert isinstance(logger.handlers[0], logging.StreamHandler)
        assert not logger.propagate
        assert logger.level == logging.DEBUG

    reset_logger("foo")
    reset_logger("abc")


def test_initialize_logging():

    with mock.patch("os.getenv", return_value="foo.bar"):
        with mock.patch("google.api_core.client_logging._BASE_LOGGER_NAME", "foo"):
            initialize_logging()

            base_logger = logging.getLogger("foo")
            assert base_logger.handlers == []
            assert not base_logger.propagate
            assert base_logger.level == logging.NOTSET

            module_logger = logging.getLogger("foo.bar")
            assert isinstance(module_logger.handlers[0], logging.StreamHandler)
            assert not module_logger.propagate
            assert module_logger.level == logging.DEBUG

            # Check that `initialize_logging()` is a no-op after the first time by verifying that user-set configs are not modified:
            base_logger.propagate = True
            module_logger.propagate = True

            initialize_logging()

            assert base_logger.propagate
            assert module_logger.propagate

    reset_logger("foo")
    reset_logger("foo.bar")


def test_structured_log_formatter():
    # TODO(https://github.com/googleapis/python-api-core/issues/761): Test additional fields when implemented.
    record = logging.LogRecord(
        name="foo",
        level=logging.DEBUG,
        msg="This is a test message.",
        pathname="foo/bar",
        lineno=25,
        args=None,
        exc_info=None,
    )

    # Extra fields:
    record.rpcName = "bar"

    formatted_msg = StructuredLogFormatter().format(record)
    parsed_msg = json.loads(formatted_msg)

    assert parsed_msg["name"] == "foo"
    assert parsed_msg["severity"] == "DEBUG"
    assert parsed_msg["message"] == "This is a test message."
    assert parsed_msg["rpcName"] == "bar"
