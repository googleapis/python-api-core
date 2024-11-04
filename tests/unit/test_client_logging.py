import logging
import pytest

from google.api_core.client_logging import BaseLogger


def test_base_logger(caplog):

    logger = BaseLogger().get_logger()

    with caplog.at_level(logging.INFO, logger="google"):
        logger.info("This is a test message.")

    assert "This is a test message." in caplog.text
    assert caplog.records[0].name == "google"
    assert caplog.records[0].levelname == "INFO"
    assert caplog.records[0].message == "This is a test message."
