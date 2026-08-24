# captcha_handler.py
import time
import logging
from typing import List
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import NoSuchElementException
from .exceptions import CaptchaTimeoutError

logger = logging.getLogger(__name__)


class CaptchaHandler:
    def __init__(self, driver: WebDriver, selectors: List[str]):
        self.driver = driver
        self.selectors = selectors

    def is_captcha_present(self) -> bool:
        """Check if any CAPTCHA widget is visible in the DOM."""
        for sel in self.selectors:
            try:
                elements = self.driver.find_elements("css selector", sel)
                for elem in elements:
                    if elem.is_displayed():
                        logger.debug(f"CAPTCHA detected via selector: {sel}")
                        return True
            except Exception:
                continue
        return False

    def wait_for_solve(self, timeout: int) -> bool:
        """
        Poll until CAPTCHA disappears or timeout.
        Returns True if solved, False otherwise.
        """
        logger.info(f"Waiting for manual CAPTCHA solve (max {timeout}s)...")
        start = time.time()
        while time.time() - start < timeout:
            if not self.is_captcha_present():
                logger.info("CAPTCHA solved.")
                return True
            time.sleep(2)
        logger.warning(f"CAPTCHA not solved within {timeout}s")
        return False

    def alert_and_wait(self, timeout: int) -> bool:
        """Print prominent alert and wait for solve."""
        if not self.is_captcha_present():
            return True

        print("\n" + "!" * 60)
        print("!" + " " * 58 + "!")
        print("!" + "   CAPTCHA DETECTED — ACTION REQUIRED".center(58) + "!")
        print("!" + "   Please solve the CAPTCHA in the Chrome window".center(58) + "!")
        print("!" + "   The bot will continue automatically after you solve it".center(58) + "!")
        print("!" + " " * 58 + "!")
        print("!" * 60 + "\n")
        logger.info("CAPTCHA alert printed. Waiting for solve...")

        solved = self.wait_for_solve(timeout)
        if not solved:
            raise CaptchaTimeoutError("CAPTCHA not solved within timeout")
        return True