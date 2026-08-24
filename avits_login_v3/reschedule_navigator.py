# reschedule_navigator.py
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

    # ----- MODIFIED: go_to_my_appointment() with retries and longer timeout -----
    def go_to_my_appointment(self, timeout: int = 20, retries: int = 3):
        """
        Navigate to My Appointment page with retries and explicit wait for UI.
        """
        for attempt in range(retries):
            try:
                wait = WebDriverWait(self.driver, timeout)
                selectors = [
                    "//*[contains(text(), 'My Appointments')]",
                    "//*[contains(text(), 'My Appointment')]",
                    "a[routerlink*='myappointment']"
                ]
                clicked = False
                for selector in selectors:
                    try:
                        if selector.startswith("//"):
                            btn = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                        else:
                            btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                        btn.click()
                        logger.info("Navigated to My Appointments")
                        clicked = True
                        break
                    except:
                        continue

                if not clicked:
                    raise TimeoutException("No clickable My Appointments button found")

                # Wait for the dashboard UI to be ready (My Appointments button visible again? Actually we want the reschedule button maybe)
                # But to be safe, we wait for a known element on the dashboard page
                WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'RESCHEDULE')]"))
                )
                logger.info("Dashboard UI confirmed – RESCHEDULE button visible")
                time.sleep(2)
                return True

            except TimeoutException:
                logger.warning(f"go_to_my_appointment attempt {attempt+1}/{retries} timed out")
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                else:
                    logger.error("Failed to navigate to My Appointments after all retries")
                    return False
            except Exception as e:
                logger.error(f"go_to_my_appointment error: {e}")
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return False
        return False
    # ----------------------------------------------------------------

    # ----- MODIFIED: click_reschedule() with retries and longer timeout -----
    def click_reschedule(self, timeout: int = 25, retries: int = 3):
        """
        Click RESCHEDULE and extract applicantId/appUUID from URL.
        Retries up to 'retries' times.
        """
        for attempt in range(retries):
            try:
                wait = WebDriverWait(self.driver, timeout)
                time.sleep(2)

                resched_buttons = self.driver.find_elements(
                    By.XPATH, "//*[contains(text(), 'RESCHEDULE')]"
                )

                if not resched_buttons:
                    logger.warning(f"No RESCHEDULE buttons found (attempt {attempt+1})")
                    if attempt < retries - 1:
                        time.sleep(2)
                        continue
                    else:
                        logger.error("No RESCHEDULE buttons found after all retries")
                        return False

                btn_clicked = False
                for btn in resched_buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                        time.sleep(0.5)
                        btn.click()
                        logger.info("Clicked RESCHEDULE button")
                        btn_clicked = True
                        time.sleep(1.5)
                        break

                if not btn_clicked:
                    raise TimeoutException("No visible/enabled RESCHEDULE button found")

                # ---- HANDLE CONFIRMATION POPUP (unchanged logic) ----
                try:
                    dialog = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "mat-dialog-container"))
                    )
                    logger.info("Confirmation dialog detected")
                    time.sleep(0.5)
                    # Method 1: Find Confirm button by text
                    try:
                        confirm_btn = self.driver.find_element(
                            By.XPATH, "//button//span[contains(text(), 'Confirm')]"
                        )
                        confirm_btn = confirm_btn.find_element(By.XPATH, "..")
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", confirm_btn)
                        time.sleep(0.5)
                        confirm_btn.click()
                        logger.info("Clicked Confirm button (Method 1)")
                        time.sleep(2)
                    except Exception as e:
                        logger.warning(f"Method 1 failed: {e}")
                        # Method 2: Find by class
                        try:
                            confirm_btn = self.driver.find_element(
                                By.CSS_SELECTOR, "button.mat-raised-button .mat-button-wrapper"
                            )
                            confirm_btn = confirm_btn.find_element(By.XPATH, "..")
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", confirm_btn)
                            time.sleep(0.5)
                            confirm_btn.click()
                            logger.info("Clicked Confirm button (Method 2)")
                            time.sleep(2)
                        except Exception as e2:
                            logger.warning(f"Method 2 failed: {e2}")
                            # Method 3: JavaScript click
                            try:
                                confirm_btn = self.driver.find_element(
                                    By.XPATH, "//button[contains(@class, 'mat-raised-button')]//span[contains(text(), 'Confirm')]/.."
                                )
                                self.driver.execute_script("arguments[0].click();", confirm_btn)
                                logger.info("Clicked Confirm button (Method 3 - JavaScript)")
                                time.sleep(2)
                            except Exception as e3:
                                logger.error(f"All methods failed to click Confirm: {e3}")
                                # If popup appears but we can't click Confirm, we treat it as failure and retry
                                if attempt < retries - 1:
                                    time.sleep(2)
                                    continue
                                else:
                                    return False
                except Exception as e:
                    logger.debug(f"No confirmation popup found: {e}")
                # -----------------------------------------------------

                # ---- WAIT FOR RESCHEDULE PAGE TO LOAD (with increased patience) ----
                page_loaded = False
                max_wait = timeout  # use the same timeout value
                start_time = time.time()
                while time.time() - start_time < max_wait:
                    current_url = self.driver.current_url
                    if "slot" in current_url or "appointment" in current_url:
                        logger.info(f"Reschedule page loaded: {current_url}")
                        page_loaded = True
                        break
                    # Check for dropdown or header
                    try:
                        dropdown = self.driver.find_element(
                            By.XPATH, "//*[contains(text(), '-- Select --')]"
                        )
                        if dropdown.is_displayed():
                            page_loaded = True
                            break
                    except:
                        pass
                    try:
                        header = self.driver.find_element(
                            By.XPATH, "//*[contains(text(), 'Reschedule an appointment')]"
                        )
                        if header.is_displayed():
                            page_loaded = True
                            break
                    except:
                        pass
                    time.sleep(0.5)

                if page_loaded:
                    # ---- EXTRACT IDs FROM URL ----
                    current_url = self.driver.current_url
                    parsed = urlparse(current_url)
                    params = parse_qs(parsed.query)
                    self.session.applicant_id = params.get('applicantId', [None])[0]
                    self.session.app_uuid = params.get('appUUID', [None])[0]
                    logger.info(f"Extracted applicantId: {self.session.applicant_id}, appUUID: {self.session.app_uuid}")
                    time.sleep(2)
                    return True
                else:
                    logger.warning("Reschedule page may not have loaded correctly")
                    # Still consider it a success if we got this far? We'll treat as failure to retry.
                    if attempt < retries - 1:
                        time.sleep(2)
                        continue
                    else:
                        return False

            except TimeoutException:
                logger.warning(f"click_reschedule attempt {attempt+1}/{retries} timed out")
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                else:
                    logger.error("click_reschedule failed after all retries")
                    return False
            except Exception as e:
                logger.error(f"click_reschedule error: {e}")
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
                else:
                    return False
        return False
    # ---------------------------------------------------------------

    # ----- MODIFIED: select_location() with retries and longer initial wait -----
    def select_location(self, location: str = "Accra", timeout: int = 25, retries: int = 2):
        """
        Select a location from the dropdown on the reschedule page.
        Retries up to 'retries' times.
        """
        for attempt in range(retries):
            try:
                wait = WebDriverWait(self.driver, timeout)
                time.sleep(5)  # increased initial wait

                # Method 1: Click dropdown and select
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

                # Method 2: Try using a select element directly
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
    # ----------------------------------------------------------------

    def is_on_reschedule_page(self) -> bool:
        """Check if we're on the reschedule page."""
        return "slot" in self.driver.current_url or "appointment" in self.driver.current_url