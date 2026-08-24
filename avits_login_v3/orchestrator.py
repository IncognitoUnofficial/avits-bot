# orchestrator.py – with fast polling, no emojis
import logging
import time
import sys
import argparse
import os
from typing import Dict, Any, List
from .account_manager import AccountManager
from .session_pool import SessionPool
from .config import load_config
from .utils import setup_logging

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self, accounts_file: str = "accounts.json"):
        self.account_manager = AccountManager(accounts_file)
        self.config = load_config()
        self.pool = None
        log_file = self.config.get("log_file", "logs/avits_login.log")
        setup_logging(log_file=log_file, console_level=logging.INFO)
        logger.info("=" * 70)
        logger.info("AVITS Multi-Account Orchestrator Started")
        logger.info(f"Accounts file: {accounts_file}")
        logger.info(f"Log file: {log_file}")
        logger.info("=" * 70)
    
    def run_all(self):
        accounts = self.account_manager.get_active_accounts()
        if not accounts:
            logger.warning("No active accounts found")
            print("\n[ERROR] No active accounts found. Add accounts to accounts.json or use --add")
            return
        
        max_sessions = self.account_manager.get_global_setting("max_concurrent_sessions", 2)
        poll_interval = self.account_manager.get_global_setting("poll_interval", 3)
        keep_open = self.account_manager.get_global_setting("keep_open", False)
        
        self.config["poll_interval"] = poll_interval
        self.config["keep_open"] = keep_open
        self.config["max_concurrent_sessions"] = max_sessions
        self.config["max_polls"] = 2000
        
        logger.info("=" * 70)
        logger.info(f"Starting orchestrator with {len(accounts)} accounts")
        logger.info(f"Max concurrent sessions: {max_sessions}")
        logger.info(f"Poll interval: {poll_interval}s")
        logger.info("=" * 70)
        
        print("\n" + "=" * 70)
        print(f"[START] Starting {len(accounts)} accounts (max {max_sessions} concurrent)")
        print(f"[INFO] Poll interval: {poll_interval}s")
        print("=" * 70 + "\n")
        
        self.pool = SessionPool(accounts, self.config)
        self.pool.start_all()
        
        while self.pool.is_running:
            summary = self.pool.get_summary()
            self._print_status(summary)
            time.sleep(10)
        
        final_summary = self.pool.get_summary()
        self._print_final_summary(final_summary)
        logger.info("Orchestrator finished")
    
    def _print_status(self, summary: Dict[str, Any]):
        print("\n" + "=" * 70)
        print(f"[STATUS] {summary['running']} running, {summary['completed']} completed, {summary['waiting']} waiting")
        print(f"   [OK] Success: {summary['success']} | [FAIL] Failed: {summary['failed']}")
        print("-" * 70)
        for session in summary["sessions"]:
            status_icon = "[RUN]" if session["is_running"] else "[OK]" if session.get("success") else "[FAIL]" if session["is_complete"] else "[WAIT]"
            status_text = "Running" if session["is_running"] else "Complete" if session["is_complete"] else "Waiting"
            date_info = f" -> {session['date']}" if session.get("date") else ""
            error_info = f" ({session['error']})" if session.get("error") else ""
            print(f"   {status_icon} {session['email']} - {status_text}{date_info}{error_info}")
        print("=" * 70)
    
    def _print_final_summary(self, summary: Dict[str, Any]):
        print("\n" + "=" * 70)
        print("[FINAL SUMMARY]")
        print("=" * 70)
        print(f"Total accounts: {summary['total']}")
        print(f"[OK] Success: {summary['success']}")
        print(f"[FAIL] Failed: {summary['failed']}")
        print("-" * 70)
        for session in summary["sessions"]:
            status_icon = "[OK]" if session.get("success") else "[FAIL]"
            date_info = f" -> {session['date']}" if session.get("date") else ""
            error_info = f" ({session['error']})" if session.get("error") else ""
            print(f"   {status_icon} {session['email']}{date_info}{error_info}")
        print("=" * 70)
        logger.info("Final summary:")
        logger.info(f"  Total: {summary['total']}, Success: {summary['success']}, Failed: {summary['failed']}")
        for session in summary["sessions"]:
            logger.info(f"  {session['email']}: {'OK' if session.get('success') else 'FAIL'} {session.get('date', '')} {session.get('error', '')}")
    
    def run_account(self, account_id: str):
        account = self.account_manager.get_account(account_id)
        if not account:
            logger.error(f"Account not found: {account_id}")
            print(f"\n[ERROR] Account not found: {account_id}")
            return
        if not account.get("active"):
            logger.warning(f"Account {account_id} is inactive")
            print(f"\n[WARN] Account {account_id} is inactive. Use --toggle {account_id} to activate.")
            return
        
        poll_interval = self.account_manager.get_global_setting("poll_interval", 3)
        keep_open = self.account_manager.get_global_setting("keep_open", False)
        self.config["poll_interval"] = poll_interval
        self.config["keep_open"] = keep_open
        self.config["max_polls"] = 2000
        
        print(f"\n[START] Running account: {account['email']}")
        print(f"[INFO] Poll interval: {poll_interval}s\n")
        
        self.pool = SessionPool([account], self.config)
        self.pool.start_all()
        
        while self.pool.is_running:
            summary = self.pool.get_summary()
            for session in summary["sessions"]:
                if session["is_running"]:
                    print(f"[RUN] {session['email']} - Running...")
                elif session["is_complete"]:
                    if session.get("success"):
                        print(f"[OK] {session['email']} - Success! Booked: {session.get('date')}")
                    else:
                        print(f"[FAIL] {session['email']} - Failed: {session.get('error')}")
            time.sleep(5)
        
        final_summary = self.pool.get_summary()
        self._print_final_summary(final_summary)


