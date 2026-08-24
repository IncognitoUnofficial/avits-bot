#!/usr/bin/env python3
"""
AVITS Login Bot v3 – Modular, stealth, headed Chrome login.
"""
import argparse
import time
import sys
import logging
from typing import Optional

from .config import load_config
from .driver_manager import init_driver
from .login_page import LoginPage
from .captcha_handler import CaptchaHandler
from .network_listener import NetworkListener
from .session_manager import SessionManager
from .result_saver import save_result
from .utils import setup_logging
from .exceptions import (
    DriverInitError, LoginError, TokenExtractionError, CaptchaTimeoutError
)

def main():
    parser = argparse.ArgumentParser(
        description="AVITS Login Bot v3 – Stealth headed Chrome",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m avits_login_v3.main -e "user@gmail.com" -p "mypassword"
  python -m avits_login_v3.main -e "user@gmail.com" -p "mypassword" --keep-open --proxy "http://user:pass@host:port"
        """
    )
    parser.add_argument("-e", "--email", required=True, help="AVITS account email")
    parser.add_argument("-p", "--password", required=True, help="AVITS account password")
    parser.add_argument("-t", "--timeout", type=int, default=30,
                        help="Page-load timeout in seconds (default: 30)")
    parser.add_argument("--keep-open", action="store_true",
                        help="Keep browser open after login for inspection")
    parser.add_argument("--proxy", help="Proxy URL (e.g., http://user:pass@host:port)")
    parser.add_argument("--config", help="Path to config.json (optional)")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)
    if args.timeout:
        config["timeout_seconds"] = args.timeout
    # Override proxy from CLI if given (else use config's proxy)
    proxy = args.proxy or config.get("proxy")

    # Setup logging
    logger = setup_logging(log_file=config.get("log_file", "avits_login.log"))
    logger.info("=" * 60)
    logger.info("AVITS Login Bot v3 – Stealth Headed Chrome")
    logger.info(f"Account: {args.email}")
    logger.info("=" * 60)

    session = SessionManager()
    driver = None
    success = False
    attempt = 0
    max_attempts = config.get("max_login_attempts", 3)
    retry_delay = config.get("retry_delay_seconds", 10)

    while attempt < max_attempts and not success:
        attempt += 1
        logger.info(f"Login attempt {attempt}/{max_attempts}")
        driver = None  # Reset driver for each attempt

        try:
            # 1. Init driver (with proxy if provided)
            driver = init_driver(config, proxy=proxy)

            # 2. Network listener
            listener = NetworkListener(driver, config["login_api_path"])
            listener.clear_logs()

            # 3. Login page
            login_page = LoginPage(driver, config)
            login_page.load()

            # 4. CAPTCHA handler – detect before filling
            captcha = CaptchaHandler(driver, config["captcha_selectors"])
            if captcha.is_captcha_present():
                captcha.alert_and_wait(config.get("captcha_wait_seconds", 300))
            else:
                logger.info("No CAPTCHA detected before login.")

            # 5. Fill credentials
            login_page.fill_credentials(args.email, args.password)

            # 6. Click sign in
            login_page.click_sign_in()

            # 7. Wait for tokens and status code
            tokens, status_code = listener.wait_for_tokens(timeout=config["timeout_seconds"])

            # 8. Check for 5xx server errors
            if status_code and 500 <= int(status_code) < 600:
                logger.error(f"Login API returned {status_code} – server error")
                raise LoginError(f"HTTP {status_code}")   # triggers retry

            if tokens:
                session.update_tokens(tokens)
                logger.info("Tokens captured successfully.")
            else:
                logger.warning("No tokens captured via network logs.")

            # 9. Check dashboard load
            if login_page.is_dashboard_loaded():
                logger.info("Dashboard loaded – login successful.")
                success = True  # Mark as success
            else:
                # Check for other error messages
                errors = login_page.get_error_messages()
                if errors:
                    logger.error(f"Login failed with errors: {errors}")
                    if any("500" in e or "Internal Server" in e for e in errors):
                        raise LoginError("Server error (5xx)")
                    else:
                        raise LoginError(f"Login error: {errors}")
                else:
                    raise LoginError("Unknown login failure")

            # 10. ONLY IF SUCCESSFUL: Gather session data and save
            if success:
                session_data = {
                    "url": driver.current_url,
                    "title": driver.title,
                    "cookies": driver.get_cookies(),
                }
                try:
                    session_data["localStorage"] = driver.execute_script(
                        "return Object.fromEntries(Object.entries(localStorage));"
                    )
                except Exception:
                    session_data["localStorage"] = {}
                try:
                    session_data["sessionStorage"] = driver.execute_script(
                        "return Object.fromEntries(Object.entries(sessionStorage));"
                    )
                except Exception:
                    session_data["sessionStorage"] = {}

                session.session_data = session_data
                save_result(args.email, session.tokens, session_data,
                            config.get("result_file", "avits_login_result.json"))

                logger.info("=" * 60)
                logger.info("LOGIN SUCCESSFUL")
                if session.tokens.get("authorization_header"):
                    jwt = session.tokens["authorization_header"]
                    logger.info(f"JWT: {jwt[:60]}...")
                logger.info("=" * 60)

        except (DriverInitError, LoginError, TokenExtractionError, CaptchaTimeoutError) as e:
            logger.error(f"Attempt {attempt} failed: {e}")
            if attempt < max_attempts:
                logger.info(f"Retrying in {retry_delay}s...")
                time.sleep(retry_delay)
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                    driver = None
            else:
                logger.error("All attempts exhausted. Login failed.")
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            break

    # ============================================================
    # CLEANUP – Keep browser open ONLY on successful login
    # ============================================================
    if driver:
        if success and args.keep_open:
            # Keep browser open ONLY on successful login
            logger.info("✅ Login successful! Browser remains open for inspection.")
            logger.info("Press Enter in this terminal to close the browser and exit...")
            input()
        elif not success:
            # On failure, close immediately
            logger.info("❌ Login failed. Closing browser...")
        else:
            # If --keep-open wasn't specified, close immediately
            logger.info("Browser closing...")
        
        try:
            driver.quit()
            logger.info("Browser closed.")
        except Exception:
            pass

    if not success:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()