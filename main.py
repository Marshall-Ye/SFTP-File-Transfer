import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import paramiko
import pathlib
import threading
import time
import sys

# ── 1) CHOOSE ENVIRONMENT: True = Prod, False = Test ───────────────────────
IS_PRODUCTION = 0

if IS_PRODUCTION:
    ENV_NAME   = "Prod"
    SFTP_HOST  = "ftpv2.acelynk.com"
    SFTP_USER  = "d9t_invoices"
    SFTP_PASS  = "qP8a0RvbYQ4HsIa3"
else:
    ENV_NAME   = "Test"
    SFTP_HOST  = "certftp.acelynk.com"
    SFTP_USER  = "d9t_invoices"
    SFTP_PASS  = "P6RQstzpAPNuWsn1"

REMOTE_DIR = "/"

# ── 2) MAIN APPLICATION ────────────────────────────────────────────────────
class SFTPHelperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Magaya SFTP Helper")
        self.geometry("760x560")
        self.resizable(False, False)

        # Default download folder: sibling “SFTP download” directory
        base_dir = pathlib.Path(
            sys.executable if getattr(sys, "frozen", False) else __file__
        ).resolve().parent
        self.download_folder = base_dir / "SFTP download"

        # ── Header
        ctk.CTkLabel(
            self, text="Magaya SFTP Helper",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=10)

        # ── Button bar
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(pady=5)

        ctk.CTkButton(
            btn_frame, text="Set Download Folder", command=self.pick_folder
        ).grid(row=0, column=0, padx=10)

        self.download_btn = ctk.CTkButton(
            btn_frame, text="Download Selected File(s)", command=self.download_selected
        )
        self.download_btn.grid(row=0, column=1, padx=10)

        # ── Server file list
        ctk.CTkLabel(
            self, text="Files on Server (Ctrl/Shift-click to select):"
        ).pack(pady=(10, 0))
        self.file_listbox = tk.Listbox(
            self, height=12, width=90, selectmode=tk.EXTENDED    # Windows-style
        )
        self.file_listbox.pack(pady=5)

        # ── Log window
        ctk.CTkLabel(self, text="Log:").pack(pady=(10, 0))
        self.log_box = ctk.CTkTextbox(self, width=720, height=150)
        self.log_box.pack(pady=5)
        self.log(f"App started in {ENV_NAME} environment.")
        self.log(f"Default download folder: {self.download_folder}")

        # ── Background refresh thread
        threading.Thread(target=self.refresh_loop, daemon=True).start()

    # ── UI callbacks --------------------------------------------------------
    def pick_folder(self):
        if (folder := filedialog.askdirectory()):
            self.download_folder = pathlib.Path(folder)
            self.log(f"Download folder set to: {self.download_folder}")

    def download_selected(self):
        indices = self.file_listbox.curselection()
        if not indices:
            self.log("⏩ No files selected.")
            return

        files = [self.file_listbox.get(i) for i in indices]
        self.download_btn.configure(state=ctk.DISABLED)
        threading.Thread(target=self.download_worker, args=(files,), daemon=True).start()

    # ── SFTP helpers --------------------------------------------------------
    def connect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(SFTP_HOST, username=SFTP_USER, password=SFTP_PASS)
        return ssh, ssh.open_sftp()

    # ── Download worker -----------------------------------------------------
    def download_worker(self, files):
        try:
            self.log(f"Starting download of {len(files)} file(s)…")
            ssh, sftp = self.connect()
            sftp.chdir(REMOTE_DIR)
            pulled = 0
            self.download_folder.mkdir(parents=True, exist_ok=True)

            for fname in files:
                rpath = f"{REMOTE_DIR}/{fname}"
                lpath = self.download_folder / fname

                # Skip identical file
                if lpath.exists() and lpath.stat().st_size == sftp.stat(rpath).st_size:
                    self.log(f"⏩ Skip {fname} (already downloaded)")
                    continue

                try:
                    self.log(f"⬇ Downloading {fname} …")
                    sftp.get(rpath, str(lpath))
                    self.log(f"✔ {fname}")
                    pulled += 1
                except Exception as e:
                    self.log(f"✖ {fname} ({e})")

            sftp.close(); ssh.close()
            self.log(f"Download complete — {pulled} new file(s).")
        except Exception as e:
            self.log(f"[Error] Download failed: {e}")
        finally:
            self.download_btn.configure(state=ctk.NORMAL)
            self.refresh_now()

    # ── File-list refresh ---------------------------------------------------
    def fetch_server_files(self):
        ssh, sftp = self.connect()
        sftp.chdir(REMOTE_DIR)
        files = sorted(f for f in sftp.listdir()
                       if f.lower().endswith((".pdf", ".xml")))
        sftp.close(); ssh.close()
        return files

    def update_listbox(self, files):
        selected = {self.file_listbox.get(i) for i in self.file_listbox.curselection()}
        self.file_listbox.delete(0, tk.END)
        for idx, f in enumerate(files):
            self.file_listbox.insert(tk.END, f)
            if f in selected:
                self.file_listbox.selection_set(idx)

    def refresh_now(self):
        try:
            self.update_listbox(self.fetch_server_files())
            self.log(f"🔄 Refreshed at {time.strftime('%H:%M:%S')}")
        except Exception as e:
            self.log(f"[Error] Refresh failed: {e}")

    def refresh_loop(self):
        while True:
            self.refresh_now()
            time.sleep(60)

    # ── Log helper ----------------------------------------------------------
    def log(self, msg: str):
        self.log_box.insert(tk.END, f"{msg}\n")
        self.log_box.see(tk.END)

# ── RUN APP ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = SFTPHelperApp()
    app.mainloop()
