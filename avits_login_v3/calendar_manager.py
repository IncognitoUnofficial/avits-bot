# calendar_manager.py – UI‑only with period‑picker‑first navigation, optimised timeouts
import logging
import time
import threading
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from .session_manager import SessionManager

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# MONTH MAP
# ------------------------------------------------------------------
MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "JUNE": 6,
    "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10,
    "NOVEMBER": 11, "DECEMBER": 12,
}

MONTH_NAMES_FULL = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

POLL_FREQUENCY = 0.1

# ------------------------------------------------------------------
# CALENDAR NAVIGATOR (PERIOD‑PICKER FIRST)
# ------------------------------------------------------------------
class CalendarNavigator:
    def __init__(self, driver: WebDriver):
        self.driver = driver

    def _get_header_text(self) -> Optional[str]:
        try:
            return self.driver.find_element(
                By.CSS_SELECTOR, ".mat-calendar-period-button"
            ).text.strip()
        except Exception:
            return None

    def get_current_month_year(self) -> Optional[Tuple[int, int]]:
        header = self._get_header_text()
        if not header:
            return None
        # If header contains a dash (year range), we are in multi-year view
        if "\u2013" in header or "-" in header:
            return None
        parts = header.split()
        if len(parts) < 2:
            return None
        month = MONTH_MAP.get(parts[0].upper(), 0)
        try:
            year = int(parts[1])
        except ValueError:
            return None
        return (month, year) if month else None

    def _is_multi_year_view(self) -> bool:
        header = self._get_header_text()
        return header and ("\u2013" in header or "-" in header)

    def _wait_for_header_change(self, old_header: Optional[str], timeout: float = 2.0) -> bool:
        try:
            WebDriverWait(self.driver, timeout, poll_frequency=POLL_FREQUENCY).until(
                lambda d: self._get_header_text() != old_header
            )
            return True
        except TimeoutException:
            return False

    def _wait_for_target(self, target_month: int, target_year: int, timeout: float = 2.5, confirm_time: float = 0.2) -> bool:
        end = time.monotonic() + timeout
        matched_since = None
        while time.monotonic() < end:
            current = self.get_current_month_year()
            if current == (target_month, target_year):
                matched_since = matched_since or time.monotonic()
                if time.monotonic() - matched_since >= confirm_time:
                    return True
            else:
                matched_since = None
            time.sleep(POLL_FREQUENCY)
        return False

    # ----------------------------------------------------------------
    # PERIOD PICKER (primary)
    # ----------------------------------------------------------------
    def _navigate_via_period_picker(self, target_year: int, target_month: int) -> bool:
        for attempt in range(3):
            try:
                return self._try_period_picker(target_year, target_month)
            except StaleElementReferenceException:
                logger.warning(f"Period picker stale (attempt {attempt+1}/3)")
                time.sleep(0.3)
                continue
            except Exception as e:
                logger.warning(f"Period picker error (attempt {attempt+1}/3): {e}")
                time.sleep(0.3)
                continue
        return False

    def _try_period_picker(self, target_year: int, target_month: int) -> bool:
        # 1. If already in multi-year view, close it first
        if self._is_multi_year_view():
            period_btn = WebDriverWait(self.driver, 2, poll_frequency=POLL_FREQUENCY).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".mat-calendar-period-button"))
            )
            period_btn.click()
            # Wait for month view
            WebDriverWait(self.driver, 2, poll_frequency=POLL_FREQUENCY).until(
                lambda d: not self._is_multi_year_view()
            )
            # Now we are in month view; we'll proceed to open the picker again
            # (if we didn't, we'd be in month view already)

        # 2. Open the period picker
        period_btn = WebDriverWait(self.driver, 2, poll_frequency=POLL_FREQUENCY).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".mat-calendar-period-button"))
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", period_btn)
        period_btn.click()

        # 3. Wait for year grid to appear
        WebDriverWait(self.driver, 2, poll_frequency=POLL_FREQUENCY).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".mat-calendar-body-cell"))
        )

        # 4. Select target year – try to find it directly
        year_btn = None
        try:
            year_btn = WebDriverWait(self.driver, 2, poll_frequency=POLL_FREQUENCY).until(
                EC.element_to_be_clickable((By.XPATH, f"//button[contains(@class, 'mat-calendar-body-cell') and @aria-label='{target_year}']"))
            )
        except TimeoutException:
            # If not visible, scroll the year grid (max 8 steps)
            for _ in range(8):
                # Determine direction based on target year relative to currently visible years
                visible = self._get_visible_years()
                if not visible:
                    break
                if target_year in visible:
                    # It just became visible; try to find it again
                    try:
                        year_btn = WebDriverWait(self.driver, 1, poll_frequency=POLL_FREQUENCY).until(
                            EC.element_to_be_clickable((By.XPATH, f"//button[contains(@class, 'mat-calendar-body-cell') and @aria-label='{target_year}']"))
                        )
                        break
                    except:
                        continue
                if target_year < min(visible):
                    btn_selector = ".mat-calendar-previous-button"
                elif target_year > max(visible):
                    btn_selector = ".mat-calendar-next-button"
                else:
                    # Should be visible but not found; retry finding
                    continue
                try:
                    scroll_btn = WebDriverWait(self.driver, 1, poll_frequency=POLL_FREQUENCY).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, btn_selector))
                    )
                    scroll_btn.click()
                    time.sleep(0.3)
                except:
                    break
            # After scrolling, try once more to find the year
            if not year_btn:
                try:
                    year_btn = WebDriverWait(self.driver, 1, poll_frequency=POLL_FREQUENCY).until(
                        EC.element_to_be_clickable((By.XPATH, f"//button[contains(@class, 'mat-calendar-body-cell') and @aria-label='{target_year}']"))
                    )
                except:
                    pass

        if not year_btn:
            logger.warning(f"Could not find year button for {target_year}")
            return False

        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", year_btn)
        year_btn.click()

        # 5. Wait for month view to appear (header should no longer be a range)
        try:
            WebDriverWait(self.driver, 2, poll_frequency=POLL_FREQUENCY).until(
                lambda d: not self._is_multi_year_view()
            )
        except TimeoutException:
            # If month view didn't appear, maybe we need to click the period button again?
            # But we'll proceed anyway – the month buttons might still be visible.
            pass

        # 6. Select target month via aria-label
        month_label = f"{MONTH_NAMES_FULL[target_month - 1]} {target_year}"
        month_btn = WebDriverWait(self.driver, 2, poll_frequency=POLL_FREQUENCY).until(
            EC.element_to_be_clickable((By.XPATH, f"//button[contains(@class, 'mat-calendar-body-cell') and @aria-label='{month_label}']"))
        )
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", month_btn)
        month_btn.click()

        # 7. Verify we reached the target
        if self._wait_for_target(target_month, target_year, timeout=2.0):
            logger.info(f"Period picker succeeded: {target_month}/{target_year}")
            return True
        else:
            logger.warning(f"Period picker landed on {self.get_current_month_year()} instead of target")
            return False

    def _get_visible_years(self) -> List[int]:
        years = []
        for cell in self.driver.find_elements(By.CSS_SELECTOR, ".mat-calendar-body-cell"):
            label = (cell.get_attribute("aria-label") or "").strip()
            if label.isdigit():
                years.append(int(label))
        return years

    # ----------------------------------------------------------------
    # ARROWS (fallback)
    # ----------------------------------------------------------------
    def _click_arrow_with_retry(self, btn_selector: str) -> bool:
        for _ in range(3):
            try:
                btn = WebDriverWait(self.driver, 2, poll_frequency=POLL_FREQUENCY).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, btn_selector))
                )
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                btn.click()
                time.sleep(0.1)
                return True
            except StaleElementReferenceException:
                time.sleep(0.3)
                continue
            except:
                return False
        return False

    def _navigate_via_arrows(self, target_year: int, target_month: int, max_clicks: int = 24) -> bool:
        current = self.get_current_month_year()
        if not current:
            return False
        cur_month, cur_year = current

        if target_year > cur_year or (target_year == cur_year and target_month > cur_month):
            btn_selector = ".mat-calendar-next-button"
        else:
            btn_selector = ".mat-calendar-previous-button"

        clicks = 0
        while clicks < max_clicks:
            current = self.get_current_month_year()
            if current == (target_month, target_year):
                return self._wait_for_target(target_month, target_year, timeout=1.5)
            if not self._click_arrow_with_retry(btn_selector):
                break
            clicks += 1
        return False

    # ----------------------------------------------------------------
    # UNIFIED ENTRY – period picker first for all jumps
    # ----------------------------------------------------------------
    def navigate_to(self, target_year: int, target_month: int, overall_timeout: float = 15.0) -> bool:
        deadline = time.monotonic() + overall_timeout
        attempt = 0

        while time.monotonic() < deadline:
            attempt += 1

            # If we are already in multi-year view, close it
            if self._is_multi_year_view():
                try:
                    period_btn = WebDriverWait(self.driver, 2, poll_frequency=POLL_FREQUENCY).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, ".mat-calendar-period-button"))
                    )
                    period_btn.click()
                    WebDriverWait(self.driver, 2, poll_frequency=POLL_FREQUENCY).until(
                        lambda d: not self._is_multi_year_view()
                    )
                except Exception as e:
                    logger.warning(f"Could not close multi-year view: {e}")
                    return False

            current = self.get_current_month_year()
            if current and current[0] == target_month and current[1] == target_year:
                return True

            # Primary: period picker
            if self._navigate_via_period_picker(target_year, target_month):
                return True

            # Fallback: arrows
            logger.info("Period picker failed, trying arrows")
            if self._navigate_via_arrows(target_year, target_month):
                return True

            if time.monotonic() >= deadline:
                break
            logger.warning(f"Navigation attempt {attempt} failed, retrying")
            time.sleep(0.5)

        logger.error(f"Navigation to {target_month}/{target_year} failed after {attempt} attempts")
        return False


