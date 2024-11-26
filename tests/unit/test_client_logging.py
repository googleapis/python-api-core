import logging
import pytest

from google.api_core.client_logging import setup_logging

# TODO: We should not be testing against the "google" logger
# and should mock `base_logger` instead.

def reset_logger(scope):
    logger = logging.getLogger(scope)
    logger.handlers = []
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    
def test_setup_logging_w_no_scopes():
    setup_logging()
    base_logger = logging.getLogger("google")
    assert base_logger.handlers == []
    assert base_logger.propagate == False
    assert base_logger.level == logging.NOTSET

    reset_logger("google")


def test_setup_logging_w_base_scope():
    setup_logging("google")
    base_logger = logging.getLogger("google")
    assert isinstance(base_logger.handlers[0], logging.StreamHandler)
    assert base_logger.propagate == False
    assert base_logger.level == logging.DEBUG

    reset_logger("google")

def test_setup_logging_w_module_scope():
    setup_logging("google.foo")
    
    base_logger = logging.getLogger("google")
    assert base_logger.handlers == []
    assert base_logger.propagate == False
    assert base_logger.level == logging.NOTSET

    module_logger = logging.getLogger("google.foo")
    assert isinstance(module_logger.handlers[0], logging.StreamHandler)
    assert module_logger.propagate == False
    assert module_logger.level == logging.DEBUG


    reset_logger("google")
    reset_logger("google.foo")

def test_setup_logging_w_incorrect_scope():
    setup_logging("foo")
    
    base_logger = logging.getLogger("google")
    assert base_logger.handlers == []
    assert base_logger.propagate == False
    assert base_logger.level == logging.NOTSET

    # TODO(https://github.com/googleapis/python-api-core/issues/759): update test once we add logic to ignore an incorrect scope.
    logger = logging.getLogger("foo")
    assert isinstance(logger.handlers[0], logging.StreamHandler)
    assert logger.propagate == False
    assert logger.level == logging.DEBUG

    reset_logger("google")
    reset_logger("foo")
