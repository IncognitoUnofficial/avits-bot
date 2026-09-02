# booking_executor.py – fast‑track for new appointment path (Select POST and Proceed)
import logging
import time
from typing import Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from .session_manager import SessionManager
from .network_listener import NetworkListener

logger = logging.getLogger(__name__)

class BookingExecutor:
    def __init__(self, driver: WebDriver, session: SessionManager):
        self.driver = driver
        self.session = session

        # Booking endpoints (tried in order)
        self.possible_endpoints = [
            "/visaappointmentapi/appointments/book",
            "/visaappointmentapi/appointments/reschedule",
            "/visaadministrationapi/v1/modifyslot/confirm",
            "/visaapplicantapi/v1/appointment/confirm"
        ]

    def book_appointment(
        self,
        date_str: str,
        time_slot: Optional[str] = None,
        skip_time_selection: bool = True
    ) -> Dict[str, Any]:
        """
        Finalise booking for the new appointment path.

        If skip_time_selection is True (default), it assumes the time slot
        is already selected/clicked. Otherwise, it will attempt to select it.
        """
        try:
            # Step 1: (Optional) select time slot if not skipped
            if not skip_time_selection and time_slot:
                try:
                    xpath = f"//div[contains(@class, 'booking-time-buttons')]//button[contains(@class, 'green-button') and normalize-space(text())='{time_slot}']"
                    time_element = WebDriverWait(self.driver, timeout=2, poll_frequency=0.1).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", time_element)
                    time_element.click()
                    logger.info(f"Selected time slot: {time_slot}")
                except Exception as e:
                    logger.warning(f"Could not select time slot: {e}")
                    return {"success": False, "error": f"Time slot selection failed: {e}"}

            # Step 2: Click "Select POST and Proceed" button (new appointment path)
            btn_xpaths = [
                "//button[contains(@class, 'lrg-common-buttton') and contains(@class, 'light-lanvander-button') and normalize-space(text())='Select POST and Proceed']",
                "//button[contains(text(), 'Select POST and Proceed')]",
                "//span[contains(text(), 'Select POST and Proceed')]/..",
            ]

            book_btn = None
            for xpath in btn_xpaths:
                try:
                    book_btn = WebDriverWait(self.driver, timeout=3, poll_frequency=0.1).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    if book_btn:
                        logger.info(f"Found confirmation button with selector: {xpath}")
                        break
                except:
                    continue

            if not book_btn:
                return {"success": False, "error": "Could not find 'Select POST and Proceed' button"}

            # Step 3: Clear network logs and click
            for endpoint in self.possible_endpoints:
                try:
                    listener = NetworkListener(self.driver, endpoint)
                    listener.clear_logs()
                except:
                    pass

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", book_btn)
            time.sleep(0.05)
            book_btn.click()
            logger.info("Clicked 'Select POST and Proceed' – waiting for response...")

            # Step 4: Listen for booking confirmation from any endpoint (timeout 6 sec)
            for endpoint in self.possible_endpoints:
                try:
                    listener = NetworkListener(self.driver, endpoint)
                    tokens, status = listener.wait_for_tokens(timeout=6)
                    if status == 200:
                        logger.info(f"✅ Booking confirmed via {endpoint}")
                        return {"success": True, "date": date_str, "time": time_slot, "endpoint": endpoint}
                    elif status:
                        logger.debug(f"Endpoint {endpoint} returned status {status}")
                except Exception as e:
                    logger.debug(f"Endpoint {endpoint} listener failed: {e}")
                    continue

            logger.error("No booking response captured from any endpoint")
            return {"success": False, "error": "No booking response captured"}

        except Exception as e:
            logger.error(f"Booking failed: {e}")
            return {"success": False, "error": str(e)}

    def logout(self) -> bool:
        """Log out quickly."""
        try:
            logout_btn = self.driver.find_element(
                By.XPATH, "//*[contains(text(), 'Signout')]"
            )
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", logout_btn)
            logout_btn.click()
            logger.info("Logged out")
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False