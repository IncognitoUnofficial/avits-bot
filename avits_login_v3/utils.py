# utils.py
import logging
import random
import time
import sys
import os
from logging.handlers import TimedRotatingFileHandler
from typing import Optional
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webdriver import WebDriver


def setup_logging(log_file: Optional[str] = None, console_level=logging.INFO):
    """
    Configure logging with daily log rotation.
    
    Args:
        log_file: Path to log file (e.g., "avits_login.log")
        console_level: Logging level for console output
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Remove existing handlers to avoid duplicates
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Console handler (INFO+)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(console_level)
    console_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console.setFormatter(console_format)
    root.addHandler(console)

    # File handler with daily rotation
    if log_file:
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Use TimedRotatingFileHandler for daily rotation
        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",  # Rotate at midnight
            interval=1,       # Every 1 day
            backupCount=30,   # Keep 30 days of logs
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
        )
        file_handler.setFormatter(file_format)
        
        # Add suffix for the date (e.g., avits_login.log.2026-08-17)
        file_handler.suffix = "%Y-%m-%d"
        
        root.addHandler(file_handler)
        
        logger = logging.getLogger(__name__)
        logger.info(f"Logging to: {log_file} (rotated daily)")

    # Silence noisy loggers
    for name in ["selenium", "urllib3", "undetected_chromedriver"]:
        logging.getLogger(name).setLevel(logging.WARNING)

    return root


logger = logging.getLogger("avits_bot")


def human_type(element: WebElement, text: str, delay_min: float = 0.03, delay_max: float = 0.12):
    """Type text character-by-character with human-like pauses."""
    logger.debug(f"Typing {len(text)} chars into element {element.tag_name}")
    for i, char in enumerate(text):
        element.send_keys(char)
        delay = random.uniform(delay_min, delay_max)
        if random.random() < 0.08:      # thinking pause
            delay += random.uniform(0.15, 0.45)
        if random.random() < 0.03:      # typo‑correction pause
            delay += random.uniform(0.3, 0.8)
        time.sleep(delay)
    logger.debug("Typing complete")


def human_move_and_click(driver: WebDriver, element: WebElement):
    """Move mouse to element with a curved, human-like path and click."""
    actions = ActionChains(driver)

    # 1. Approach with offset
    actions.move_to_element_with_offset(
        element,
        random.randint(-80, 80),
        random.randint(-30, 30)
    )
    actions.pause(random.uniform(0.15, 0.4))

    # 2. Closer
    actions.move_to_element_with_offset(
        element,
        random.randint(-10, 10),
        random.randint(-5, 5)
    )
    actions.pause(random.uniform(0.08, 0.2))

    # 3. Centre
    actions.move_to_element(element)
    actions.pause(random.uniform(0.05, 0.15))

    # 4. Click
    actions.click()
    actions.pause(random.uniform(0.05, 0.1))
    actions.perform()
    logger.debug("Clicked with human‑like mouse path")