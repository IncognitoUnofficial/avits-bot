# rescheduler.py – optimised BEFORE, fast‑track booking, dynamic waits, skip navigation, booking_mode support
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .session_manager import SessionManager
from .reschedule_navigator import RescheduleNavigator
from .calendar_manager import CalendarManager
from .booking_executor import BookingExecutor
from .login_page import LoginPage
from .captcha_handler import CaptchaHandler
from .network_listener import NetworkListener
from .driver_manager import init_driver
from .config import load_config

logger = logging.getLogger(__name__)

# ---- TIMING CONSTANTS ----
STABILITY_TIMEOUT = 1.5      # seconds – how long to wait for calendar to stabilise
STABLE_TIME = 0.5            # seconds – required unchanged state duration
NAVIGATION_TIMEOUT = 2.0     # seconds – single attempt for BEFORE navigation
# -------------------------

class Rescheduler:
    def __init__(self, session_manager: SessionManager, driver, config: Dict[str, Any]):
        self.session = session_manager
        self.driver = driver
        self.config = config
        self.navigator = RescheduleNavigator(driver, session_manager)
        self.calendar = CalendarManager(driver, session_manager)
        self.executor = BookingExecutor(driver, session_manager)
        self.max_polls = config.get("max_polls", 2000)
        self.poll_interval = config.get("poll_interval", 2)          # kept as fallback info
        self.email = config.get("email")
        self.password = config.get("password")
        self.location = config.get("location", "Accra")
        self.date_range = config.get("date_range", {})
        self.booking_mode = config.get("booking_mode", "reschedule")  # "reschedule" or "new"
        self.relogin_attempts = 0
        self.max_relogins = 2

    def run(self) -> Dict[str, Any]:
        while True:
            try:
                result = self._run_cycle()
            except WebDriverException as e:
                logger.warning(f"WebDriver error: {e}")
                result = {"success": False, "error": "Browser error"}
            if result.get("success"):
                return result
            if result.get("error") in ("Session expired", "Max polls reached", "Logged out", "Browser error"):
                if self.relogin_attempts >= self.max_relogins:
                    return {"success": False, "error": f"Max relogin attempts reached ({self.max_relogins})"}
                self.relogin_attempts += 1
                logger.info(f"Relogin attempt {self.relogin_attempts}/{self.max_relogins} due to: {result.get('error')}")
                if not self._restart_browser_and_relogin():
                    return {"success": False, "error": "Relogin failed"}
                self.navigator = RescheduleNavigator(self.driver, self.session)
                self.calendar = CalendarManager(self.driver, self.session)
                self.executor = BookingExecutor(self.driver, self.session)
                continue
            return result

    def _run_cycle(self) -> Dict[str, Any]:
        print(f"\n🚀 Starting rescheduler for {self.location}")
        print(f"📅 Date range: {self.date_range.get('from', 'N/A')} → {self.date_range.get('to', 'N/A')}")
        print(f"⏱️  Poll interval (fallback timeout): {self.poll_interval}s")
        print(f"🔄 Relogin attempts: {self.relogin_attempts}/{self.max_relogins}")
        print(f"📌 Booking mode: {self.booking_mode}")

        target_months = self._build_month_list(self.date_range)
        if not target_months:
            return {"success": False, "error": "Invalid date range"}

        # ---- LOGIN (if needed) ----
        if not self.session.is_authenticated():
            print("[1] Logging in...")
            if not self._perform_login():
                return {"success": False, "error": "Login failed"}
            print("[+] Login successful!")
            time.sleep(0.5)

        # ---- NAVIGATION (branch based on booking_mode) ----
        if self.booking_mode == "new":
            # New appointment path
            print("[2] Navigating to Pending Appointment Request...")
            if not self.navigator.go_to_pending_appointment():
                return {"success": False, "error": "Could not navigate to Pending Appointment Request"}
            print("✅ Navigated to booking page")

            print("[3] Selecting applicant...")
            if not self.navigator.select_applicant():
                return {"success": False, "error": "Could not select applicant"}
            print("✅ Applicant selected")
            # The page now shows the calendar, same as reschedule page
        else:
            # Existing reschedule path (default)
            if self.navigator.is_on_reschedule_page():
                print("   ✅ Already on reschedule page, skipping navigation...")
            else:
                print("[2] Navigating to My Appointments...")
                if not self.navigator.go_to_my_appointment():
                    return {"success": False, "error": "Could not navigate to My Appointments"}
                print("✅ Navigated to My Appointments")
                time.sleep(0.3)

                print("[3] Clicking Reschedule...")
                if not self.navigator.click_reschedule():
                    return {"success": False, "error": "Could not click Reschedule"}
                print("✅ Clicked Reschedule")
                time.sleep(0.3)

                print(f"[4] Selecting location: {self.location}...")
                if not self.navigator.select_location(self.location):
                    return {"success": False, "error": f"Could not select location: {self.location}"}
                print(f"✅ Selected location: {self.location}")

        # ---- Initial stability ----
        print("[~] Waiting for initial calendar stability...")
        stable = self.calendar.wait_for_calendar_stable(timeout=STABILITY_TIMEOUT, stable_time=STABLE_TIME)
        if stable:
            print("[~] Initial calendar stable")
        else:
            print("[~] Initial stability timeout, proceeding anyway")

        # ---- Polling loop ----
        polls = 0
        while polls < self.max_polls:
            polls += 1
            remaining = self.session.get_remaining_time()
            print(f"\n   Poll {polls}/{self.max_polls} (Session: {remaining/60:.1f} min remaining)")

            # ---- CHECK LOGOUT ----
            if self.session.is_expired():
                return {"success": False, "error": "Session expired"}
            if self._is_logged_out():
                return {"success": False, "error": "Logged out"}
            try:
                if "login" in self.driver.current_url:
                    return {"success": False, "error": "Logged out"}
            except:
                return {"success": False, "error": "Browser unavailable"}

            # ---- GET CURRENT MONTH ----
            current = self.calendar.navigator.get_current_month_year()
            if current is None:
                print("   ⚠️ Could not determine current month, refreshing...")
                self.calendar.refresh_calendar(self.location)
                self.calendar.wait_for_calendar_stable(timeout=STABILITY_TIMEOUT, stable_time=STABLE_TIME)
                continue

            cur_month, cur_year = current
            print(f"   📍 Current month/year: {cur_month}/{cur_year}")

            # ---- PARSE DATE RANGE ----
            try:
                start_dt = datetime.strptime(self.date_range["from"], "%Y-%m-%d")
                end_dt = datetime.strptime(self.date_range["to"], "%Y-%m-%d")
            except Exception as e:
                print(f"   ❌ Invalid date range: {e}")
                return {"success": False, "error": "Invalid date range"}

            start_year, start_month = start_dt.year, start_dt.month
            end_year, end_month = end_dt.year, end_dt.month

            # ---- READ GREEN DATES (always) ----
            current_green_dates = self.calendar.get_available_green_dates(stable_time=STABLE_TIME)
            if current_green_dates:
                print(f"   📅 Current month green dates: {current_green_dates}")
            else:
                print("   📅 Current month has no green dates")

            # ---- EARLY CHECKS (before/after) ----
            if cur_year > end_year or (cur_year == end_year and cur_month > end_month):
                print("   🔄 Current month is AFTER target range – refreshing...")
                self.calendar.refresh_calendar(self.location)
                self.calendar.wait_for_calendar_stable(timeout=STABILITY_TIMEOUT, stable_time=STABLE_TIME)
                continue

            elif cur_year < start_year or (cur_year == start_year and cur_month < start_month):
                # BEFORE range: attempt to navigate to start month once (2s timeout)
                print("   🔄 Current month is BEFORE target range – attempting to navigate to start month (1 attempt only, 2s timeout)...")
                start_year, start_month = target_months[0]
                if self.calendar.navigator.navigate_to(start_year, start_month, overall_timeout=NAVIGATION_TIMEOUT):
                    print("   ✅ Successfully navigated to start month, continuing scan...")
                    # Now we are on the start month; fall through to scanning
                else:
                    print("   ❌ Could not navigate to start month – refreshing...")
                    self.calendar.refresh_calendar(self.location)
                    self.calendar.wait_for_calendar_stable(timeout=STABILITY_TIMEOUT, stable_time=STABLE_TIME)
                    continue

            # ---- NOW WE ARE INSIDE THE RANGE – SCAN TARGET MONTHS ----
            print("   🔍 Scanning target months...")

            # Build list of months to scan: start with current month if inside
            try:
                idx = target_months.index((cur_year, cur_month))
                months_to_scan = target_months[idx:] + target_months[:idx]
                print(f"      Current month is inside range – scanning from current month first")
            except ValueError:
                months_to_scan = target_months

            target_date = None
            for year, month in months_to_scan:
                print(f"      📆 Checking {year}-{month:02d}...")
                if (year, month) != (cur_year, cur_month):
                    try:
                        if not self.calendar.navigate_to_month(year, month):
                            print(f"      ⚠️ Could not navigate to {year}-{month:02d}, skipping")
                            continue
                    except Exception as e:
                        print(f"      ⚠️ Navigation error: {e}, skipping")
                        continue

                green_dates = self.calendar.get_available_green_dates(stable_time=STABLE_TIME)
                if green_dates:
                    print(f"      Found {len(green_dates)} green dates: {green_dates[:5]}...")
                    for d in green_dates:
                        if self.date_range["from"] <= d <= self.date_range["to"]:
                            target_date = d
                            print(f"      ✅ Found target date: {target_date}")
                            break
                else:
                    print(f"      No green dates")
                if target_date:
                    break

            # ---- FAST‑TRACK BOOKING ATTEMPT ----
            if target_date:
                print(f"\n⚡ Attempting fast booking for {target_date}...")
                booking_result = self._attempt_booking(target_date)
                if booking_result.get("success"):
                    print(f"\n✅✅✅ BOOKING SUCCESSFUL! ✅✅✅")
                    print(f"   Date: {target_date}")
                    print(f"   Time: {booking_result.get('time')}")
                    self.executor.logout()
                    return {"success": True, "date": target_date, "time": booking_result.get('time')}
                else:
                    error = booking_result.get('error', 'Unknown error')
                    print(f"   ❌ Booking attempt failed: {error}")
                    print("   🔄 Will refresh and continue polling...")
            else:
                print("   ❌ No green dates in target months")

            # ---- REFRESH AND WAIT FOR STABILITY ----
            if polls < self.max_polls:
                print("   [~] Refreshing calendar...")
                self.calendar.refresh_calendar(self.location)
                self.calendar.wait_for_calendar_stable(timeout=STABILITY_TIMEOUT, stable_time=STABLE_TIME)
                # Loop immediately (no fixed sleep)

        return {"success": False, "error": "Max polls reached"}

    # ------------------------------------------------------------------
    # FAST‑TRACK BOOKING ATTEMPT
    # ------------------------------------------------------------------
    def _attempt_booking(self, target_date: str) -> Dict[str, Any]:
        """
        Attempt to book the given date as fast as possible.
        Returns {'success': bool, 'time': str|None, 'error': str|None}
        """
        if not self.calendar.select_date_ui(target_date):
            return {"success": False, "error": "Could not select date (maybe not clickable?)"}

        try:
            container = WebDriverWait(self.driver, timeout=3, poll_frequency=0.1).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".booking-time-buttons.slot_calender"))
            )
        except TimeoutException:
            return {"success": False, "error": "Time slots did not appear within 3 seconds"}

        try:
            time_buttons = container.find_elements(By.CSS_SELECTOR, "button.green-button")
            visible_enabled = [btn for btn in time_buttons if btn.is_displayed() and btn.is_enabled()]
            if not visible_enabled:
                return {"success": False, "error": "No visible/enabled time slots"}
            selected_time = visible_enabled[0].text.strip()
            if not selected_time:
                return {"success": False, "error": "Time slot text empty"}
        except Exception as e:
            return {"success": False, "error": f"Error reading time slots: {e}"}

        try:
            visible_enabled[0].click()
        except Exception as e:
            return {"success": False, "error": f"Could not click time slot: {e}"}

        try:
            result = self.executor.book_appointment(target_date, selected_time, skip_time_selection=True)
            if result.get("success"):
                return {"success": True, "time": selected_time}
            else:
                return {"success": False, "error": result.get("error", "Booking executor failed")}
        except Exception as e:
            return {"success": False, "error": f"Booking executor exception: {e}"}

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _is_logged_out(self) -> bool:
        try:
            if "login" in self.driver.current_url:
                return True
            sign_in_btns = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'SIGN IN')]")
            if sign_in_btns:
                return True
            msgs = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Session expired') or contains(text(), 'logged out') or contains(text(), 'Log in')]")
            if msgs:
                return True
            return False
        except Exception:
            return True

    def _perform_login(self) -> bool:
        try:
            config = load_config()
            listener = NetworkListener(self.driver, config["login_api_path"])
            listener.clear_logs()
            login_page = LoginPage(self.driver, config)
            login_page.load()
            captcha = CaptchaHandler(self.driver, config["captcha_selectors"])
            if captcha.is_captcha_present():
                print("[!] CAPTCHA detected! Please solve it...")
                captcha.alert_and_wait(300)
            login_page.fill_credentials(self.email, self.password)
            login_page.click_sign_in()
            tokens, status = listener.wait_for_tokens(timeout=30)
            if tokens:
                self.session.update_tokens(tokens)
                logger.info(f"Login successful! (HTTP {status})")
                return True
            logger.error("Login failed - no tokens")
            return False
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    def _restart_browser_and_relogin(self) -> bool:
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass

            print("[*] Restarting browser...")
            self.driver = init_driver(self.config)

            print("[*] Logging in again...")
            if not self._perform_login():
                return False

            print("[+] Relogin successful!")

            # Re‑navigate to the reschedule page (will be skipped later if already there)
            self.navigator = RescheduleNavigator(self.driver, self.session)
            if not self.navigator.go_to_my_appointment():
                return False
            if not self.navigator.click_reschedule():
                return False
            if not self.navigator.select_location(self.location):
                return False

            # Wait for calendar to stabilise after relogin
            print("[~] Waiting for calendar to stabilise after relogin...")
            stable = self.calendar.wait_for_calendar_stable(timeout=STABILITY_TIMEOUT, stable_time=STABLE_TIME)
            if stable:
                print("[~] Calendar stable after relogin")
            else:
                print("[~] Calendar stability timeout, proceeding anyway")

            print("[+] Navigation to reschedule page completed")
            return True
        except Exception as e:
            logger.error(f"Error during browser restart/relogin: {e}")
            return False

    def _build_month_list(self, date_range: Dict[str, str]) -> List[Tuple[int, int]]:
        if not date_range or not date_range.get("from") or not date_range.get("to"):
            return []
        try:
            start = datetime.strptime(date_range["from"], "%Y-%m-%d")
            end = datetime.strptime(date_range["to"], "%Y-%m-%d")
            months = []
            current = start
            while current <= end:
                months.append((current.year, current.month))
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
            return months
        except Exception as e:
            logger.error(f"Error building month list: {e}")
            return []