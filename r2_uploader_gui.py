import os
import json
import mimetypes
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

EXTRA_MIME = {
    ".m3u8": "application/vnd.apple.mpegurl",
    ".ts": "video/mp2t",
    ".m4s": "video/iso.segment",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
    ".mp3": "audio/mpeg",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg; codecs=opus",
    ".flac": "audio/flac",
    ".wav": "audio/wav",
    ".json": "application/json",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".svg": "image/svg+xml",
}


class R2UploaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("R2 Uploader Studio")
        self.root.geometry("900x620")

        self.folder_var = tk.StringVar()
        self.bucket_var = tk.StringVar()
        self.endpoint_var = tk.StringVar()  # https://<ACCOUNT_ID>.r2.cloudflarestorage.com
        self.key_var = tk.StringVar()
        self.secret_var = tk.StringVar()

        self._setup_theme()
        self._set_app_icon()
        self._build()

    def _setup_theme(self):
        style = ttk.Style()
        style.theme_use("clam")
        self.root.configure(bg="#0f131a")

        style.configure("App.TFrame", background="#0f131a")
        style.configure("App.TLabel", background="#0f131a", foreground="#d9e0ea", font=("Segoe UI", 11))
        style.configure("Title.TLabel", background="#0f131a", foreground="#66b6ff", font=("Segoe UI Semibold", 26))
        style.configure("TEntry", fieldbackground="#141a23", foreground="#edf2f7", insertcolor="#edf2f7")
        style.configure("TButton", background="#1a2230", foreground="#eaf1fb", borderwidth=0, focusthickness=0)
        style.map("TButton", background=[("active", "#243247")])
        style.configure("Accent.TButton", background="#2ea043", foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", "#3ab551")])
        style.configure("TProgressbar", troughcolor="#1b2330", background="#4f8cff")

    def _set_app_icon(self):
        self._app_icon = tk.PhotoImage(width=16, height=16)
        self._app_icon.put("#0f131a", to=(0, 0, 16, 16))
        self._app_icon.put("#2f81f7", to=(2, 2, 14, 14))
        self._app_icon.put("#0f131a", to=(5, 4, 11, 12))
        self._app_icon.put("#58a6ff", to=(7, 6, 13, 10))
        self.root.iconphoto(True, self._app_icon)

    def _build(self):
        pad = {"padx": 8, "pady": 6}

        frm = ttk.Frame(self.root, style="App.TFrame")
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="R2 Uploader Studio", style="Title.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", **pad)

        ttk.Label(frm, text="Carpeta local", style="App.TLabel").grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.folder_var, width=72).grid(row=1, column=1, sticky="we", **pad)
        ttk.Button(frm, text="Seleccionar carpeta", command=self.pick_folder).grid(row=1, column=2, **pad)

        ttk.Label(frm, text="Bucket", style="App.TLabel").grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.bucket_var, width=40).grid(row=2, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Endpoint R2", style="App.TLabel").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.endpoint_var, width=72).grid(row=3, column=1, columnspan=2, sticky="we", **pad)

        ttk.Label(frm, text="Access Key ID", style="App.TLabel").grid(row=4, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.key_var, width=50).grid(row=4, column=1, sticky="w", **pad)

        ttk.Label(frm, text="Secret Access Key", style="App.TLabel").grid(row=5, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.secret_var, width=50, show="*").grid(row=5, column=1, sticky="w", **pad)

        ttk.Button(frm, text="Guardar como…", command=self.save_form_data).grid(row=6, column=0, sticky="w", padx=8, pady=10)
        ttk.Button(frm, text="Cargar configuración…", command=self.load_form_data).grid(row=6, column=1, sticky="w", padx=8, pady=10)
        self.upload_btn = ttk.Button(frm, text="Subir", style="Accent.TButton", command=self.start_upload)
        self.upload_btn.grid(row=6, column=2, sticky="e", padx=8, pady=10)

        self.progress = ttk.Progressbar(frm, orient="horizontal", mode="determinate")
        self.progress.grid(row=7, column=0, columnspan=3, sticky="we", padx=8, pady=10)

        self.log = tk.Text(
            frm,
            height=20,
            bg="#111821",
            fg="#d9e0ea",
            insertbackground="#d9e0ea",
            relief="flat",
            borderwidth=1,
            highlightthickness=1,
            highlightbackground="#2a3445",
            highlightcolor="#4f8cff",
        )
        self.log.grid(row=8, column=0, columnspan=3, sticky="nsew", padx=8, pady=8)

        frm.grid_columnconfigure(1, weight=1)
        frm.grid_rowconfigure(8, weight=1)

    def pick_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)

    def _form_payload(self):
        return {
            "folder": self.folder_var.get(),
            "bucket": self.bucket_var.get(),
            "endpoint": self.endpoint_var.get(),
            "access_key_id": self.key_var.get(),
            "secret_access_key": self.secret_var.get(),
        }

    def save_form_data(self):
        path = filedialog.asksaveasfilename(
            title="Guardar configuración",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._form_payload(), f, indent=2, ensure_ascii=False)
            self.log_line(f"Configuración guardada en: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la configuración:\n{e}")

    def load_form_data(self):
        path = filedialog.askopenfilename(
            title="Cargar configuración",
            filetypes=[("JSON", "*.json"), ("Todos los archivos", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.folder_var.set(data.get("folder", ""))
            self.bucket_var.set(data.get("bucket", ""))
            self.endpoint_var.set(data.get("endpoint", ""))
            self.key_var.set(data.get("access_key_id", ""))
            self.secret_var.set(data.get("secret_access_key", ""))
            self.log_line(f"Configuración cargada desde: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar la configuración:\n{e}")

    def log_line(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.root.update_idletasks()

    def validate(self):
        folder = self.folder_var.get().strip()
        bucket = self.bucket_var.get().strip()
        endpoint = self.endpoint_var.get().strip()
        key = self.key_var.get().strip()
        secret = self.secret_var.get().strip()

        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error", "Selecciona una carpeta válida.")
            return None
        if not bucket:
            messagebox.showerror("Error", "El bucket es obligatorio.")
            return None
        if not endpoint.startswith("https://") and not endpoint.startswith("http://"):
            messagebox.showerror("Error", "Endpoint inválido. Ej: https://<ACCOUNT_ID>.r2.cloudflarestorage.com")
            return None
        if not key or not secret:
            messagebox.showerror("Error", "Access Key ID y Secret Access Key son obligatorios.")
            return None

        return folder, bucket, endpoint, key, secret

    def s3_client(self, endpoint, key, secret):
        return boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=key,
            aws_secret_access_key=secret,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )

    def list_remote(self, client, bucket):
        remote = {}
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                remote[obj["Key"]] = obj["Size"]  # comparación simple: misma key + mismo size => skip
        return remote

    def start_upload(self):
        data = self.validate()
        if not data:
            return

        self.upload_btn.config(state="disabled")
        threading.Thread(target=self.upload_worker, args=data, daemon=True).start()

    def upload_worker(self, folder, bucket, endpoint, key, secret):
        try:
            self.log_line("Conectando a R2...")
            client = self.s3_client(endpoint, key, secret)
            client.head_bucket(Bucket=bucket)
            self.log_line(f"Bucket OK: {bucket}")

            self.log_line("Leyendo archivos remotos...")
            remote = self.list_remote(client, bucket)
            self.log_line(f"Encontrados en R2: {len(remote)}")

            local_files = []
            root = Path(folder)
            for p in root.rglob("*"):
                if p.is_file():
                    rel_key = p.relative_to(root).as_posix()
                    size = p.stat().st_size
                    local_files.append((str(p), rel_key, size))

            self.log_line(f"Archivos locales: {len(local_files)}")

            to_upload = []
            skipped = 0
            for full_path, key_name, size in local_files:
                if key_name in remote and remote[key_name] == size:
                    skipped += 1
                    self.log_line(f"SKIP {key_name} (duplicado)")
                else:
                    to_upload.append((full_path, key_name))

            self.log_line(f"Subir: {len(to_upload)} | Omitidos: {skipped}")

            total = len(to_upload)
            self.progress["value"] = 0
            self.progress["maximum"] = max(total, 1)

            for i, (full_path, key_name) in enumerate(to_upload, start=1):
                self.log_line(f"[{i}/{total}] Subiendo {key_name}")
                extension = Path(full_path).suffix.lower()
                content_type = EXTRA_MIME.get(extension) or mimetypes.guess_type(full_path)[0] or "application/octet-stream"
                client.upload_file(full_path, bucket, key_name, ExtraArgs={"ContentType": content_type})
                self.progress["value"] = i
                self.root.update_idletasks()

            self.log_line("✅ Subida completada.")
            messagebox.showinfo("OK", f"Subida terminada.\nSubidos: {len(to_upload)}\nOmitidos: {skipped}")

        except ClientError as e:
            self.log_line(f"❌ Error S3/R2: {e}")
            messagebox.showerror("Error S3/R2", str(e))
        except Exception as e:
            self.log_line(f"❌ Error: {e}")
            messagebox.showerror("Error", str(e))
        finally:
            self.upload_btn.config(state="normal")


if __name__ == "__main__":
    root = tk.Tk()
    app = R2UploaderGUI(root)
    root.mainloop()