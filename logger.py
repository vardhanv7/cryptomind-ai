"""
CryptoMind AI - Logger Module
Handles all logging to file and terminal.
"""

import logging
import os
from datetime import datetime


def setup_logger():
    """
    Set up the logger that writes to both file and terminal.
    Call this once at the start of the program.
    """
    # Create logs folder if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    # Create logger
    logger = logging.getLogger("CryptoMind")
    logger.setLevel(logging.DEBUG)

    # Don't add handlers if they already exist (prevents duplicates)
    if logger.handlers:
        return logger

    # File handler - writes everything to log file
    log_filename = f"logs/cryptomind_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # Terminal handler - shows INFO and above on screen
    terminal_handler = logging.StreamHandler()
    terminal_handler.setLevel(logging.INFO)

    # Format: timestamp - level - message
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    terminal_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(terminal_handler)

    logger.info("CryptoMind AI Logger initialized")
    return logger


def get_logger():
    """Get the existing logger (call setup_logger first)."""
    return logging.getLogger("CryptoMind")


if __name__ == "__main__":
    # Test the logger
    logger = setup_logger()
    logger.info("This is an info message")
    logger.debug("This is a debug message (only in file)")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    print("\nLogger test complete! Check the logs/ folder.")
