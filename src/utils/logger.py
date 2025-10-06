"""
Logging utility module with debug-level logging.

Per Constitution Principle VI (Error Resilience) and Clarification Q2,
provides debug-level logging with full details including intermediate states.
"""
import logging
import sys
from pathlib import Path


def setup_logger(
    name: str,
    log_file: Path | None = None,
    level: int = logging.DEBUG
) -> logging.Logger:
    """
    Set up a logger with debug-level logging to both console and file.

    Args:
        name: Logger name (typically __name__ of calling module)
        log_file: Optional file path for log output
        level: Logging level (default: DEBUG)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    # Console handler with INFO level for user-facing output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with DEBUG level for detailed logging
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str, log_file: Path | None = None) -> logging.Logger:
    """
    Get or create a logger instance.

    Args:
        name: Logger name
        log_file: Optional file path for log output

    Returns:
        Logger instance
    """
    return setup_logger(name, log_file)


def log_extraction_error(
    email_id: str,
    error_type: str,
    error_message: str,
    log_file: Path = Path("outputs/extraction_errors.log")
) -> None:
    """
    Log extraction error with structured format.

    Per T038 and Clarification Q2, logs debug-level details for
    extraction errors to dedicated log file.

    Args:
        email_id: ID of email that failed extraction
        error_type: Type of error (rate_limit, timeout, malformed, unknown)
        error_message: Detailed error message
        log_file: Path to extraction errors log (default: outputs/extraction_errors.log)
    """
    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create dedicated logger for extraction errors
    error_logger = setup_logger(
        'extraction_errors',
        log_file,
        level=logging.DEBUG
    )

    # Log with structured format
    error_logger.error(
        f"email_id={email_id} | error_type={error_type} | message={error_message}"
    )
