# session_manager.py
import logging
import time
import requests
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class SessionManager:
    """Holds tokens, session data, and extracted IDs."""
    def __init__(self):
        self.tokens: Dict[str, str] = {}
        self.session_data: Dict = {}
        self.session_start: Optional[float] = None
        self.session_duration = 3600  # 1 hour default
        self.last_activity: Optional[float] = None

        # Extracted IDs for API calls
        self.applicant_id: Optional[str] = None
        self.app_uuid: Optional[str] = None
        self.application_id: Optional[str] = None
        self.post_user_id: Optional[int] = None

    def update_tokens(self, tokens: Dict[str, str]):
        self.tokens = tokens
        self.session_start = time.time()
        self.last_activity = time.time()
        logger.debug("Tokens updated.")

    def record_activity(self):
        self.last_activity = time.time()

    def get_auth_headers(self) -> Dict[str, str]:
        headers = {}
        if self.tokens.get("authorization_header"):
            headers["Authorization"] = self.tokens["authorization_header"]
        if self.tokens.get("csrf_token"):
            headers["X-CSRF-TOKEN"] = self.tokens["csrf_token"]
        headers["Content-Type"] = "application/json"
        return headers

    def is_authenticated(self) -> bool:
        return bool(self.tokens.get("authorization_header"))

    def get_remaining_time(self) -> float:
        if not self.session_start:
            return 0
        elapsed = time.time() - self.session_start
        return max(0, self.session_duration - elapsed)

    def is_expired(self) -> bool:
        return self.get_remaining_time() <= 0

    # ------------------------------------------------------------------
    # Token Refresh (API-based, no browser needed)
    # ------------------------------------------------------------------
    def refresh_auth_token(self) -> bool:
        """
        Use the refresh token to get a new JWT.
        Returns True if successful.
        """
        refresh_token = self.tokens.get("refresh_token")
        if not refresh_token:
            logger.error("No refresh token available")
            return False

        # The refresh endpoint – adjust if different
        refresh_url = "https://www.usvisaappt.com/identity/user/refresh"
        headers = {
            "Content-Type": "application/json",
        }
        payload = {
            "refresh_token": refresh_token
        }

        try:
            response = requests.post(refresh_url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # The response might contain a new id_token or access_token
                if "id_token" in data:
                    self.tokens["authorization_header"] = data["id_token"]
                    self.session_start = time.time()
                    logger.info("Token refreshed successfully")
                    return True
                elif "access_token" in data:
                    self.tokens["authorization_header"] = data["access_token"]
                    self.session_start = time.time()
                    logger.info("Token refreshed successfully")
                    return True
                else:
                    logger.error(f"Unexpected refresh response: {data}")
                    return False
            else:
                logger.error(f"Token refresh failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False