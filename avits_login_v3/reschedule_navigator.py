# reschedule_navigator.py – reliable new‑path navigator (no dashboard class dependency)
import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from .session_manager import SessionManager

logger = logging.getLogger(__name__)

class RescheduleNavigator:
    def __init__(self, driver: WebDriver, session: SessionManager):
        self.driver = driver
        self.session = session

    # ----- go_to_pending_appointment() – direct selector loop (no class wait) -----
    def go_to_pending_appointment(self, timeout: int = 20) -> bool:
        """
        From the dashboard, click the 'Pending Appointment Request' button/link.
        Does not rely on a specific dashboard class; directly looks for the button.
        """
        try:
            wait = WebDriverWait(self.driver, timeout)
            # Give the page a moment to settle
            time.sleep(1)

            selectors = [
                "//*[contains(text(), 'Pending Appointment Request')]",
                "//*[contains(text(), 'PENDING APPOINTMENT REQUEST')]",
                "//button[contains(@class, 'pending')]",
                "//a[contains(@href, 'appointment')]//*[contains(text(), 'Pending')]",
                "//*[contains(@class, 'pending-appointment')]",
            ]
            for selector in selectors:
                try:
                    elem = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                    time.sleep(0.3)
                    elem.click()
                    logger.info("Clicked Pending Appointment Request")
                    time.sleep(2)
                    return True
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            logger.error("Could not find Pending Appointment Request button after all selectors")
            return False
        except Exception as e:
            logger.error(f"Error navigating to Pending Appointment Request: {e}")
            return False

    # ----- select_applicant() – robust (unchanged) -----
    def select_applicant(self, index: int = 0, timeout: int = 15) -> bool:
        try:
            wait = WebDriverWait(self.driver, timeout)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table")))
            time.sleep(0.5)

            selectors = [
                f"(//div[@class='custom-checkbox']//span[@class='checkbox'])[{index+1}]",
                f"(//div[@class='custom-checkbox']//span)[{index+1}]",
                f"(//div[@class='custom-checkbox']//input[@type='checkbox'])[{index+1}]",
            ]
            for selector in selectors:
                try:
                    elem = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", elem)
                    time.sleep(0.2)
                    elem.click()
                    logger.info(f"Selected applicant checkbox (index {index})")
                    time.sleep(0.5)
                    return True
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue

            # Fallback
            try:
                div = wait.until(EC.element_to_be_clickable((By.XPATH, f"(//div[@class='custom-checkbox'])[{index+1}]")))
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", div)
                time.sleep(0.2)
                div.click()
                logger.info(f"Selected applicant via parent div (index {index})")
                return True
            except Exception as e:
                logger.error(f"All methods to select applicant failed: {e}")
                return False

        except Exception as e:
            logger.error(f"Error selecting applicant: {e}")
            return False

    # ----- select_location() – unchanged -----
    def select_location(self, location: str = "Accra", timeout: int = 25, retries: int = 2) -> bool:
        for attempt in range(retries):
            try:
                wait = WebDriverWait(self.driver, timeout)
                time.sleep(5)

                try:
                    dropdown_triggers = [
                        "//*[contains(text(), '-- Select --')]",
                        "//*[contains(text(), '--select--')]",
                        "//*[contains(@class, 'dropdown')]//*[contains(text(), 'Select')]",
                        "//select"
                    ]
                    dropdown = None
                    for selector in dropdown_triggers:
                        try:
                            if selector == "//select":
                                dropdown = wait.until(EC.element_to_be_clickable((By.TAG_NAME, "select")))
                            else:
                                dropdown = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                            break
                        except:
                            continue
                    if dropdown:
                        dropdown.click()
                        logger.info("Dropdown clicked")
                        time.sleep(1)
                        location_option = wait.until(
                            EC.element_to_be_clickable((By.XPATH, f"//*[contains(text(), '{location}')]"))
                        )
                        location_option.click()
                        logger.info(f"Selected location: {location}")
                        time.sleep(3)
                        return True
                except Exception as e:
                    logger.warning(f"Method 1 failed: {e}")

                try:
                    selects = self.driver.find_elements(By.TAG_NAME, "select")
                    for select in selects:
                        if select.is_displayed():
                            select.click()
                            time.sleep(0.5)
                            options = select.find_elements(By.TAG_NAME, "option")
                            for option in options:
                                if location.lower() in option.text.lower():
                                    option.click()
                                    logger.info(f"Selected location via select: {location}")
                                    time.sleep(3)
                                    return True
                except Exception as e:
                    logger.warning(f"Method 2 failed: {e}")

                logger.warning(f"select_location attempt {attempt+1}/{retries} failed")
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                else:
                    logger.error("All methods failed to select location after retries")
                    return False

            except Exception as e:
                logger.error(f"select_location error: {e}")
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return False
        return False