def main():
    parser = argparse.ArgumentParser(description="AVITS Multi-Account Orchestrator")
    parser.add_argument("--accounts", default="accounts.json", help="Accounts file path")
    parser.add_argument("--run-all", action="store_true", help="Run all active accounts")
    parser.add_argument("--account", help="Run a specific account by ID")
    parser.add_argument("--list", action="store_true", help="List all accounts")
    parser.add_argument("--add", nargs=3, metavar=("EMAIL", "PASSWORD", "LOCATION"), help="Add a new account")
    parser.add_argument("--toggle", help="Toggle account active status by ID")
    parser.add_argument("--remove", help="Remove an account by ID")
    parser.add_argument("--set-date", nargs=3, metavar=("ACCOUNT_ID", "FROM", "TO"), help="Set date range for an account")
    args = parser.parse_args()
    
    manager = AccountManager(args.accounts)
    
    if args.list:
        print("\n" + "=" * 70)
        print("[LIST] ACCOUNTS")
        print("=" * 70)
        if not manager.accounts:
            print("   No accounts found.")
        else:
            for acc in manager.accounts:
                status = "[OK] Active" if acc.get("active") else "[INACTIVE]"
                dr = acc.get("date_range", {})
                date_str = f"{dr.get('from', 'N/A')} -> {dr.get('to', 'N/A')}"
                print(f"   {acc['id']}: {acc['email']}")
                print(f"      Status: {status}")
                print(f"      Location: {acc.get('location', 'Accra')}")
                print(f"      Date Range: {date_str}")
                print()
        print("=" * 70)
        return
    
    if args.add:
        email, password, location = args.add
        manager.add_account(email, password, location)
        print(f"[OK] Added account: {email}")
        return
    
    if args.toggle:
        manager.toggle_account(args.toggle)
        print(f"[OK] Toggled account: {args.toggle}")
        return
    
    if args.remove:
        manager.remove_account(args.remove)
        print(f"[OK] Removed account: {args.remove}")
        return
    
    if args.set_date:
        account_id, from_date, to_date = args.set_date
        manager.update_account(account_id, {
            "date_range": {"from": from_date, "to": to_date}
        })
        print(f"[OK] Updated date range for {account_id}: {from_date} -> {to_date}")
        return
    
    orchestrator = Orchestrator(args.accounts)
    if args.run_all:
        orchestrator.run_all()
    elif args.account:
        orchestrator.run_account(args.account)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()