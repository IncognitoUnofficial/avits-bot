#!/usr/bin/env python3
"""
AVITS Booking Bot – Tkinter GUI
Simple, reliable, no threading issues.
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import sys
import os
import threading
import queue
import json

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from avits_login_v3.account_manager import AccountManager

class AVITSBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AVITS Booking Bot")
        self.root.geometry("900x700")
        
        # Account manager
        self.account_manager = AccountManager("accounts.json")
        
        # Queue for log messages
        self.log_queue = queue.Queue()
        self.process = None
        self.running = False
        
        self.setup_ui()
        self.load_accounts()
        self.process_log_queue()
    
    def setup_ui(self):
        """Setup the UI layout."""
        # Title
        title = tk.Label(self.root, text="🇺🇸 AVITS Booking Bot", font=("Arial", 20, "bold"))
        title.pack(pady=10)
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Account list frame
        account_frame = ttk.LabelFrame(main_frame, text="Accounts", padding="10")
        account_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Account list with scrollbar
        list_frame = ttk.Frame(account_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.account_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=6)
        self.account_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.account_listbox.yview)
        
        # Account buttons
        btn_frame = ttk.Frame(account_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="▶️ Start Selected", command=self.start_account).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="⏹️ Stop", command=self.stop_account).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔄 Refresh", command=self.load_accounts).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="➕ Add Account", command=self.add_account_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🗑️ Remove", command=self.remove_account).pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.status_label = tk.Label(main_frame, text="Status: Idle", font=("Arial", 10, "bold"))
        self.status_label.pack(pady=5)
        
        # Log output
        log_frame = ttk.LabelFrame(main_frame, text="Live Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, font=("Courier", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Global controls
        global_frame = ttk.Frame(main_frame)
        global_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(global_frame, text="▶️ Start All", command=self.start_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(global_frame, text="⏹️ Stop All", command=self.stop_all).pack(side=tk.LEFT, padx=5)
        
        # Info label
        info_label = tk.Label(main_frame, text="⚠️ Accounts and settings are stored in accounts.json", font=("Arial", 8), fg="gray")
        info_label.pack(pady=5)
    
    def load_accounts(self):
        """Load accounts into listbox."""
        self.account_manager.load_accounts()
        self.account_listbox.delete(0, tk.END)
        for acc in self.account_manager.accounts:
            status = "🟢" if acc.get("active") else "🔴"
            dr = acc.get("date_range", {})
            date_str = f"{dr.get('from', 'N/A')} → {dr.get('to', 'N/A')}"
            display = f"{status} {acc.get('email')} ({acc.get('location', 'Accra')}) [{date_str}]"
            self.account_listbox.insert(tk.END, display)
    
    def get_selected_account(self):
        """Get the selected account."""
        selection = self.account_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an account first.")
            return None
        idx = selection[0]
        if idx < len(self.account_manager.accounts):
            return self.account_manager.accounts[idx]
        return None
    
    def start_account(self):
        """Start the selected account."""
        account = self.get_selected_account()
        if not account:
            return
        
        if not account.get("active"):
            messagebox.showwarning("Inactive", "This account is inactive. Activate it first.")
            return
        
        if self.running:
            messagebox.showinfo("Running", "A session is already running.")
            return
        
        email = account.get("email")
        password = account.get("password")
        
        self.log_text.insert(tk.END, f"🚀 Starting {email}...\n")
        self.log_text.see(tk.END)
        self.status_label.config(text=f"Status: Running {email}")
        self.running = True
        
        # Run in a separate thread with subprocess
        thread = threading.Thread(target=self._run_bot, args=(email, password), daemon=True)
        thread.start()
    
    def _run_bot(self, email, password):
        """Run the bot in a subprocess."""
        try:
            cmd = [
                sys.executable,
                "test_reschedule.py",
                "-e", email,
                "-p", password,
                "--keep-open"
            ]
            
            self.log_queue.put(f"🔵 Running: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            self.process = process
            
            for line in process.stdout:
                if line.strip():
                    self.log_queue.put(line.strip())
            
            process.wait()
            
            if process.returncode == 0:
                self.log_queue.put(f"✅ {email} - Completed successfully")
            else:
                self.log_queue.put(f"❌ {email} - Exit code {process.returncode}")
            
        except Exception as e:
            self.log_queue.put(f"❌ Error: {e}")
        
        self.running = False
        self.process = None
        self.log_queue.put("🔵 Session finished")
        self.status_label.config(text="Status: Idle")
    
    def start_all(self):
        """Start all active accounts."""
        if self.running:
            messagebox.showinfo("Running", "A session is already running.")
            return
        
        active = [acc for acc in self.account_manager.accounts if acc.get("active")]
        if not active:
            messagebox.showwarning("No Active Accounts", "No active accounts found.")
            return
        
        # Start the first active account
        acc = active[0]
        self.account_listbox.selection_clear(0, tk.END)
        idx = self.account_manager.accounts.index(acc)
        self.account_listbox.selection_set(idx)
        self.start_account()
    
    def stop_account(self):
        """Stop the running session."""
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.log_queue.put("⏹️ Process terminated")
            except:
                pass
        self.status_label.config(text="Status: Stopped")
    
    def stop_all(self):
        """Stop all running sessions."""
        self.stop_account()
    
    def add_account_dialog(self):
        """Open dialog to add an account."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Account")
        dialog.geometry("450x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Grid layout
        ttk.Label(dialog, text="Email:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        email_entry = ttk.Entry(dialog, width=35)
        email_entry.grid(row=0, column=1, padx=10, pady=10)
        
        ttk.Label(dialog, text="Password:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        pass_entry = ttk.Entry(dialog, width=35, show="*")
        pass_entry.grid(row=1, column=1, padx=10, pady=10)
        
        ttk.Label(dialog, text="Location:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        loc_var = tk.StringVar(value="Accra")
        loc_combo = ttk.Combobox(dialog, textvariable=loc_var, values=["Accra", "Lagos", "Abuja", "Port Harcourt"], width=32)
        loc_combo.grid(row=2, column=1, padx=10, pady=10)
        
        ttk.Label(dialog, text="From Date:").grid(row=3, column=0, padx=10, pady=10, sticky="e")
        from_entry = ttk.Entry(dialog, width=35)
        from_entry.insert(0, "2026-09-01")
        from_entry.grid(row=3, column=1, padx=10, pady=10)
        
        ttk.Label(dialog, text="To Date:").grid(row=4, column=0, padx=10, pady=10, sticky="e")
        to_entry = ttk.Entry(dialog, width=35)
        to_entry.insert(0, "2026-11-30")
        to_entry.grid(row=4, column=1, padx=10, pady=10)
        
        def save_account():
            email = email_entry.get().strip()
            password = pass_entry.get().strip()
            location = loc_var.get()
            from_date = from_entry.get().strip()
            to_date = to_entry.get().strip()
            
            if not email or not password:
                messagebox.showwarning("Missing Fields", "Email and password are required.")
                return
            
            self.account_manager.add_account(
                email=email,
                password=password,
                location=location,
                date_range={"from": from_date, "to": to_date}
            )
            dialog.destroy()
            self.load_accounts()
            messagebox.showinfo("Success", f"Added account: {email}")
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="➕ Add Account", command=save_account).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def remove_account(self):
        """Remove the selected account."""
        account = self.get_selected_account()
        if not account:
            return
        
        if messagebox.askyesno("Confirm", f"Remove {account.get('email')}?"):
            self.account_manager.remove_account(account.get("id"))
            self.load_accounts()
    
    def process_log_queue(self):
        """Process pending log messages."""
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, msg + "\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        # Schedule next check
        self.root.after(100, self.process_log_queue)

def main():
    root = tk.Tk()
    app = AVITSBotGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()