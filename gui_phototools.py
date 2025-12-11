# gui_phototools_basic.py
import os
import threading
import tkinter as tk
import numpy as np
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageTk, ImageOps  # 👈 añadido para el preview

# Tus módulos
import tiff_to_jpeg as tj
import split_half_frames as sf
import frames_pic as fp
import fix_dates as fd
import rename_files as rn


# -------- Utilidades comunes --------
_last_dir = os.path.join(os.path.expanduser("~"), "Desktop")  # start in Desktop by default

def choose_dir(var: tk.StringVar, title: str):
    """Open folder picker remembering the last selected directory."""
    global _last_dir
    d = filedialog.askdirectory(title=title, initialdir=_last_dir)
    if d:
        var.set(d)
        _last_dir = d  # remember last chosen folder

def list_images(folder, exts):
    try:
        return [f for f in os.listdir(folder) if f.lower().endswith(exts)]
    except FileNotFoundError:
        return []

def safe_makedirs(path):
    os.makedirs(path, exist_ok=True)


# ====== Pantalla 1: TIFF → JPEG ======
class TiffToJpegFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.inp = tk.StringVar()
        self.out = tk.StringVar()
        self.max_long = tk.IntVar(value=getattr(tj, "MAX_LONG_EDGE", 2048))
        self.quality = tk.IntVar(value=getattr(tj, "JPEG_QUALITY", 90))
        self.pb = None
        self.log = None
        self.btn = None
        self._build()

    def _build(self):
        pad={'padx':10,'pady':6}
        ttk.Label(self, text="TIFF → JPEG (ligero / Instagram OK)", font=("TkDefaultFont", 12, "bold")).grid(column=0,row=0,columnspan=3,sticky="w",**pad)

        ttk.Label(self,text="Carpeta entrada (TIFF):").grid(column=0,row=1,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.inp,width=54).grid(column=1,row=1,sticky="we",**pad)
        ttk.Button(self,text="Elegir…",command=lambda: choose_dir(self.inp,"Entrada TIFF")).grid(column=2,row=1,**pad)

        ttk.Label(self,text="Carpeta salida (JPEG):").grid(column=0,row=2,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.out,width=54).grid(column=1,row=2,sticky="we",**pad)
        ttk.Button(self,text="Elegir…",command=lambda: choose_dir(self.out,"Salida JPEG")).grid(column=2,row=2,**pad)

        ttk.Separator(self).grid(column=0,row=3,columnspan=3,sticky="we",**pad)

        ttk.Label(self,text="Long edge máx (px):").grid(column=0,row=4,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.max_long,width=10).grid(column=1,row=4,sticky="w",**pad)

        ttk.Label(self,text="Calidad JPEG (70–95):").grid(column=0,row=5,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.quality,width=10).grid(column=1,row=5,sticky="w",**pad)

        self.pb = ttk.Progressbar(self, mode="determinate")
        self.pb.grid(column=0,row=6,columnspan=3,sticky="we",**pad)

        self.log = tk.Text(self, height=10)
        self.log.grid(column=0,row=7,columnspan=3,sticky="nsew",**pad)
        self.grid_rowconfigure(7, weight=1); self.grid_columnconfigure(1, weight=1)

        self.btn = ttk.Button(self,text="Procesar",command=self.start)
        self.btn.grid(column=2,row=8,sticky="e",**pad)

    def start(self):
        inp, out = self.inp.get().strip(), self.out.get().strip()
        if not inp or not os.path.isdir(inp):
            messagebox.showerror("Error","Selecciona una carpeta TIFF válida."); return
        if not out:
            messagebox.showerror("Error","Selecciona carpeta de salida."); return
        safe_makedirs(out)

        files = list_images(inp, (".tif",".tiff"))
        if not files:
            messagebox.showinfo("Info","No hay TIFFs en la carpeta."); return

        tj.MAX_LONG_EDGE = int(self.max_long.get())
        tj.JPEG_QUALITY  = int(self.quality.get())

        self.pb["value"]=0; self.pb["maximum"]=len(files)
        self.log.delete("1.0","end")
        self.btn.state(["disabled"])
        threading.Thread(target=self._run,args=(inp,out,files),daemon=True).start()

    def _run(self, inp, out, files):
        ok, fail = 0, 0
        for i, f in enumerate(files, 1):
            try:
                tj.convert_tiff(os.path.join(inp, f), out)
                ok += 1
                self.log.insert("end", f"✅ {f}\n")
            except Exception as e:
                fail += 1
                self.log.insert("end", f"❌ {f}: {e}\n")
            self.log.see("end"); self.pb["value"]=i
        self.log.insert("end", f"\nHecho. OK: {ok}, Fallos: {fail}\n")
        self.btn.state(["!disabled"])


