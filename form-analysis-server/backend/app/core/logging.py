"""
Logging configuration for the application.

Provides structured logging with JSON formatting for production
and human-readable format for development.
"""

import logging
import sys
from typing import Any, Dict

import structlog
from structlog.typing import FilteringBoundLogger


def setup_logging(level: str = "INFO", format_type: str = "json") -> None:
    """
    Configure structured logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Format type ("json" for production, "console" for development)
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    
    # Configure processors based on format
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    
    if format_type == "json":
        # Production: JSON formatting
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Development: Human readable
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=True),
        ])
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> FilteringBoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        FilteringBoundLogger: Configured logger instance
        
    Example:
        ```python
        logger = get_logger(__name__)
        logger.info("User logged in", user_id=123, ip="192.168.1.1")
        ```
    """
    return structlog.get_logger(name)