# rescheduler.py – with debug logs and robust recovery
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
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

class Rescheduler:
    def __init__(self, session_manager: SessionManager, driver, config: Dict[str, Any]):
        self.session = session_manager
        self.driver = driver
        self.config = config
        self.navigator = RescheduleNavigator(driver, session_manager)
        self.calendar = CalendarManager(driver, session_manager)
        self.executor = BookingExecutor(driver, session_manager)
        self.max_polls = config.get("max_polls", 2000)
        self.poll_interval = config.get("poll_interval", 2)
        self.email = config.get("email")
        self.password = config.get("password")
        self.location = config.get("location", "Accra")
        self.date_range = config.get("date_range", {})
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
        print(f"⏱️  Poll interval: {self.poll_interval}s")
        print(f"🔄 Relogin attempts: {self.relogin_attempts}/{self.max_relogins}")

        target_months = self._build_month_list(self.date_range)
        if not target_months:
            return {"success": False, "error": "Invalid date range"}

        if not self.session.is_authenticated():
            print("[1] Logging in...")
            if not self._perform_login():
                return {"success": False, "error": "Login failed"}
            print("[+] Login successful!")
            time.sleep(0.5)

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
        time.sleep(0.3)

        polls = 0
        while polls < self.max_polls:
            polls += 1
            remaining = self.session.get_remaining_time()
            print(f"\n   Poll {polls}/{self.max_polls} (Session: {remaining/60:.1f} min remaining)")

            # ---- DEBUG: CHECK LOGOUT ----
            if self.session.is_expired():
                return {"success": False, "error": "Session expired"}
            if self._is_logged_out():
                return {"success": False, "error": "Logged out"}
            try:
                if "login" in self.driver.current_url:
                    return {"success": False, "error": "Logged out"}
            except:
                return {"success": False, "error": "Browser unavailable"}

            # ---- DEBUG: GET CURRENT MONTH ----
            print("   [DEBUG] Getting current month/year...")
            current = self.calendar.navigator.get_current_month_year()
            print(f"   [DEBUG] current = {current}")

            if current is None:
                print("   [DEBUG] current is None – checking multi-year view...")
                if self.calendar.navigator._is_multi_year_view():
                    print("   [DEBUG] Multi-year view detected – closing it")
                    self.calendar.navigator._close_multi_year_view()
                    current = self.calendar.navigator.get_current_month_year()
                    print(f"   [DEBUG] After closing multi-year view: current = {current}")
                if current is None:
                    print("   ⚠️ Could not determine current month, refreshing...")
                    self.calendar.refresh_calendar(self.location)
                    time.sleep(self.poll_interval)
                    continue

            cur_month, cur_year = current
            print(f"   📍 Current month/year: {cur_month}/{cur_year}")

            # ---- DEBUG: PARSE DATE RANGE ----
            try:
                start_dt = datetime.strptime(self.date_range["from"], "%Y-%m-%d")
                end_dt = datetime.strptime(self.date_range["to"], "%Y-%m-%d")
            except Exception as e:
                print(f"   ❌ Invalid date range: {e}")
                return {"success": False, "error": "Invalid date range"}

            current_dt = datetime(cur_year, cur_month, 1)
            print(f"   [DEBUG] current_dt={current_dt}, end_dt={end_dt}")

            # ---- EARLY CHECK: AFTER TARGET RANGE ----
            if current_dt > end_dt:
                print("   🔄 Current month is AFTER target range – refreshing...")
                self.calendar.refresh_calendar(self.location)
                time.sleep(self.poll_interval)
                continue

            # ---- READ GREEN DATES ----
            current_green_dates = self.calendar.get_available_green_dates(stable_time=0.4)
            if current_green_dates:
                print(f"   📅 Current month green dates: {current_green_dates}")
            else:
                print("   📅 Current month has no green dates")

            # ---- SCAN TARGET MONTHS ----
            print("   🔍 Scanning target months...")
            target_date = None
            for year, month in target_months:
                print(f"      📆 Checking {year}-{month:02d}...")
                try:
                    if not self.calendar.navigate_to_month(year, month):
                        print(f"      ⚠️ Could not navigate, skipping")
                        continue
                except Exception as e:
                    print(f"      ⚠️ Navigation error: {e}, skipping")
                    continue
                green_dates = self.calendar.get_available_green_dates(stable_time=0.4)
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

            if target_date:
                print(f"\n[5] Booking {target_date}...")
                if not self.calendar.select_date_ui(target_date):
                    print(f"   ⚠️ Could not select date: {target_date}")
                    continue
                print("   ⏳ Waiting for time slots...")
                time.sleep(2)
                time_slots = self.calendar.get_time_slots_ui(target_date)
                if not time_slots:
                    print("   ⚠️ No time slots available")
                    continue
                selected_time = time_slots[0]
                print(f"   🕐 Selecting time slot: {selected_time}")
                result = self.executor.book_appointment(target_date, selected_time)
                if result.get("success"):
                    print(f"\n✅✅✅ BOOKING SUCCESSFUL! ✅✅✅")
                    print(f"   Date: {target_date}")
                    print(f"   Time: {selected_time}")
                    self.executor.logout()
                    return {"success": True, "date": target_date, "time": selected_time}
                else:
                    print(f"   ❌ Booking failed: {result.get('error')}")
                    return {"success": False, "error": result.get('error')}
            else:
                print("   ❌ No green dates in target months")

            # ---- REFRESH AND SLEEP ----
            if polls < self.max_polls:
                print("   [~] Refreshing calendar...")
                self.calendar.refresh_calendar(self.location)
                time.sleep(self.poll_interval)

        return {"success": False, "error": "Max polls reached"}

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
            self.navigator = RescheduleNavigator(self.driver, self.session)
            if not self.navigator.go_to_my_appointment():
                return False
            if not self.navigator.click_reschedule():
                return False
            if not self.navigator.select_location(self.location):
                return False
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