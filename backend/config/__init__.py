"""Configuration module for EspressoBot"""

from .logfire_config import configure_logfire, instrument_app, get_logfire, trace_function

__all__ = ["configure_logfire", "instrument_app", "get_logfire", "trace_function"]
