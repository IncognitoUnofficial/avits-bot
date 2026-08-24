# network_listener.py
import json
import time
import logging
from typing import Dict, Optional, Tuple, Any
from selenium.webdriver.remote.webdriver import WebDriver

logger = logging.getLogger(__name__)

class NetworkListener:
    """
    Listens for network requests and responses.
    Captures request payloads and response tokens.
    """
    def __init__(self, driver: WebDriver, api_path: str):
        self.driver = driver
        self.api_path = api_path
        self.tokens: Dict[str, str] = {}
        self.last_request_payload: Optional[Dict[str, Any]] = None
        self._response_captured = False

    def clear_logs(self):
        """Clear performance logs and reset capture state."""
        try:
            self.driver.get_log("performance")
        except Exception:
            pass
        self.last_request_payload = None
        self.tokens = {}

    def extract_from_performance_logs(self) -> Tuple[Dict[str, str], Optional[int], Optional[Dict[str, Any]]]:
        """
        Parse performance logs for the target API.
        Returns (tokens_dict, status_code, request_payload).
        """
        try:
            logs = self.driver.get_log("performance")
        except Exception as e:
            logger.error(f"Failed to read performance logs: {e}")
            return {}, None, None

        request_payload = None
        for entry in logs:
            try:
                msg = json.loads(entry["message"])["message"]
                method = msg.get("method")

                # Capture request payload
                if method == "Network.requestWillBeSent":
                    req = msg["params"]["request"]
                    url = req.get("url", "")
                    if self.api_path in url:
                        post_data = req.get("postData")
                        if post_data:
                            try:
                                request_payload = json.loads(post_data)
                                logger.debug(f"Captured request payload: {request_payload}")
                            except json.JSONDecodeError:
                                logger.debug(f"Captured raw post data: {post_data}")

                # Capture response
                if method == "Network.responseReceived":
                    resp = msg["params"]["response"]
                    url = resp.get("url", "")
                    if self.api_path in url:
                        status = resp.get("status")
                        logger.info(f"Found API response: HTTP {status} for {url}")
                        headers = {k.lower(): v for k, v in resp.get("headers", {}).items()}
                        tokens = {
                            "authorization_header": headers.get("authorization", ""),
                            "refresh_token": headers.get("refreshtoken", ""),
                            "csrf_token": headers.get("csrftoken", ""),
                            "status_code": status,
                            "url": url,
                        }
                        self.tokens = tokens
                        return tokens, status, request_payload
            except Exception:
                continue
        return {}, None, request_payload

    def wait_for_tokens(self, timeout: int) -> Tuple[Dict[str, str], Optional[int]]:
        """Wait for the login API response."""
        start = time.time()
        while time.time() - start < timeout:
            tokens, status, _ = self.extract_from_performance_logs()
            if tokens:
                logger.info(f"Tokens extracted. Status: {status}")
                return tokens, status
            time.sleep(0.5)
        logger.warning(f"No login API response found within {timeout}s")
        return {}, None

    def get_request_payload(self, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """
        Wait for and return the request payload of the target API.
        Useful for capturing applicationId, postUserId, etc.
        """
        start = time.time()
        while time.time() - start < timeout:
            _, _, payload = self.extract_from_performance_logs()
            if payload:
                self.last_request_payload = payload
                return payload
            time.sleep(0.3)
        logger.warning(f"No request payload found within {timeout}s")
        return None