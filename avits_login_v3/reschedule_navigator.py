# reschedule_navigator.py – stable version + go_to_pending_appointment() and select_applicant()
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

    # ----- Existing: go_to_my_appointment() -----
    def go_to_my_appointment(self, timeout: int = 20, retries: int = 3):
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

    # ----- Existing: click_reschedule() -----
    def click_reschedule(self, timeout: int = 25, retries: int = 3):
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

                # Handle confirmation popup
                try:
                    dialog = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "mat-dialog-container"))
                    )
                    logger.info("Confirmation dialog detected")
                    time.sleep(0.5)
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
                            try:
                                confirm_btn = self.driver.find_element(
                                    By.XPATH, "//button[contains(@class, 'mat-raised-button')]//span[contains(text(), 'Confirm')]/.."
                                )
                                self.driver.execute_script("arguments[0].click();", confirm_btn)
                                logger.info("Clicked Confirm button (Method 3 - JavaScript)")
                                time.sleep(2)
                            except Exception as e3:
                                logger.error(f"All methods failed to click Confirm: {e3}")
                                if attempt < retries - 1:
                                    time.sleep(2)
                                    continue
                                else:
                                    return False
                except Exception as e:
                    logger.debug(f"No confirmation popup found: {e}")

                # Wait for reschedule page to load
                page_loaded = False
                max_wait = timeout
                start_time = time.time()
                while time.time() - start_time < max_wait:
                    current_url = self.driver.current_url
                    if "slot" in current_url or "appointment" in current_url:
                        logger.info(f"Reschedule page loaded: {current_url}")
                        page_loaded = True
                        break
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

    # ----- Existing: select_location() -----
    def select_location(self, location: str = "Accra", timeout: int = 25, retries: int = 2):
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

    # ----- Existing: is_on_reschedule_page() -----
    def is_on_reschedule_page(self) -> bool:
        return "slot" in self.driver.current_url or "appointment" in self.driver.current_url

    # ----- NEW: go_to_pending_appointment() -----
    def go_to_pending_appointment(self, timeout: int = 20) -> bool:
        """
        From the dashboard, click the 'Pending Appointment Request' button/link.
        """
        try:
            wait = WebDriverWait(self.driver, timeout)
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

    # ----- NEW: select_applicant() -----
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