# ====== Preview para Split Half-Frames ======
class SplitPreviewDialog(tk.Toplevel):
    def __init__(self, master, sample_path):
        super().__init__(master)
        self.title("Preview — Split Half-Frames")
        self.sample_path = sample_path
        self.resizable(True, True)

        # Variables ligadas a los parámetros
        self.var_dark   = tk.IntVar(value=getattr(sf, "THRESHOLD_DARK", 25))
        self.var_white  = tk.IntVar(value=getattr(sf, "THRESHOLD_WHITE", 235))
        self.var_tol    = tk.DoubleVar(value=getattr(sf, "BORDER_TOL", 0.92))
        self.var_maxpct = tk.DoubleVar(value=getattr(sf, "MAX_CROP_PCT", 0.12))
        self.var_margin = tk.DoubleVar(value=getattr(sf, "MARGIN", 0.20))
        self.var_window = tk.IntVar(value=getattr(sf, "WINDOW", 20))

        # ----- Controles -----
        control_frame = ttk.Frame(self)
        control_frame.pack(fill="x", padx=10, pady=6)

        def add_slider(label, var, frm, to, row):
            ttk.Label(control_frame, text=label, width=18).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            scale = ttk.Scale(control_frame, from_=frm, to=to, variable=var)
            scale.grid(row=row, column=1, sticky="we", padx=4, pady=2)
            entry = ttk.Entry(control_frame, textvariable=var, width=8)
            entry.grid(row=row, column=2, sticky="e", padx=4, pady=2)

        control_frame.columnconfigure(1, weight=1)

        add_slider("THRESHOLD_DARK",  self.var_dark,   5, 60,    0)
        add_slider("THRESHOLD_WHITE", self.var_white, 200, 255,  1)
        add_slider("BORDER_TOL",      self.var_tol,   0.70, 0.99, 2)
        add_slider("MAX_CROP_PCT",    self.var_maxpct, 0.05, 0.25, 3)
        add_slider("MARGIN",          self.var_margin, 0.10, 0.35, 4)
        add_slider("WINDOW",          self.var_window, 6, 64,     5)

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=4)
        ttk.Button(btns, text="Recalcular", command=self.refresh).pack(side="left")
        ttk.Button(btns, text="Usar estos parámetros", command=self.accept).pack(side="right")

        self.canvas = tk.Canvas(self, bg="#222")
        self.canvas.pack(fill="both", expand=True)

        self._preview_img = None
        self.bind("<Configure>", lambda e: self._redraw())
        self.refresh()

    # --- lógica de preview: copia de tu split_half_frames pero parametrizada ---
    def _process_for_preview(self):
        # Leer parámetros actuales de los sliders
        THRESHOLD_DARK = int(self.var_dark.get())
        THRESHOLD_WHITE = int(self.var_white.get())
        BORDER_TOL = float(self.var_tol.get())
        MAX_CROP_PCT = float(self.var_maxpct.get())
        MARGIN = float(self.var_margin.get())
        WINDOW = int(self.var_window.get())

        # Cargar imagen
        img = Image.open(self.sample_path)
        img = ImageOps.exif_transpose(img).convert("RGB")

        # ----- 1) autocrop lab border -----
        g = np.array(img.convert("L"))
        h, w = g.shape

        max_x = int(w * MAX_CROP_PCT)
        max_y = int(h * MAX_CROP_PCT)

        def scan_from_left():
            x = 0
            while x < max_x:
                col = g[:, x]
                if (col >= THRESHOLD_WHITE).mean() > BORDER_TOL or (col <= THRESHOLD_DARK).mean() > BORDER_TOL:
                    x += 1
                else:
                    break
            return x

        def scan_from_right():
            x = w - 1
            limit = w - max_x
            while x > limit:
                col = g[:, x]
                if (col >= THRESHOLD_WHITE).mean() > BORDER_TOL or (col <= THRESHOLD_DARK).mean() > BORDER_TOL:
                    x -= 1
                else:
                    break
            return w - 1 - x

        def scan_from_top():
            y = 0
            while y < max_y:
                row = g[y, :]
                if (row >= THRESHOLD_WHITE).mean() > BORDER_TOL or (row <= THRESHOLD_DARK).mean() > BORDER_TOL:
                    y += 1
                else:
                    break
            return y

        def scan_from_bottom():
            y = h - 1
            limit = h - max_y
            while y > limit:
                row = g[y, :]
                if (row >= THRESHOLD_WHITE).mean() > BORDER_TOL or (row <= THRESHOLD_DARK).mean() > BORDER_TOL:
                    y -= 1
                else:
                    break
            return h - 1 - y

        left_b   = scan_from_left()
        right_b  = scan_from_right()
        top_b    = scan_from_top()
        bottom_b = scan_from_bottom()

        x0 = min(max(0, left_b), w - 2)
        x1 = max(x0 + 1, w - right_b)
        y0 = min(max(0, top_b), h - 2)
        y1 = max(y0 + 1, h - bottom_b)

        img2 = img.crop((x0, y0, x1, y1))

        # ----- 2) buscar divisor -----
        g2 = np.array(img2.convert("L"))
        hh, ww = g2.shape
        start = int(ww * MARGIN)
        end   = int(ww * (1 - MARGIN))
        start = max(0, min(start, ww - 1))
        end   = max(start + 1, min(end, ww))

        profile = g2.mean(axis=0)
        idx = np.argmin(profile[start:end]) + start
        l = max(start, idx - WINDOW)
        r = min(end, idx + WINDOW)
        split_col = l + np.argmin(profile[l:r])

        # ----- 3) cortar y quitar bandas oscuras -----
        left = img2.crop((0, 0, split_col, img2.height))
        right = img2.crop((split_col, 0, img2.width, img2.height))

        def trim_dark_bands_local(im):
            g = np.array(im.convert("L"))
            h, w = g.shape

            top = 0
            while top < h and g[top, :].mean() < THRESHOLD_DARK:
                top += 1
            bottom = h - 1
            while bottom > 0 and g[bottom, :].mean() < THRESHOLD_DARK:
                bottom -= 1

            left = 0
            while left < w and g[:, left].mean() < THRESHOLD_DARK:
                left += 1
            right = w - 1
            while right > 0 and g[:, right].mean() < THRESHOLD_DARK:
                right -= 1

            x0 = max(0, min(left, right - 1))
            x1 = min(w, max(right + 1, x0 + 1))
            y0 = max(0, min(top, bottom - 1))
            y1 = min(h, max(bottom + 1, y0 + 1))
            return im.crop((x0, y0, x1, y1))

        left = trim_dark_bands_local(left)
        right = trim_dark_bands_local(right)

        return left, right

    def refresh(self):
        # recalcular preview con los parámetros actuales
        left, right = self._process_for_preview()

        gap = 16
        total_w = left.width + right.width + gap
        max_preview_w = 1400
        scale = min(1.0, max_preview_w / total_w)
        new_h = int(max(left.height, right.height) * scale)

        comp = Image.new("RGB", (int(total_w * scale), new_h), (40, 40, 40))
        Lr = left.resize((int(left.width * scale), int(left.height * scale)), Image.LANCZOS)
        Rr = right.resize((int(right.width * scale), int(right.height * scale)), Image.LANCZOS)

        comp.paste(Lr, (0, 0))
        comp.paste(Rr, (Lr.width + int(gap * scale), 0))

        self._preview_img = ImageTk.PhotoImage(comp)
        self._redraw()

    def _redraw(self):
        self.canvas.delete("all")
        if self._preview_img:
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            iw = self._preview_img.width()
            ih = self._preview_img.height()
            x = max(0, (cw - iw) // 2)
            y = max(0, (ch - ih) // 2)
            self.canvas.create_image(x, y, anchor="nw", image=self._preview_img)

    def accept(self):
        # cuando aceptas, copiamos a los globals de split_half_frames.py
        sf.THRESHOLD_DARK = int(self.var_dark.get())
        sf.THRESHOLD_WHITE = int(self.var_white.get())
        sf.BORDER_TOL = float(self.var_tol.get())
        sf.MAX_CROP_PCT = float(self.var_maxpct.get())
        sf.MARGIN = float(self.var_margin.get())
        sf.WINDOW = int(self.var_window.get())
        self.destroy()



# ====== Pantalla 2: Split Half-Frames ======
class SplitHalfFramesFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.inp = tk.StringVar()
        self.out = tk.StringVar()
        # Adaptado a la nueva versión de split_half_frames.py
        self.threshold = tk.IntVar(value=getattr(sf, "THRESHOLD_DARK", 25))
        self.margin = tk.DoubleVar(value=getattr(sf, "MARGIN", 0.20))
        self.window = tk.IntVar(value=getattr(sf, "WINDOW", 20))
        self.pb = None
        self.log = None
        self.btn = None
        self.btn_preview = None
        self._build()

    def _build(self):
        pad={'padx':10,'pady':6}
        ttk.Label(self, text="Split Half-Frames (auto-borde lab + banda central)", font=("TkDefaultFont", 12, "bold")).grid(column=0,row=0,columnspan=3,sticky="w",**pad)

        ttk.Label(self,text="Carpeta entrada (scans dobles):").grid(column=0,row=1,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.inp,width=54).grid(column=1,row=1,sticky="we",**pad)
        ttk.Button(self,text="Elegir…",command=lambda: choose_dir(self.inp,"Entrada scans")).grid(column=2,row=1,**pad)

        ttk.Label(self,text="Carpeta salida (cortes):").grid(column=0,row=2,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.out,width=54).grid(column=1,row=2,sticky="we",**pad)
        ttk.Button(self,text="Elegir…",command=lambda: choose_dir(self.out,"Salida cortes")).grid(column=2,row=2,**pad)

        ttk.Separator(self).grid(column=0,row=3,columnspan=3,sticky="we",**pad)

        ttk.Label(self,text="THRESHOLD_DARK (0–255):").grid(column=0,row=4,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.threshold,width=10).grid(column=1,row=4,sticky="w",**pad)

        ttk.Label(self,text="MARGIN (0–0.5):").grid(column=0,row=5,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.margin,width=10).grid(column=1,row=5,sticky="w",**pad)

        ttk.Label(self,text="WINDOW (px):").grid(column=0,row=6,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.window,width=10).grid(column=1,row=6,sticky="w",**pad)

        self.pb = ttk.Progressbar(self, mode="determinate")
        self.pb.grid(column=0,row=7,columnspan=3,sticky="we",**pad)

        self.log = tk.Text(self, height=10)
        self.log.grid(column=0,row=8,columnspan=3,sticky="nsew",**pad)
        self.grid_rowconfigure(8, weight=1); self.grid_columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(self)
        btn_frame.grid(column=0,row=9,columnspan=3,sticky="e",**pad)

        self.btn_preview = ttk.Button(btn_frame, text="Preview rollo…", command=self.preview)
        self.btn_preview.pack(side="left", padx=(0,8))

        self.btn = ttk.Button(btn_frame,text="Procesar",command=self.start)
        self.btn.pack(side="left")

    def preview(self):
        inp = self.inp.get().strip()
        if not inp or not os.path.isdir(inp):
            messagebox.showerror("Error","Selecciona una carpeta de entrada válida."); return

        # elegir el primer archivo compatible como muestra
        sample = None
        for f in os.listdir(inp):
            if f.lower().endswith((".jpg",".jpeg",".png",".tif",".tiff")):
                sample = os.path.join(inp, f)
                break
        if not sample:
            messagebox.showinfo("Info","No hay imágenes compatibles en la carpeta."); return

        # sincronizar los globals con lo que hay en los campos antes del preview
        sf.THRESHOLD_DARK = int(self.threshold.get())
        sf.MARGIN = float(self.margin.get())
        sf.WINDOW = int(self.window.get())

        dlg = SplitPreviewDialog(self, sample)
        self.wait_window(dlg)

        # al cerrar, los globals de sf ya reflejan los sliders del preview
        self.threshold.set(getattr(sf, "THRESHOLD_DARK", 25))
        self.margin.set(getattr(sf, "MARGIN", 0.20))
        self.window.set(getattr(sf, "WINDOW", 20))
        messagebox.showinfo("Preview", "Parámetros ajustados para este rollo.")

    def start(self):
        inp, out = self.inp.get().strip(), self.out.get().strip()
        if not inp or not os.path.isdir(inp):
            messagebox.showerror("Error","Selecciona una carpeta de entrada válida."); return
        if not out:
            messagebox.showerror("Error","Selecciona carpeta de salida."); return
        safe_makedirs(out)

        files = list_images(inp, (".jpg",".jpeg",".png",".tif",".tiff"))
        if not files:
            messagebox.showinfo("Info","No hay imágenes en la carpeta."); return

        # Aplicamos los campos simples a los globals clave
        sf.THRESHOLD_DARK = int(self.threshold.get())
        sf.MARGIN    = float(self.margin.get())
        sf.WINDOW    = int(self.window.get())

        self.pb["value"]=0; self.pb["maximum"]=len(files)
        self.log.delete("1.0","end")
        self.btn.state(["disabled"])
        self.btn_preview.state(["disabled"])
        threading.Thread(target=self._run,args=(inp,out,files),daemon=True).start()

    def _run(self, inp, out, files):
        ok, fail = 0, 0
        for i, f in enumerate(files, 1):
            try:
                sf.split_half_frame(os.path.join(inp, f), out)
                ok += 1
                self.log.insert("end", f"✅ {f}\n")
            except Exception as e:
                fail += 1
                self.log.insert("end", f"❌ {f}: {e}\n")
            self.log.see("end"); self.pb["value"]=i
        self.log.insert("end", f"\nHecho. OK: {ok}, Fallos: {fail}\n")
        self.btn.state(["!disabled"])
        self.btn_preview.state(["!disabled"])


# ====== Pantalla 3: Marcos 4:5 / 5:4 ======
class FramesPicFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.inp = tk.StringVar()
        self.out = tk.StringVar()
        self.long_edge = tk.IntVar(value=getattr(fp, "OUTPUT_LONG_SIDE", 3000))
        self.min_border = tk.IntVar(value=getattr(fp, "MIN_BORDER", 50))
        self.corner_pct = tk.DoubleVar(value=getattr(fp, "CORNER_RADIUS_PCT", 0.02))
        self.upscale = tk.BooleanVar(value=getattr(fp, "UPSCALE_SMALLER", True))
        self.pb = None
        self.log = None
        self.btn = None
        self._build()

    def _build(self):
        pad={'padx':10,'pady':6}
        ttk.Label(self, text="Marcos (Portrait 4:5 / Landscape 5:4) con esquinas redondeadas", font=("TkDefaultFont", 12, "bold")).grid(column=0,row=0,columnspan=3,sticky="w",**pad)

        ttk.Label(self,text="Carpeta entrada:").grid(column=0,row=1,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.inp,width=54).grid(column=1,row=1,sticky="we",**pad)
        ttk.Button(self,text="Elegir…",command=lambda: choose_dir(self.inp,"Entrada fotos")).grid(column=2,row=1,**pad)

        ttk.Label(self,text="Carpeta salida:").grid(column=0,row=2,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.out,width=54).grid(column=1,row=2,sticky="we",**pad)
        ttk.Button(self,text="Elegir…",command=lambda: choose_dir(self.out,"Salida")).grid(column=2,row=2,**pad)

        ttk.Separator(self).grid(column=0,row=3,columnspan=3,sticky="we",**pad)

        ttk.Label(self,text="Long edge (px):").grid(column=0,row=4,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.long_edge,width=10).grid(column=1,row=4,sticky="w",**pad)

        ttk.Label(self,text="Borde mínimo (px):").grid(column=0,row=5,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.min_border,width=10).grid(column=1,row=5,sticky="w",**pad)

        ttk.Label(self,text="Radio esquinas (% del lado corto):").grid(column=0,row=6,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.corner_pct,width=10).grid(column=1,row=6,sticky="w",**pad)

        ttk.Checkbutton(self,text="Reescalar si es más pequeña (upscale)",variable=self.upscale)\
            .grid(column=0,row=7,columnspan=2,sticky="w",**pad)

        self.pb = ttk.Progressbar(self, mode="determinate")
        self.pb.grid(column=0,row=8,columnspan=3,sticky="we",**pad)

        self.log = tk.Text(self, height=10)
        self.log.grid(column=0,row=9,columnspan=3,sticky="nsew",**pad)
        self.grid_rowconfigure(9, weight=1); self.grid_columnconfigure(1, weight=1)

        self.btn = ttk.Button(self,text="Procesar",command=self.start)
        self.btn.grid(column=2,row=10,sticky="e",**pad)

    def start(self):
        inp, out = self.inp.get().strip(), self.out.get().strip()
        if not inp or not os.path.isdir(inp):
            messagebox.showerror("Error","Selecciona entrada válida."); return
        if not out:
            messagebox.showerror("Error","Selecciona carpeta de salida."); return
        safe_makedirs(out)

        files = list_images(inp, (".jpg",".jpeg",".png",".tif",".tiff"))
        if not files:
            messagebox.showinfo("Info","No hay imágenes en la carpeta."); return

        fp.OUTPUT_LONG_SIDE = int(self.long_edge.get())
        fp.MIN_BORDER = int(self.min_border.get())
        fp.CORNER_RADIUS_PCT = float(self.corner_pct.get())
        fp.UPSCALE_SMALLER = bool(self.upscale.get())

        self.pb["value"]=0; self.pb["maximum"]=len(files)
        self.log.delete("1.0","end")
        self.btn.state(["disabled"])
        threading.Thread(target=self._run,args=(inp,out,files),daemon=True).start()

    def _run(self, inp, out, files):
        ok, fail = 0, 0
        for i, f in enumerate(files, 1):
            try:
                src = os.path.join(inp, f)
                name, _ = os.path.splitext(f)
                dst = os.path.join(out, f"{name}_blog.jpg")
                fp.process_image(src, dst)
                ok += 1
                self.log.insert("end", f"✅ {f}\n")
            except Exception as e:
                fail += 1
                self.log.insert("end", f"❌ {f}: {e}\n")
            self.log.see("end"); self.pb["value"]=i
        self.log.insert("end", f"\nHecho. OK: {ok}, Fallos: {fail}\n")
        self.btn.state(["!disabled"])


# ====== Pantalla 4: Cambiar fechas ======
class FixDatesFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.inp = tk.StringVar()
        self.recursive = tk.BooleanVar(value=True)
        self.dry_run = tk.BooleanVar(value=True)   # por defecto en prueba
        self.pb = None; self.log = None; self.btn = None
        self._build()

    def _build(self):
        pad={'padx':10,'pady':6}
        ttk.Label(self, text="Fix Dates — EXIF DateTimeOriginal → FileCreate/Modify", font=("TkDefaultFont", 12, "bold")).grid(column=0,row=0,columnspan=3,sticky="w",**pad)

        ttk.Label(self,text="Carpeta entrada:").grid(column=0,row=1,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.inp,width=54).grid(column=1,row=1,sticky="we",**pad)
        ttk.Button(self,text="Elegir…",command=lambda: choose_dir(self.inp,"Carpeta con fotos")).grid(column=2,row=1,**pad)

        ttk.Separator(self).grid(column=0,row=2,columnspan=3,sticky="we",**pad)

        ttk.Checkbutton(self,text="Recursivo (subcarpetas)",variable=self.recursive).grid(column=0,row=3,sticky="w",**pad)
        ttk.Checkbutton(self,text="Dry-run (no cambia nada)",variable=self.dry_run).grid(column=1,row=3,sticky="w",**pad)

        self.pb = ttk.Progressbar(self, mode="determinate")
        self.pb.grid(column=0,row=4,columnspan=3,sticky="we",**pad)

        self.log = tk.Text(self, height=12)
        self.log.grid(column=0,row=5,columnspan=3,sticky="nsew",**pad)
        self.grid_rowconfigure(5, weight=1); self.grid_columnconfigure(1, weight=1)

        self.btn = ttk.Button(self,text="Ejecutar",command=self.start)
        self.btn.grid(column=2,row=6,sticky="e",**pad)

    def start(self):
        folder = self.inp.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error","Selecciona una carpeta válida."); return
        if not fd.has_exiftool():
            messagebox.showerror("Error","ExifTool no encontrado. Instálalo con: brew install exiftool"); return

        total = sum(1 for _ in fd.iter_files(folder, recursive=self.recursive.get()))
        if total == 0:
            messagebox.showinfo("Info","No se encontraron imágenes soportadas."); return

        self.pb["value"]=0; self.pb["maximum"]=total
        self.log.delete("1.0","end")
        self.btn.state(["disabled"])
        threading.Thread(target=self._run,args=(folder,total),daemon=True).start()

    def _run(self, folder, total):
        ok = fail = i = 0
        recursive = self.recursive.get()
        dry_run = self.dry_run.get()
        try:
            for path in fd.iter_files(folder, recursive=recursive):
                success, msg = fd.set_file_times_from_best(path, dry_run=dry_run)
                self.log.insert("end", msg + "\n"); self.log.see("end")
                i += 1; self.pb["value"] = i
                if success: ok += 1
                else: fail += 1
            self.log.insert("end", f"\nHecho. OK: {ok}, Fallos: {fail}\n")
            if dry_run:
                self.log.insert("end", "Dry-run activado: no se modificó ningún archivo.\n")
        except Exception as e:
            self.log.insert("end", f"\n❌ Error: {e}\n")
            messagebox.showerror("Error", str(e))
        finally:
            self.btn.state(["!disabled"])


# ====== Pantalla 5: Cambiar nombres ======
class RenameFilesFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.folder = tk.StringVar()
        self.recursive = tk.BooleanVar(value=False)  # default: current folder only
        self.yyyymm = tk.StringVar()
        self.tag = tk.StringVar()
        self.camera = tk.StringVar()
        self.film = tk.StringVar()
        self.dry_run = tk.BooleanVar(value=True)     # safer default
        self.pb = None; self.log = None; self.btn = None
        self._build()

    def _build(self):
        pad={'padx':10,'pady':6}
        ttk.Label(self, text="Rename — YYYYMM-Tag-Camera-Film-###", font=("TkDefaultFont", 12, "bold")).grid(column=0,row=0,columnspan=4,sticky="w",**pad)

        ttk.Label(self,text="Folder:").grid(column=0,row=1,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.folder,width=54).grid(column=1,row=1,sticky="we",**pad)
        ttk.Button(self,text="Choose…",command=lambda: choose_dir(self.folder,"Folder to rename")).grid(column=2,row=1,**pad)
        ttk.Checkbutton(self,text="Recursive",variable=self.recursive).grid(column=3,row=1,sticky="w",**pad)

        ttk.Separator(self).grid(column=0,row=2,columnspan=4,sticky="we",**pad)

        ttk.Label(self,text="YYYYMM:").grid(column=0,row=3,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.yyyymm,width=10).grid(column=1,row=3,sticky="w",**pad)

        ttk.Label(self,text="Tag:").grid(column=0,row=4,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.tag,width=24).grid(column=1,row=4,sticky="w",**pad)

        ttk.Label(self,text="Camera:").grid(column=0,row=5,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.camera,width=24).grid(column=1,row=5,sticky="w",**pad)

        ttk.Label(self,text="Film:").grid(column=0,row=6,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.film,width=24).grid(column=1,row=6,sticky="w",**pad)

        ttk.Checkbutton(self,text="Dry-run (preview only)",variable=self.dry_run).grid(column=0,row=7,sticky="w",**pad)

        self.pb = ttk.Progressbar(self, mode="determinate")
        self.pb.grid(column=0,row=8,columnspan=4,sticky="we",**pad)

        self.log = tk.Text(self, height=12)
        self.log.grid(column=0,row=9,columnspan=4,sticky="nsew",**pad)
        self.grid_rowconfigure(9, weight=1); self.grid_columnconfigure(1, weight=1)

        self.btn = ttk.Button(self,text="Rename",command=self.start)
        self.btn.grid(column=3,row=10,sticky="e",**pad)

    def start(self):
        folder = self.folder.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror("Error","Choose a valid folder."); return
        try:
            prefix = rn.build_prefix(self.yyyymm.get(), self.tag.get(), self.camera.get(), self.film.get())
        except ValueError as e:
            messagebox.showerror("Error", str(e)); return

        files = rn.list_media(folder, recursive=self.recursive.get(), exts=rn.EXTS)
        if not files:
            messagebox.showinfo("Info","No supported media found."); return

        mode = messagebox.askquestion(
            "Ordering preference",
            "Use EXIF metadata date to order files?\n"
            "Choose 'No' to order by numeric sequence in filenames.",
            icon="question"
        )
        mode = "exif" if mode == "yes" else "name"
        plan = rn.plan_new_names(files, prefix, mode=mode)

        self.pb["value"]=0; self.pb["maximum"]=len(plan)
        self.log.delete("1.0","end")
        self.btn.state(["disabled"])

        threading.Thread(target=self._run,args=(folder, plan),daemon=True).start()

    def _run(self, folder, plan):
        ok = skipped = i = 0
        for src, dst in plan:
            _ok, _sk, msgs = rn.apply_plan(os.path.dirname(src), [(src, dst)], dry_run=self.dry_run.get())
            ok += _ok; skipped += _sk
            self.log.insert("end", msgs[0] + "\n")
            self.log.see("end")
            i += 1; self.pb["value"]=i

        self.log.insert("end", f"\nDone. Renamed: {ok}, Skipped: {skipped}\n")
        if self.dry_run.get():
            self.log.insert("end", "Dry-run was ON — no files were changed.\n")
        self.btn.state(["!disabled"])


# ====== App principal (menú simple) ======
class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Photo Tools — Básico")
        self.geometry("860x560")
        self.minsize(820, 520)

        menubar = tk.Menu(self); self.config(menu=menubar)
        tools = tk.Menu(menubar, tearoff=0)
        tools.add_command(label="TIFF → JPEG", command=lambda: self.show("tiff"))
        tools.add_command(label="Split Half-Frames", command=lambda: self.show("split"))
        tools.add_command(label="Marcos 4:5 / 5:4", command=lambda: self.show("frames"))
        tools.add_command(label="Fix Dates (EXIF → File)", command=lambda: self.show("fixdates"))
        tools.add_command(label="Rename (YYYYMM-Tag-Camera-Film)", command=lambda: self.show("rename"))
        menubar.add_cascade(label="Herramientas", menu=tools)
        menubar.add_command(label="Salir", command=self.destroy)

        self.container = ttk.Frame(self); self.container.pack(fill="both", expand=True)

        self.views = {
            "tiff":   TiffToJpegFrame(self.container),
            "split":  SplitHalfFramesFrame(self.container),
            "frames": FramesPicFrame(self.container),
            "fixdates": FixDatesFrame(self.container),
            "rename": RenameFilesFrame(self.container),
        }
        for v in self.views.values():
            v.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.splash = ttk.Frame(self.container)
        self.splash.place(relx=0, rely=0, relwidth=1, relheight=1)
        ttk.Label(self.splash, text="Photo Tools — Básico", font=("TkDefaultFont", 16, "bold")).pack(pady=18)
        ttk.Label(self.splash, text="Abre un módulo desde el menú «Herramientas».").pack()

    def show(self, key):
        if hasattr(self, "splash"):
            self.splash.place_forget()
        for v in self.views.values():
            v.place_forget()
        self.views[key].place(relx=0, rely=0, relwidth=1, relheight=1)
        self.views[key].lift()


if __name__ == "__main__":
    MainApp().mainloop()
