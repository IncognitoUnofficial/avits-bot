# driver_manager.py
import os
import sys
import tempfile
import logging
import random
from typing import Optional
import undetected_chromedriver as uc
from selenium.webdriver.remote.webdriver import WebDriver
from .exceptions import DriverInitError

logger = logging.getLogger(__name__)

def init_driver(config: dict, proxy: Optional[str] = None) -> WebDriver:
    """
    Launch undetected Chrome with maximum stealth.
    Uses a fresh temporary profile every time.
    Uses a portable Chrome from the bundled 'chrome-131' folder.
    """
    try:
        # Create a fresh temporary directory for this session
        temp_profile_dir = tempfile.mkdtemp(prefix="avits_bot_")
        logger.info(f"Using fresh Chrome profile: {temp_profile_dir}")

        options = uc.ChromeOptions()
        
        # ============================================================
        # POINT TO PORTABLE CHROME (relative to executable or script)
        # ============================================================
        if getattr(sys, 'frozen', False):
            # Running as a packaged executable (PyInstaller)
            base_path = sys._MEIPASS
        else:
            # Running as a normal Python script
            # Go one level up from this file's directory (avits_login_v3)
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        chrome_path = os.path.join(base_path, "chrome-131", "chrome.exe")
        if not os.path.exists(chrome_path):
            logger.error(f"Portable Chrome not found at: {chrome_path}")
            raise DriverInitError(f"Chrome executable not found: {chrome_path}")
        options.binary_location = chrome_path
        logger.info(f"Using portable Chrome: {chrome_path}")
        
        # ============================================================
        # BASIC CHROME OPTIONS
        # ============================================================
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-features=IsolateOrigins,site-per-process")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # Use the fresh profile (isolated from system Chrome)
        options.add_argument(f"--user-data-dir={temp_profile_dir}")
        
        # Performance logging for network capture
        options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        # Proxy support (if provided)
        if proxy:
            options.add_argument(f'--proxy-server={proxy}')
            logger.info(f"Using proxy: {proxy}")

        logger.info("Launching undetected-chromedriver (headed) with portable Chrome...")
        
        # Use version_main=131 to explicitly match Chrome 131
        driver = uc.Chrome(options=options, version_main=131)

        # ============================================================
        # MAXIMUM STEALTH PATCHES – injected before any page loads
        # ============================================================
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                // ============================================================
                // 1. Remove navigator.webdriver (the most important patch)
                // ============================================================
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // ============================================================
                // 2. Fake chrome.runtime (real Chrome always has this)
                // ============================================================
                window.chrome = { 
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // ============================================================
                // 3. Remove CDP automation variables
                // ============================================================
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
                
                // ============================================================
                // 4. Fix navigator.plugins (real Chrome has 5)
                // ============================================================
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        { name: 'Chrome PDF Plugin', filename: 'pdf_viewer' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin' },
                        { name: 'Widevine Content Decryption Module', filename: 'widevinecdm' },
                        { name: 'WebRTC', filename: 'webrtc' }
                    ]
                });
                
                // ============================================================
                // 5. Realistic languages (match a US user)
                // ============================================================
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en', 'fr']
                });
                
                // ============================================================
                // 6. Fix navigator.platform (real Windows machine)
                // ============================================================
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });
                
                // ============================================================
                // 7. Override permissions (real browser behavior)
                // ============================================================
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // ============================================================
                // 8. Delete window.webdriver
                // ============================================================
                delete window.webdriver;
            '''
        })

        # ============================================================
        # POST-INIT STEALTH (redundant but safe)
        # ============================================================
        # Remove webdriver property one more time
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        
        # Delete cdc_ variables again
        driver.execute_script(
            "delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;"
            "delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;"
            "delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;"
        )

        logger.info("All stealth patches applied successfully.")
        return driver

    except Exception as e:
        logger.error(f"Failed to initialise Chrome driver: {e}")
        raise DriverInitError(f"Driver init failed: {e}") from e