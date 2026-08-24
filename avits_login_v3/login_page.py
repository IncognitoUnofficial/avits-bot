# login_page.py
import time
import random
import logging
from typing import Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from .utils import human_type, human_move_and_click
from .exceptions import LoginError

logger = logging.getLogger(__name__)

class LoginPage:
    def __init__(self, driver: WebDriver, config: dict):
        self.driver = driver
        self.config = config
        self.login_url = config["login_url"]
        self.timeout = config["timeout_seconds"]
        self.dashboard_path = config["dashboard_path"]
        self.button_texts = config["button_texts"]
        self.button_fallback = config["button_fallback_selector"]

    def load(self):
        """Navigate to login page and wait for Angular."""
        logger.info(f"Loading {self.login_url}")
        self.driver.get(self.login_url)
        self._wait_for_angular()

    def _wait_for_angular(self):
        """Wait for Angular to stabilise."""
        try:
            WebDriverWait(self.driver, self.timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(2)  # extra buffer for initial rendering

            # Try to wait for Angular testability
            try:
                self.driver.execute_script("""
                    return new Promise((resolve) => {
                        if (window.getAllAngularTestabilities) {
                            const testabilities = window.getAllAngularTestabilities();
                            let pending = testabilities.length;
                            if (pending === 0) { resolve(true); return; }
                            testabilities.forEach(t => t.whenStable(() => {
                                pending--;
                                if (pending === 0) resolve(true);
                            }));
                            setTimeout(() => resolve(false), 8000);
                        } else {
                            resolve(false);
                        }
                    });
                """)
                time.sleep(1)
            except Exception:
                logger.debug("Angular testability not available")
        except Exception as e:
            logger.warning(f"Angular wait warning: {e}")

    def fill_credentials(self, email: str, password: str):
        """
        Fill email and password using human-like typing.
        """
        # Email field – the first visible text input
        email_input = None
        for elem in self.driver.find_elements(By.CSS_SELECTOR, "input[type='text']"):
            if elem.is_displayed():
                email_input = elem
                break
        if not email_input:
            email_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
            )

        email_input.click()
        time.sleep(random.uniform(0.1, 0.3))
        human_type(
            email_input,
            email,
            self.config.get("typing_delay_min", 0.03),
            self.config.get("typing_delay_max", 0.12)
        )
        logger.info(f"Email entered: {email}")

        time.sleep(random.uniform(0.3, 0.8))

        # Password field
        pass_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        pass_input.click()
        time.sleep(random.uniform(0.1, 0.3))
        human_type(
            pass_input,
            password,
            self.config.get("typing_delay_min", 0.03),
            self.config.get("typing_delay_max", 0.12)
        )
        logger.info("Password entered")

        time.sleep(random.uniform(0.5, 1.2))

    def click_sign_in(self):
        """Find and click the SIGN IN button."""
        button = None
        # Try to find by text
        for btn in self.driver.find_elements(By.TAG_NAME, "button"):
            try:
                if not btn.is_displayed():
                    continue
                txt = (btn.text or btn.get_attribute("value") or "").upper()
                if any(t in txt for t in self.button_texts) and "SIGN UP" not in txt:
                    button = btn
                    break
            except Exception:
                continue

        if not button:
            # Fallback to class
            button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.button_fallback))
            )

        human_move_and_click(self.driver, button)
        logger.info("Clicked SIGN IN")

    # ----- MODIFIED: is_dashboard_loaded() with retries and UI element wait -----
    def is_dashboard_loaded(self, timeout: int = 25, retries: int = 3) -> bool:
        """
        Wait for the dashboard to load by checking for a known UI element
        (e.g., 'My Appointments' button). Retries up to 'retries' times.
        """
        for attempt in range(retries):
            try:
                # Wait for URL to contain dashboard path
                WebDriverWait(self.driver, timeout).until(
                    lambda d: self.dashboard_path in d.current_url
                )
                logger.info(f"Dashboard URL detected: {self.driver.current_url}")

                # Now wait for a concrete UI element that confirms the page is ready
                # Look for "My Appointments" button (any visible text)
                WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'My Appointments')]"))
                )
                logger.info("Dashboard UI ready – 'My Appointments' button visible")
                return True

            except TimeoutException:
                logger.warning(f"Dashboard load attempt {attempt+1}/{retries} timed out after {timeout}s")
                if attempt < retries - 1:
                    logger.info("Retrying dashboard load check...")
                    time.sleep(2)
                    continue
                else:
                    logger.error("Dashboard not loaded after all retries.")
                    return False
            except Exception as e:
                logger.error(f"Dashboard check error: {e}")
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return False
        return False
    # -----------------------------------------------------------

    def get_error_messages(self) -> list:
        """Collect visible error messages."""
        errors = []
        for selector in [".alert", ".error", ".toast", "[role='alert']", ".text-danger"]:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elems:
                    if elem.is_displayed() and elem.text.strip():
                        errors.append(elem.text.strip())
            except Exception:
                continue
        return errors