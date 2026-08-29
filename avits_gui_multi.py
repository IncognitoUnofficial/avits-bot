#!/usr/bin/env python3
"""
AVITS Booking Bot – Multi-Account GUI
Runs up to `max_concurrent_sessions` accounts simultaneously.
Supports starting all active accounts, starting a single selected account,
stopping, editing, adding, removing, and toggling active status.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import sys
import os
import threading
import queue
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from avits_login_v3.account_manager import AccountManager

class AVITSMultiBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AVITS Bot – Multi-Account")
        self.root.geometry("900x700")
        
        self.account_manager = AccountManager("accounts.json")
        self.log_queue = queue.Queue()
        self.process = None
        self.running = False
        self.lock = threading.Lock()
        
        self.setup_ui()
        self.load_accounts()
        self.process_log_queue()
    
    def setup_ui(self):
        title = tk.Label(self.root, text="🇺🇸 AVITS Multi-Account Bot", font=("Arial", 18, "bold"))
        title.pack(pady=10)
        
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        account_frame = ttk.LabelFrame(main_frame, text="Accounts", padding="10")
        account_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        list_frame = ttk.Frame(account_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.account_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=6)
        self.account_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.account_listbox.yview)
        
        btn_frame = ttk.Frame(account_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        # Start / Stop buttons
        ttk.Button(btn_frame, text="▶️ Start Selected", command=self.start_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="▶️ Start All", command=self.start_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="⏹️ Stop All", command=self.stop_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔄 Refresh", command=self.load_accounts).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔄 Toggle Active", command=self.toggle_active).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="➕ Add Account", command=self.add_account_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="✏️ Edit Selected", command=self.edit_account_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🗑️ Remove", command=self.remove_account).pack(side=tk.LEFT, padx=5)
        
        self.status_label = tk.Label(main_frame, text="Status: Idle", font=("Arial", 10, "bold"))
        self.status_label.pack(pady=5)
        
        log_frame = ttk.LabelFrame(main_frame, text="Live Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, font=("Courier", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        info_label = tk.Label(main_frame, text="⚠️ Max concurrent sessions: from accounts.json", font=("Arial", 8), fg="gray")
        info_label.pack(pady=5)
    
    def load_accounts(self):
        self.account_manager.load_accounts()
        self.account_listbox.delete(0, tk.END)
        for acc in self.account_manager.accounts:
            status = "🟢" if acc.get("active") else "🔴"
            dr = acc.get("date_range", {})
            date_str = f"{dr.get('from', 'N/A')} → {dr.get('to', 'N/A')}"
            mode = acc.get("booking_mode", "reschedule")
            display = f"{status} {acc.get('email')} ({acc.get('location', 'Accra')}) [{date_str}] [mode:{mode}]"
            self.account_listbox.insert(tk.END, display)
    
    def get_selected_account(self):
        selection = self.account_listbox.curselection()
        if not selection:
            return None
        idx = selection[0]
        if idx < len(self.account_manager.accounts):
            return self.account_manager.accounts[idx]
        return None
    
    # ================================================================
    # START / STOP
    # ================================================================
    def start_selected(self):
        account = self.get_selected_account()
        if not account:
            messagebox.showwarning("No Selection", "Please select an account first.")
            return
        if not account.get("active"):
            messagebox.showwarning("Inactive", "This account is inactive. Activate it first.")
            return
        if self.running:
            messagebox.showinfo("Running", "A session is already running.")
            return
        
        account_id = account.get("id")
        self.log_text.insert(tk.END, f"🚀 Starting selected account: {account.get('email')}...\n")
        self.log_text.see(tk.END)
        self.running = True
        self.status_label.config(text=f"Status: Running {account.get('email')}")
        thread = threading.Thread(target=self._run_orchestrator, args=(account_id,), daemon=True)
        thread.start()
    
    def start_all(self):
        if self.running:
            messagebox.showinfo("Running", "Sessions are already running.")
            return
        active = [acc for acc in self.account_manager.accounts if acc.get("active")]
        if not active:
            messagebox.showwarning("No Active Accounts", "No active accounts found.")
            return
        self.log_text.insert(tk.END, "🚀 Starting orchestrator with all active accounts...\n")
        self.log_text.see(tk.END)
        self.running = True
        self.status_label.config(text="Status: Running")
        thread = threading.Thread(target=self._run_orchestrator, daemon=True)
        thread.start()
    
    def stop_all(self):
        if not self.running:
            messagebox.showinfo("Not Running", "No session is currently running.")
            return
        self.running = False
        if self.process:
            try:
                self.process.terminate()
                self.log_queue.put("⏹️ Process terminated")
            except:
                pass
        self.status_label.config(text="Status: Stopped")
        self.log_queue.put("⏹️ Stop requested")
    
    # ---- UPDATED: _run_orchestrator() - works in source and packaged mode ----
    def _run_orchestrator(self, account_id=None):
        try:
            # Determine the base directory
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
                orchestrator_exe = os.path.join(base_dir, 'AVITS_Orchestrator.exe')
                cmd = [orchestrator_exe]
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                script_path = os.path.join(base_dir, 'run_orchestrator.py')
                cmd = [sys.executable, script_path]

            if account_id:
                cmd.extend(['--account', account_id])
            else:
                cmd.append('--run-all')

            self.log_queue.put(f"🔵 Running: {' '.join(cmd)}")
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=base_dir,
                encoding='utf-8'
            )
            for line in self.process.stdout:
                if line.strip():
                    self.log_queue.put(line.strip())
            self.process.wait()
            if self.process.returncode == 0:
                self.log_queue.put("✅ Orchestrator completed successfully")
            else:
                self.log_queue.put(f"❌ Orchestrator exited with code {self.process.returncode}")
        except Exception as e:
            self.log_queue.put(f"❌ Error: {e}")
        self.running = False
        self.process = None
        self.status_label.config(text="Status: Idle")
        self.log_queue.put("🔵 Session finished")
    
    # ================================================================
    # ACCOUNT MANAGEMENT
    # ================================================================
    def toggle_active(self):
        acc = self.get_selected_account()
        if not acc:
            messagebox.showwarning("No Selection", "Please select an account first.")
            return
        new_status = not acc.get("active", False)
        self.account_manager.toggle_account(acc["id"])
        self.load_accounts()
        status_text = "activated" if new_status else "deactivated"
        messagebox.showinfo("Toggle", f"Account {acc.get('email')} {status_text}.")
    
    def add_account_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Account")
        dialog.geometry("450x480")
        dialog.transient(self.root)
        dialog.grab_set()
        
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
        
        ttk.Label(dialog, text="Booking Mode:").grid(row=5, column=0, padx=10, pady=10, sticky="e")
        mode_var = tk.StringVar(value="reschedule")
        mode_combo = ttk.Combobox(dialog, textvariable=mode_var, values=["reschedule", "new"], width=32)
        mode_combo.grid(row=5, column=1, padx=10, pady=10)
        
        def save_account():
            email = email_entry.get().strip()
            password = pass_entry.get().strip()
            location = loc_var.get()
            from_date = from_entry.get().strip()
            to_date = to_entry.get().strip()
            booking_mode = mode_var.get()
            if not email or not password:
                messagebox.showwarning("Missing Fields", "Email and password are required.")
                return
            self.account_manager.add_account(
                email=email,
                password=password,
                location=location,
                date_range={"from": from_date, "to": to_date},
                booking_mode=booking_mode
            )
            dialog.destroy()
            self.load_accounts()
            messagebox.showinfo("Success", f"Added account: {email}")
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="➕ Add Account", command=save_account).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def edit_account_dialog(self):
        account = self.get_selected_account()
        if not account:
            messagebox.showwarning("No Selection", "Please select an account first.")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Account")
        dialog.geometry("450x480")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Email:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        email_entry = ttk.Entry(dialog, width=35)
        email_entry.insert(0, account.get("email", ""))
        email_entry.grid(row=0, column=1, padx=10, pady=10)
        
        ttk.Label(dialog, text="Password:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        pass_entry = ttk.Entry(dialog, width=35, show="*")
        pass_entry.insert(0, account.get("password", ""))
        pass_entry.grid(row=1, column=1, padx=10, pady=10)
        
        ttk.Label(dialog, text="Location:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        loc_var = tk.StringVar(value=account.get("location", "Accra"))
        loc_combo = ttk.Combobox(dialog, textvariable=loc_var, values=["Accra", "Lagos", "Abuja", "Port Harcourt"], width=32)
        loc_combo.grid(row=2, column=1, padx=10, pady=10)
        
        ttk.Label(dialog, text="From Date:").grid(row=3, column=0, padx=10, pady=10, sticky="e")
        dr = account.get("date_range", {})
        from_entry = ttk.Entry(dialog, width=35)
        from_entry.insert(0, dr.get("from", "2026-09-01"))
        from_entry.grid(row=3, column=1, padx=10, pady=10)
        
        ttk.Label(dialog, text="To Date:").grid(row=4, column=0, padx=10, pady=10, sticky="e")
        to_entry = ttk.Entry(dialog, width=35)
        to_entry.insert(0, dr.get("to", "2026-11-30"))
        to_entry.grid(row=4, column=1, padx=10, pady=10)
        
        ttk.Label(dialog, text="Booking Mode:").grid(row=5, column=0, padx=10, pady=10, sticky="e")
        mode_var = tk.StringVar(value=account.get("booking_mode", "reschedule"))
        mode_combo = ttk.Combobox(dialog, textvariable=mode_var, values=["reschedule", "new"], width=32)
        mode_combo.grid(row=5, column=1, padx=10, pady=10)
        
        def save_edit():
            email = email_entry.get().strip()
            password = pass_entry.get().strip()
            location = loc_var.get()
            from_date = from_entry.get().strip()
            to_date = to_entry.get().strip()
            booking_mode = mode_var.get()
            if not email or not password:
                messagebox.showwarning("Missing Fields", "Email and password are required.")
                return
            self.account_manager.update_account(account["id"], {
                "email": email,
                "password": password,
                "location": location,
                "date_range": {"from": from_date, "to": to_date},
                "booking_mode": booking_mode
            })
            dialog.destroy()
            self.load_accounts()
            messagebox.showinfo("Success", f"Updated account: {email}")
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=20)
        ttk.Button(btn_frame, text="💾 Save Changes", command=save_edit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
    
    def remove_account(self):
        acc = self.get_selected_account()
        if not acc:
            return
        if messagebox.askyesno("Confirm", f"Remove {acc.get('email')}?"):
            self.account_manager.remove_account(acc.get("id"))
            self.load_accounts()
    
    # ================================================================
    # LOGGING
    # ================================================================
    def process_log_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.insert(tk.END, msg + "\n")
                self.log_text.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self.process_log_queue)

def main():
    root = tk.Tk()
    app = AVITSMultiBotGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()