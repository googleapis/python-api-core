import logging
from unittest import mock

from google.api_core.client_logging import (
    setup_logging,
    initialize_logging,
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

    base_logger.propagate = True
    module_logger.propagate = True

    with mock.patch("os.getenv", return_value="foo.bar"):
        with mock.patch("google.api_core.client_logging._BASE_LOGGER_NAME", "foo"):
            initialize_logging()

    assert base_logger.propagate
    assert module_logger.propagate

    reset_logger("foo")
    reset_logger("foo.bar")
