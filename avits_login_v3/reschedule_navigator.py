# reschedule_navigator.py – for new appointment path
import logging
import time
from urllib.parse import urlparse, parse_qs
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException
from .session_manager import SessionManager

logger = logging.getLogger(__name__)

class RescheduleNavigator:
    def __init__(self, driver: WebDriver, session: SessionManager):
        self.driver = driver
        self.session = session

    # ----- go_to_pending_appointment() -----
    def go_to_pending_appointment(self, timeout: int = 20) -> bool:
        """
        From the dashboard, click the 'Pending Appointment Request' button/link.
        """
        try:
            wait = WebDriverWait(self.driver, timeout)
            # Wait for dashboard to be ready
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "my-dashboard-content")))
            
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
                except:
                    continue
            logger.error("Could not find Pending Appointment Request button")
            return False
        except Exception as e:
            logger.error(f"Error navigating to Pending Appointment Request: {e}")
            return False

    # ----- select_applicant() -----
    def select_applicant(self, index: int = 0, timeout: int = 15) -> bool:
        """
        On the booking page, select the checkbox for the applicant at the given index (default first).
        Targets the <span class="checkbox"> inside the custom-checkbox div.
        """
        try:
            wait = WebDriverWait(self.driver, timeout)
            
            # Wait for the applicant table to be present
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table")))
            time.sleep(1)  # allow dynamic content to settle
            
            # Most reliable XPath: find the checkbox span inside the custom-checkbox div
            xpath = f"(//div[@class='custom-checkbox']//span[@class='checkbox'])[{index+1}]"
            checkbox_span = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", checkbox_span)
            time.sleep(0.3)
            checkbox_span.click()
            logger.info(f"Selected applicant checkbox (index {index})")
            time.sleep(0.5)
            return True
            
        except Exception as e:
            logger.error(f"Error selecting applicant: {e}")
            return False