import logging
import json
import re
import os

_LOGGING_INITIALIZED = False

# TODO(<add-link>): Update Request / Response messages.
REQUEST_MESSAGE = "Sending request ..."
RESPONSE_MESSAGE = "Receiving response ..."

# TODO(<add-link>): Update this list to support additional logging fields
_recognized_logging_fields = ["httpRequest", "rpcName", "serviceName"] # Additional fields to be Logged.

def logger_configured(logger):
  return logger.hasHandlers() or logger.level != logging.NOTSET or logger.propagate == False

def initialize_logging():
   global _LOGGING_INITIALIZED
   if _LOGGING_INITIALIZED:
     return
   scopes = os.getenv("GOOGLE_SDK_PYTHON_LOGGING_SCOPE")
   setup_logging(scopes)
   _LOGGING_INITIALIZED = True

def parse_logging_scopes(scopes):
  if not scopes:
     return []
  # TODO(<add-link>): check if the namespace is a valid namespace.
  # TODO(<add-link>): parse a list of namespaces. Current flow expects a single string for now.
  namespaces = [scopes]
  return namespaces

def configure_defaults(logger):
   if not logger_configured(logger):
        console_handler = logging.StreamHandler()
        logger.setLevel("DEBUG")
        logger.propagate = False
        formatter = StructuredLogFormatter()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

def setup_logging(scopes):
    # disable log propagation at base logger level to the root logger only if a base logger is not already configured via code changes.
    base_logger = logging.getLogger("google")
    if not logger_configured(base_logger):
        base_logger.propagate = False
    
    # only returns valid logger scopes (namespaces)
    # this list has at most one element.
    loggers = parse_logging_scopes(scopes) 

    for namespace in loggers:
      # This will either create a module level logger or get the reference of the base logger instantiated above.
      logger = logging.getLogger(namespace)

      # Configure default settings.
      configure_defaults(logger)

class StructuredLogFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            'timestamp': self.formatTime(record),
            'severity': record.levelname,
            'name': record.name,
            'message': record.getMessage(),
        }

        for field_name in _recognized_logging_fields:
            value = getattr(record, field_name, None)
            if value is not None:
                log_obj[field_name] = value
        return json.dumps(log_obj)
