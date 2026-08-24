# booking_executor.py
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
        
        # Possible booking endpoints (tried in order of likelihood)
        self.possible_endpoints = [
            "/visaappointmentapi/appointments/book",
            "/visaappointmentapi/appointments/reschedule",
            "/visaadministrationapi/v1/modifyslot/confirm",
            "/visaapplicantapi/v1/appointment/confirm"
        ]
    
    def book_appointment(self, date_str: str, time_slot: Optional[str] = None) -> Dict[str, Any]:
        """
        Book an appointment for the selected date and time.
        Listens for the booking response from any of the possible endpoints.
        """
        try:
            # Step 1: Ensure time slot is selected (if provided)
            if time_slot:
                try:
                    # Use the updated time slot selector (green-button inside .booking-time-buttons)
                    xpath = f"//div[contains(@class, 'booking-time-buttons')]//button[contains(@class, 'green-button') and normalize-space(text())='{time_slot}']"
                    time_element = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", time_element)
                    time.sleep(0.2)
                    time_element.click()
                    logger.info(f"Selected time slot: {time_slot}")
                except Exception as e:
                    logger.warning(f"Could not select time slot: {e}")
                    # Continue anyway – maybe the time is already selected
            
            # Step 2: Click "Book POST Appointment" button
            # Use the button with classes from the actual DOM
            btn_xpath = "//button[contains(@class, 'lrg-common-buttton') and contains(@class, 'light-lanvander-button') and normalize-space(text())='Book POST Appointment']"
            
            # Wait for the button to be clickable (enabled and visible)
            wait = WebDriverWait(self.driver, 10)
            book_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, btn_xpath))
            )
            # Also verify it's not disabled (the 'disabled' attribute is absent)
            if book_btn.get_attribute("disabled") is not None:
                logger.warning("Book button is disabled")
                return {"success": False, "error": "Book button disabled"}
            
            # Step 3: Clear logs and click
            for endpoint in self.possible_endpoints:
                try:
                    listener = NetworkListener(self.driver, endpoint)
                    listener.clear_logs()
                except:
                    pass
            
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", book_btn)
            time.sleep(0.2)
            book_btn.click()
            logger.info("Clicked 'Book POST Appointment' – waiting for response...")
            
            # Step 4: Listen for booking confirmation from any endpoint
            for endpoint in self.possible_endpoints:
                try:
                    listener = NetworkListener(self.driver, endpoint)
                    tokens, status = listener.wait_for_tokens(timeout=8)
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
        """Log out from AVITS."""
        try:
            logout_btn = self.driver.find_element(
                By.XPATH, "//*[contains(text(), 'Signout')]"
            )
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", logout_btn)
            time.sleep(0.2)
            logout_btn.click()
            logger.info("Logged out successfully")
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False