# gui_phototools_basic.py
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Tus módulos
import tiff_to_jpeg as tj
import split_half_frames as sf
import frames_pic as fp

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

# ====== Pantalla 2: Split Half-Frames ======
class SplitHalfFramesFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.inp = tk.StringVar()
        self.out = tk.StringVar()
        self.threshold = tk.IntVar(value=getattr(sf, "THRESHOLD", 10))
        self.margin = tk.DoubleVar(value=getattr(sf, "MARGIN", 0.2))
        self.window = tk.IntVar(value=getattr(sf, "WINDOW", 20))
        self.pb = None
        self.log = None
        self.btn = None
        self._build()

    def _build(self):
        pad={'padx':10,'pady':6}
        ttk.Label(self, text="Split Half-Frames (detección banda negra central)", font=("TkDefaultFont", 12, "bold")).grid(column=0,row=0,columnspan=3,sticky="w",**pad)

        ttk.Label(self,text="Carpeta entrada (scans dobles):").grid(column=0,row=1,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.inp,width=54).grid(column=1,row=1,sticky="we",**pad)
        ttk.Button(self,text="Elegir…",command=lambda: choose_dir(self.inp,"Entrada scans")).grid(column=2,row=1,**pad)

        ttk.Label(self,text="Carpeta salida (cortes):").grid(column=0,row=2,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.out,width=54).grid(column=1,row=2,sticky="we",**pad)
        ttk.Button(self,text="Elegir…",command=lambda: choose_dir(self.out,"Salida cortes")).grid(column=2,row=2,**pad)

        ttk.Separator(self).grid(column=0,row=3,columnspan=3,sticky="we",**pad)

        ttk.Label(self,text="Threshold (0–255):").grid(column=0,row=4,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.threshold,width=10).grid(column=1,row=4,sticky="w",**pad)

        ttk.Label(self,text="Margin (0–0.5):").grid(column=0,row=5,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.margin,width=10).grid(column=1,row=5,sticky="w",**pad)

        ttk.Label(self,text="Window (px):").grid(column=0,row=6,sticky="w",**pad)
        ttk.Entry(self,textvariable=self.window,width=10).grid(column=1,row=6,sticky="w",**pad)

        self.pb = ttk.Progressbar(self, mode="determinate")
        self.pb.grid(column=0,row=7,columnspan=3,sticky="we",**pad)

        self.log = tk.Text(self, height=10)
        self.log.grid(column=0,row=8,columnspan=3,sticky="nsew",**pad)
        self.grid_rowconfigure(8, weight=1); self.grid_columnconfigure(1, weight=1)

        self.btn = ttk.Button(self,text="Procesar",command=self.start)
        self.btn.grid(column=2,row=9,sticky="e",**pad)

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

        sf.THRESHOLD = int(self.threshold.get())
        sf.MARGIN    = float(self.margin.get())
        sf.WINDOW    = int(self.window.get())

        self.pb["value"]=0; self.pb["maximum"]=len(files)
        self.log.delete("1.0","end")
        self.btn.state(["disabled"])
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
        menubar.add_cascade(label="Herramientas", menu=tools)
        menubar.add_command(label="Salir", command=self.destroy)

        self.container = ttk.Frame(self); self.container.pack(fill="both", expand=True)

        self.views = {
            "tiff":   TiffToJpegFrame(self.container),
            "split":  SplitHalfFramesFrame(self.container),
            "frames": FramesPicFrame(self.container),
        }
        for v in self.views.values():
            v.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Splash minimal
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
