# session_pool.py – with concurrency limit and no emojis
import logging
import time
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime
from .account_manager import AccountManager
from .rescheduler import Rescheduler
from .session_manager import SessionManager
from .driver_manager import init_driver
from .config import load_config

logger = logging.getLogger(__name__)

class AccountSession:
    def __init__(self, account: Dict[str, Any], config: Dict[str, Any]):
        self.account = account
        self.config = config
        self.session_manager = SessionManager()
        self.driver = None
        self.rescheduler = None
        self.thread = None
        self.is_running = False
        self.is_complete = False
        self.result = None
        self.start_time = None
        self.end_time = None
        self.error = None
    
    def start(self):
        self.is_running = True
        self.start_time = datetime.now()
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
        logger.info(f"Started session for {self.account.get('email')}")
    
    def _run(self):
        try:
            self.driver = init_driver(self.config)
            account_config = {
                "email": self.account.get("email"),
                "password": self.account.get("password"),
                "location": self.account.get("location", "Accra"),
                "date_range": self.account.get("date_range", {"from": "2026-09-01", "to": "2026-11-30"}),
                "poll_interval": self.config.get("poll_interval", 5),
                "max_polls": self.config.get("max_polls", 660),
                "keep_open": self.config.get("keep_open", False)
            }
            self.rescheduler = Rescheduler(
                self.session_manager,
                self.driver,
                account_config
            )
            self.result = self.rescheduler.run()
            self.is_complete = True
            self.is_running = False
            self.end_time = datetime.now()
            if self.result.get("success"):
                logger.info(f"[OK] {self.account.get('email')} - Success! Date: {self.result.get('date')}")
            else:
                logger.warning(f"[FAIL] {self.account.get('email')} - Failed: {self.result.get('error')}")
        except Exception as e:
            self.error = str(e)
            self.is_running = False
            self.is_complete = True
            self.end_time = datetime.now()
            logger.error(f"[FAIL] {self.account.get('email')} - Error: {e}")
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
    
    def stop(self):
        self.is_running = False
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
        logger.info(f"Stopped session for {self.account.get('email')}")
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "account_id": self.account.get("id"),
            "email": self.account.get("email"),
            "location": self.account.get("location"),
            "date_range": self.account.get("date_range"),
            "is_running": self.is_running,
            "is_complete": self.is_complete,
            "success": self.result.get("success") if self.result else False,
            "date": self.result.get("date") if self.result else None,
            "error": self.error or (self.result.get("error") if self.result else None),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else None
        }


class SessionPool:
    def __init__(self, accounts: List[Dict[str, Any]], config: Dict[str, Any]):
        self.accounts = accounts
        self.config = config
        self.max_sessions = config.get("max_concurrent_sessions", 2)
        self.sessions: List[AccountSession] = []
        self.running_sessions: List[AccountSession] = []
        self.completed_sessions: List[AccountSession] = []
        self.waiting_accounts = accounts.copy()
        self.is_running = False
        self.stop_requested = False
    
    def start_all(self):
        self.is_running = True
        self.stop_requested = False
        self.sessions = []
        self.running_sessions = []
        self.completed_sessions = []
        self.waiting_accounts = [acc for acc in self.accounts if acc.get("active", False)]
        
        logger.info(f"Starting session pool with {len(self.waiting_accounts)} accounts")
        logger.info(f"Max concurrent sessions: {self.max_sessions}")
        
        while len(self.running_sessions) < self.max_sessions and self.waiting_accounts:
            account = self.waiting_accounts.pop(0)
            session = self._create_session(account)
            session.start()
            self.running_sessions.append(session)
            self.sessions.append(session)
        
        self._monitor_loop()
    
    def _monitor_loop(self):
        while self.is_running and not self.stop_requested:
            for session in self.running_sessions[:]:
                if session.is_complete:
                    self.running_sessions.remove(session)
                    self.completed_sessions.append(session)
                    if self.waiting_accounts:
                        account = self.waiting_accounts.pop(0)
                        new_session = self._create_session(account)
                        new_session.start()
                        self.running_sessions.append(new_session)
                        self.sessions.append(new_session)
            
            if not self.running_sessions and not self.waiting_accounts:
                logger.info("All sessions complete")
                self.is_running = False
                break
            time.sleep(2)
    
    def _create_session(self, account: Dict[str, Any]) -> AccountSession:
        return AccountSession(account, self.config)
    
    def stop_all(self):
        self.stop_requested = True
        self.is_running = False
        for session in self.running_sessions:
            session.stop()
        self.waiting_accounts = []
        logger.info("Stopped all sessions")
    
    def get_status(self) -> List[Dict[str, Any]]:
        statuses = []
        for session in self.sessions:
            statuses.append(session.get_status())
        return statuses
    
    def get_summary(self) -> Dict[str, Any]:
        total = len(self.sessions)
        running = len([s for s in self.sessions if s.is_running])
        completed = len([s for s in self.sessions if s.is_complete])
        success = len([s for s in self.sessions if s.is_complete and s.result and s.result.get("success")])
        failed = len([s for s in self.sessions if s.is_complete and (not s.result or not s.result.get("success"))])
        return {
            "total": total,
            "running": running,
            "completed": completed,
            "success": success,
            "failed": failed,
            "waiting": len(self.waiting_accounts),
            "sessions": self.get_status()
        }