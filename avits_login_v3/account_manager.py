# account_manager.py – with booking_mode support
import json
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Default global settings (used if missing or empty)
DEFAULT_GLOBAL = {
    "max_concurrent_sessions": 2,
    "poll_interval": 2,
    "keep_open": False
}

class AccountManager:
    """Manages accounts from accounts.json file."""
    
    def __init__(self, config_path: str = "accounts.json"):
        self.config_path = config_path
        self.accounts: List[Dict[str, Any]] = []
        self.global_settings: Dict[str, Any] = {}
        self.load_accounts()
    
    def load_accounts(self):
        """Load accounts from JSON file, ensuring global settings have defaults."""
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Config file not found: {self.config_path}")
                self.accounts = []
                self.global_settings = DEFAULT_GLOBAL.copy()
                # Create the file with defaults
                self.save_accounts()
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.accounts = data.get("accounts", [])
                self.global_settings = data.get("global", {})
                
                # If global is empty or missing critical keys, set defaults
                if not self.global_settings or "poll_interval" not in self.global_settings:
                    self.global_settings = DEFAULT_GLOBAL.copy()
                    # Overwrite any existing values with defaults (but preserve accounts)
                    data["global"] = self.global_settings
                    # Write back to file so the file is corrected
                    with open(self.config_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4)
                    logger.info("Applied default global settings to accounts.json")
                
                # ---- NEW: ensure each account has booking_mode (default: reschedule) ----
                for acc in self.accounts:
                    if "booking_mode" not in acc:
                        acc["booking_mode"] = "reschedule"
                # If we added any booking_mode fields, save the file
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
                # ------------------------------------------------------------
                
                logger.info(f"Loaded {len(self.accounts)} accounts")
        except Exception as e:
            logger.error(f"Failed to load accounts: {e}")
            self.accounts = []
            self.global_settings = DEFAULT_GLOBAL.copy()
    
    def save_accounts(self):
        """Save accounts to JSON file, ensuring global settings are never empty."""
        try:
            # Ensure global_settings always has the required keys
            if not self.global_settings:
                self.global_settings = DEFAULT_GLOBAL.copy()
            else:
                # Ensure all default keys exist
                for key, value in DEFAULT_GLOBAL.items():
                    if key not in self.global_settings:
                        self.global_settings[key] = value
            
            data = {
                "accounts": self.accounts,
                "global": self.global_settings
            }
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Saved {len(self.accounts)} accounts")
        except Exception as e:
            logger.error(f"Failed to save accounts: {e}")
    
    def get_active_accounts(self) -> List[Dict[str, Any]]:
        """Get all active accounts."""
        return [acc for acc in self.accounts if acc.get("active", False)]
    
    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get account by ID."""
        for acc in self.accounts:
            if acc.get("id") == account_id:
                return acc
        return None
    
    def add_account(self, email: str, password: str, location: str = "Accra", 
                    date_range: Optional[Dict[str, str]] = None,
                    booking_mode: str = "reschedule") -> Dict[str, Any]:
        """Add a new account."""
        account = {
            "id": f"acc_{len(self.accounts) + 1}",
            "email": email,
            "password": password,
            "location": location,
            "date_range": date_range or {"from": "2026-09-01", "to": "2026-11-30"},
            "active": True,
            "booking_mode": booking_mode   # <-- added
        }
        self.accounts.append(account)
        self.save_accounts()
        logger.info(f"Added account: {email} (mode: {booking_mode})")
        return account
    
    def remove_account(self, account_id: str) -> bool:
        """Remove an account by ID."""
        for i, acc in enumerate(self.accounts):
            if acc.get("id") == account_id:
                self.accounts.pop(i)
                self.save_accounts()
                logger.info(f"Removed account: {acc.get('email')}")
                return True
        return False
    
    def toggle_account(self, account_id: str) -> bool:
        """Toggle account active status."""
        acc = self.get_account(account_id)
        if acc:
            acc["active"] = not acc.get("active", False)
            self.save_accounts()
            logger.info(f"Toggled account {acc.get('email')} to {acc.get('active')}")
            return True
        return False
    
    def update_account(self, account_id: str, updates: Dict[str, Any]) -> bool:
        """Update account fields."""
        acc = self.get_account(account_id)
        if acc:
            for key, value in updates.items():
                if key != "id":
                    acc[key] = value
            self.save_accounts()
            logger.info(f"Updated account: {acc.get('email')}")
            return True
        return False
    
    def get_global_setting(self, key: str, default: Any = None) -> Any:
        """Get a global setting, falling back to DEFAULT_GLOBAL if missing."""
        if key in self.global_settings:
            return self.global_settings[key]
        return DEFAULT_GLOBAL.get(key, default)
    
    def update_global_setting(self, key: str, value: Any):
        """Update a global setting."""
        self.global_settings[key] = value
        self.save_accounts()