# ------------------------------------------------------------------
# MAIN CalendarManager (UI only)
# ------------------------------------------------------------------
class CalendarManager:
    def __init__(self, driver: WebDriver, session: SessionManager):
        self.driver = driver
        self.session = session
        self.location = "Accra"
        self.calendar_cell_selector = "button.mat-calendar-body-cell"
        self.enabled_cell_selector = "button.mat-calendar-body-cell:not(.mat-calendar-body-disabled)"
        self.special_cell_selector = "button.mat-calendar-body-cell.special-date"
        self.stop_keepalive = False
        self.keepalive_thread = None
        self.navigator = CalendarNavigator(driver)

    # ==================================================================
    # UI METHODS
    # ==================================================================

    def navigate_to_month(self, target_year: int, target_month: int) -> bool:
        return self.navigator.navigate_to(target_year, target_month)

    def refresh_calendar(self, location: str = "Accra") -> bool:
        try:
            dropdown_selectors = [
                "//*[contains(@class, 'dropdown')]//*[contains(@class, 'selected')]",
                "//*[contains(@class, 'dropdown')]//*[contains(@class, 'value')]",
                "//*[contains(@class, 'dropdown-toggle')]",
                "//button[contains(@class, 'dropdown')]",
                "//*[contains(@class, 'dropdown')]",
                "//*[contains(text(), '-- Select --')]",
                "//*[contains(text(), 'Select POST')]",
                f"//*[contains(text(), '{location}')]",
            ]

            dropdown_clicked = False
            for selector in dropdown_selectors:
                try:
                    elem = WebDriverWait(self.driver, 1.0, poll_frequency=POLL_FREQUENCY).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                    elem.click()
                    dropdown_clicked = True
                    break
                except:
                    continue
            if not dropdown_clicked:
                return False

            try:
                select_option = WebDriverWait(self.driver, 1.0, poll_frequency=POLL_FREQUENCY).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '-- Select --')]"))
                )
                select_option.click()
            except:
                return False

            time.sleep(0.03)
            dropdown_reopened = False
            for selector in dropdown_selectors:
                try:
                    elem = self.driver.find_element(By.XPATH, selector)
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                    elem.click()
                    dropdown_reopened = True
                    break
                except:
                    continue
            if not dropdown_reopened:
                try:
                    elem = WebDriverWait(self.driver, 0.8, poll_frequency=POLL_FREQUENCY).until(
                        EC.element_to_be_clickable((By.XPATH, dropdown_selectors[0]))
                    )
                    elem.click()
                except:
                    pass

            try:
                location_option = WebDriverWait(self.driver, 1.0, poll_frequency=POLL_FREQUENCY).until(
                    EC.element_to_be_clickable((By.XPATH, f"//*[contains(text(), '{location}')]"))
                )
                location_option.click()
                logger.info(f"Calendar refreshed with '{location}'")
                return True
            except:
                return False
        except Exception as e:
            logger.error(f"Failed to refresh calendar: {e}")
            return False

    def wait_for_calendar_stable(self, timeout: float = 1.5, stable_time: float = 0.2, poll_frequency: float = 0.1) -> Optional[Dict[str, Any]]:
        end = time.monotonic() + timeout
        previous_state = None
        stable_since = None

        while time.monotonic() < end:
            state = self._get_calendar_state()
            if state is None:
                time.sleep(poll_frequency)
                continue

            if state != previous_state:
                previous_state = state
                stable_since = time.monotonic()
            elif stable_since is not None and (time.monotonic() - stable_since) >= stable_time:
                logger.info(
                    "Calendar stable: %d cells, %d enabled dates, %d special dates",
                    state["total_cells"],
                    state["enabled_cells"],
                    len(state["special_dates"])
                )
                return state

            time.sleep(poll_frequency)

        logger.warning("Calendar did not become stable within %s seconds", timeout)
        return None

    def _get_calendar_state(self) -> Optional[Dict[str, Any]]:
        try:
            header = self.driver.find_element(By.CSS_SELECTOR, ".mat-calendar-period-button").text.strip()
            all_cells = self.driver.find_elements(By.CSS_SELECTOR, self.calendar_cell_selector)
            enabled_cells = self.driver.find_elements(By.CSS_SELECTOR, self.enabled_cell_selector)
            special_cells = self.driver.find_elements(By.CSS_SELECTOR, self.special_cell_selector)

            enabled_dates = []
            special_dates = []
            for cell in enabled_cells:
                try:
                    aria_label = cell.get_attribute("aria-label") or ""
                    if not aria_label:
                        content = cell.find_element(By.CSS_SELECTOR, ".mat-calendar-body-cell-content")
                        aria_label = content.get_attribute("aria-label") or ""
                    actual_date = self._parse_calendar_date(aria_label)
                    if actual_date:
                        enabled_dates.append(actual_date)
                        if 'special-date' in cell.get_attribute('class'):
                            special_dates.append(actual_date)
                except:
                    continue

            return {
                "header": header,
                "total_cells": len(all_cells),
                "enabled_cells": len(enabled_cells),
                "enabled_dates": tuple(sorted(enabled_dates)),
                "special_dates": tuple(sorted(special_dates)),
            }
        except Exception as e:
            return None

    def _parse_calendar_date(self, aria_label: str) -> Optional[str]:
        if not aria_label:
            return None
        for fmt in ["%B %d, %Y", "%A, %B %d, %Y", "%b %d, %Y", "%A, %b %d, %Y"]:
            try:
                parsed = datetime.strptime(aria_label, fmt)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def get_current_ui_dates(self) -> List[str]:
        state = self.wait_for_calendar_stable(timeout=1.5, stable_time=0.2)
        return list(state["enabled_dates"]) if state else []

    def get_available_green_dates(self, stable_time: float = 0.2) -> List[str]:
        state = self.wait_for_calendar_stable(timeout=1.5, stable_time=stable_time)
        return list(state["special_dates"]) if state else []

    # ================================================================
    # DATE SELECTION
    # ================================================================
    def select_date_ui(self, date_str: str) -> bool:
        try:
            year, month, day = date_str.split("-")
            target_day = int(day)
            if not self.navigate_to_month(int(year), int(month)):
                return False
            self.wait_for_calendar_stable(timeout=1.5, stable_time=0.2)
            xpath = f"//button[contains(@class, 'mat-calendar-body-cell') and contains(@class, 'special-date')]//div[contains(@class, 'mat-calendar-body-cell-content') and normalize-space(text())='{target_day}']/.."
            try:
                day_cell = WebDriverWait(self.driver, 2, poll_frequency=POLL_FREQUENCY).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", day_cell)
                time.sleep(0.2)
                day_cell.click()
                logger.info(f"UI selected green date: {date_str}")
                time.sleep(1)
                return True
            except TimeoutException:
                green_dates = self.get_available_green_dates()
                if not green_dates:
                    return False
                return self.select_date_ui(green_dates[0])
        except Exception as e:
            logger.error(f"UI date selection failed: {e}")
            return False

    def get_time_slots_ui(self, date_str: str, timeout: float = 10.0) -> List[str]:
        try:
            container = WebDriverWait(self.driver, timeout, poll_frequency=POLL_FREQUENCY).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".booking-time-buttons.slot_calender"))
            )
            time_buttons = container.find_elements(By.CSS_SELECTOR, "button.green-button")
            times = []
            for btn in time_buttons:
                if btn.is_displayed() and btn.is_enabled():
                    text = btn.text.strip()
                    if text:
                        times.append(text)
            return times
        except Exception as e:
            logger.error(f"Failed to get time slots: {e}")
            return []

    def select_time_ui(self, time_slot: str) -> bool:
        try:
            xpath = f"//div[contains(@class, 'booking-time-buttons')]//button[contains(@class, 'green-button') and normalize-space(text())='{time_slot}']"
            time_element = WebDriverWait(self.driver, 3, poll_frequency=POLL_FREQUENCY).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", time_element)
            time_element.click()
            logger.info(f"UI selected time: {time_slot}")
            return True
        except Exception as e:
            logger.error(f"Time selection failed: {e}")
            return False

    # ==================================================================
    # KEEPALIVE
    # ==================================================================
    def start_keepalive(self, interval: int = 120):
        self.stop_keepalive = False
        if self.keepalive_thread and self.keepalive_thread.is_alive():
            return
        self.keepalive_thread = threading.Thread(target=self._keepalive_loop, args=(interval,), daemon=True)
        self.keepalive_thread.start()
        logger.info("UI keepalive thread started")

    def stop_keepalive(self):
        self.stop_keepalive = True
        if self.keepalive_thread:
            self.keepalive_thread.join(timeout=2)

    def _keepalive_loop(self, interval: int):
        while not self.stop_keepalive:
            try:
                self.driver.execute_script("return document.title;")
                self.session.record_activity()
                time.sleep(interval)
            except:
                break