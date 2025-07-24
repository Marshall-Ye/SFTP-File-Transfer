import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import paramiko
import pathlib
import threading
import time

# ── ENVIRONMENT CONFIGS ─────────────────────────────────────────────────────
ENVIRONMENTS = {
    "Test": {
        "host": "certftp.acelynk.com",
        "user": "d9t_invoices",
        "pass": "P6RQstzpAPNuWsn1",
    },
    "Prod": {
        "host": "ftpv2.acelynk.com",
        "user": "d9t_invoices",
        "pass": "qP8a0RvbYQ4HsIa3",
    },
}
REMOTE_DIR = "/"

# ── MAIN APPLICATION ────────────────────────────────────────────────────────
class SFTPHelperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Magaya SFTP Helper")
        self.geometry("760x560")
        self.resizable(False, False)

        # currently active env
        self.env_name = "Prod"   # default start in Production
        self.env = ENVIRONMENTS[self.env_name]

        # default download folder
        self.download_folder = pathlib.Path("E:/Developer_Stuff/MagayaTest")

        # ── HEADER / ENV SELECT ─────────────────────────────────────────────
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(pady=10)

        ctk.CTkLabel(
            header_frame, text="Magaya SFTP Helper",
            font=ctk.CTkFont(size=20, weight="bold")
        ).grid(row=0, column=0, padx=10)

        self.env_menu = ctk.CTkOptionMenu(
            header_frame, values=list(ENVIRONMENTS.keys()),
            command=self.switch_env
        )
        self.env_menu.set(self.env_name)
        self.env_menu.grid(row=0, column=1, padx=10)

        # ── BUTTON BAR ──────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(pady=5)

        self.folder_btn = ctk.CTkButton(
            btn_frame, text="Set Download Folder", command=self.pick_folder
        )
        self.folder_btn.grid(row=0, column=0, padx=10)

        self.download_btn = ctk.CTkButton(
            btn_frame, text="Download Selected File(s)", command=self.download_selected
        )
        self.download_btn.grid(row=0, column=1, padx=10)

        # ── SERVER FILE LIST ────────────────────────────────────────────────
        ctk.CTkLabel(
            self, text="Files on Server (Ctrl/Shift-click to select):"
        ).pack(pady=(10, 0))
        self.file_listbox = tk.Listbox(self, height=12, width=90, selectmode=tk.MULTIPLE)
        self.file_listbox.pack(pady=5)

        # ── LOG WINDOW ──────────────────────────────────────────────────────
        ctk.CTkLabel(self, text="Log:").pack(pady=(10, 0))
        self.log_box = ctk.CTkTextbox(self, width=720, height=150)
        self.log_box.pack(pady=5)
        self.log(f"App started in {self.env_name} environment.")
        self.log(f"Download folder: {self.download_folder}")

        # ── BACKGROUND REFRESH THREAD ───────────────────────────────────────
        threading.Thread(target=self.refresh_loop, daemon=True).start()

    # ── UI CALLBACKS ────────────────────────────────────────────────────────
    def switch_env(self, choice: str):
        if choice == self.env_name:
            return
        self.env_name = choice
        self.env = ENVIRONMENTS[self.env_name]
        self.log(f"🔄 Switched to {self.env_name} environment.")
        self.refresh_now()

    def pick_folder(self):
        selected = filedialog.askdirectory()
        if selected:
            self.download_folder = pathlib.Path(selected)
            self.log(f"Download folder set to: {self.download_folder}")

    def download_selected(self):
        sel_idxs = self.file_listbox.curselection()
        if not sel_idxs:
            self.log("⏩ No files selected.")
            return
        files = [self.file_listbox.get(i) for i in sel_idxs]
        self.download_btn.configure(state=ctk.DISABLED)
        threading.Thread(target=self.download_worker, args=(files,), daemon=True).start()

    # ── SFTP HELPERS ────────────────────────────────────────────────────────
    def connect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.env["host"], username=self.env["user"], password=self.env["pass"])
        return ssh, ssh.open_sftp()

    # ── DOWNLOAD WORKER ─────────────────────────────────────────────────────
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

                # skip duplicates by size
                if lpath.exists():
                    if lpath.stat().st_size == sftp.stat(rpath).st_size:
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

    # ── FILE LIST REFRESH ─────────────────────────────────────────────────--
    def fetch_server_files(self):
        ssh, sftp = self.connect()
        sftp.chdir(REMOTE_DIR)
        files = sorted(
            f for f in sftp.listdir() if f.lower().endswith((".pdf", ".xml"))
        )
        sftp.close(); ssh.close()
        return files

    def update_listbox(self, files):
        # attempt to preserve selection by filename
        selected_names = {self.file_listbox.get(i) for i in self.file_listbox.curselection()}
        self.file_listbox.delete(0, tk.END)
        for idx, f in enumerate(files):
            self.file_listbox.insert(tk.END, f)
            if f in selected_names:
                self.file_listbox.selection_set(idx)

    def refresh_now(self):
        try:
            files = self.fetch_server_files()
            self.update_listbox(files)
        except Exception as e:
            self.log(f"[Error] Refresh failed: {e}")

    def refresh_loop(self):
        while True:
            self.refresh_now()
            time.sleep(60)

    # ── LOG HELPER ──────────────────────────────────────────────────────────
    def log(self, msg):
        self.log_box.insert(tk.END, f"{msg}\n")
        self.log_box.see(tk.END)

# ── RUN THE APP ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = SFTPHelperApp()
    app.mainloop()
