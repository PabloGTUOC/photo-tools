# fix_dates.py
import os
import shutil
import subprocess
from typing import Iterable, Tuple, Optional
from datetime import datetime
import re
import json

# Extensiones de imagen + vídeo
EXTS = (
    ".jpg", ".jpeg", ".heic", ".heif", ".png", ".gif",
    ".tif", ".tiff", ".dng", ".nef", ".arw", ".cr2", ".raf",
    ".mov", ".mp4", ".m4v", ".mts", ".m2ts", ".3gp", ".avi"
)

# Orden de preferencia de tags de fecha (fotos y vídeos)
TAG_CANDIDATES = [
    "DateTimeOriginal",  # fotos
    "CreateDate",  # fotos/vídeos (QuickTime:CreateDate)
    "MediaCreateDate",  # vídeos (QuickTime:MediaCreateDate)
    "TrackCreateDate",  # vídeos (QuickTime:TrackCreateDate)
    "CreationDate",  # Keys:CreationDate (muy común en iPhone vídeos exportados)
]

# ---------- ExifTool metadata reader ----------
def read_metadata(path: str) -> dict:
    """
    Returns a dict of tags -> values using exiftool JSON.
    Keys are like 'EXIF:DateTimeOriginal', 'QuickTime:CreateDate', etc.
    """
    et = shutil.which("exiftool")
    if not et:
        return {}
    try:
        out = subprocess.check_output(
            [et, "-j", "-a", "-G1", "-s", path],
            stderr=subprocess.DEVNULL
        )
        arr = json.loads(out.decode("utf-8", errors="ignore"))
        return arr[0] if arr else {}
    except Exception:
        return {}



def _to_text(v):
    """Return a clean str or None."""
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        v = v[0]
    if isinstance(v, bytes):
        try:
            v = v.decode("utf-8")
        except Exception:
            v = v.decode("latin-1", "ignore")
    else:
        v = str(v)
    v = v.strip()
    if not v or v == "0000:00:00 00:00:00":
        return None
    return v

def _normalize_dt_string(s):
    """
    Accepts many shapes and returns 'YYYY:MM:DD HH:MM:SS' or None.
    Examples:
      2024:04:28 14:19:45
      2024-04-28 14:19:45
      2024-04-28T14:19:45+02:00
    """
    s = _to_text(s)
    if not s:
        return None
    # drop timezone suffix (e.g., +02:00 or Z)
    s = re.sub(r"(?:[T ])(\d{2}:\d{2}:\d{2}).*$", r" \1", s.replace("T", " "))
    # first two '-' to ':' so 'YYYY-MM-DD HH:MM:SS' -> 'YYYY:MM:DD HH:MM:SS'
    if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", s):
        s = s.replace("-", ":", 2)
    if re.match(r"\d{4}:\d{2}:\d{2} \d{2}:\d{2}:\d{2}", s):
        return s[:19]
    return None
def _find_exe(name: str, extra: list[str] | None = None) -> str | None:
    """
    Find an executable even when PATH is minimal (PyInstaller app).
    Tries shutil.which + common Homebrew paths + user-supplied extras.
    """
    extra = extra or []
    # 1) current PATH
    p = shutil.which(name)
    if p:
        return p
    # 2) common macOS/Homebrew locations
    common = [
        f"/opt/homebrew/bin/{name}",   # Apple Silicon default
        f"/usr/local/bin/{name}",      # Intel default
        f"/usr/bin/{name}",
    ] + extra
    for c in common:
        if os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return None

EXIFTOOL = _find_exe("exiftool")
SETFILE  = _find_exe("SetFile")

def _subproc_env() -> dict:
    """Ensure PATH includes Homebrew dirs when called from a bundled app."""
    env = os.environ.copy()
    extra = "/opt/homebrew/bin:/usr/local/bin"
    env["PATH"] = (env.get("PATH") or "") + (("" if env.get("PATH","").endswith(":") else ":") + extra)
    return env

def has_exiftool() -> bool:
    return EXIFTOOL is not None

def has_setfile() -> bool:
    return SETFILE is not None

def iter_files(folder: str, recursive: bool = True, exts: Iterable[str] = EXTS):
    exts_lower = tuple(e.lower() for e in exts)
    if recursive:
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(exts_lower):
                    yield os.path.join(root, f)
    else:
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if os.path.isfile(path) and f.lower().endswith(exts_lower):
                yield path

def _read_tags(path: str, tags: list[str]) -> dict:
    """
    Devuelve {tag: valor} con formato 'YYYY:MM:DD HH:MM:SS' para los tags pedidos.
    Para QuickTime, leemos como UTC para evitar desplazamientos erróneos.
    """
    args = ["exiftool", "-api", "QuickTimeUTC=1", "-s", "-s", "-s", "-d", "%Y:%m:%d %H:%M:%S"]
    for t in tags:
        args.append(f"-{t}")
    args.append(path)
    try:
        out = subprocess.check_output(
        [EXIFTOOL, "-time:all", "-a", "-G1", "-s", "-api", "QuickTimeUTC=1", path],
              stderr=subprocess.STDOUT,
              env=_subproc_env(),
        )
    except subprocess.CalledProcessError:
        return {}
    lines = [ln.strip() for ln in out.splitlines()]
    values = {}
    for i, t in enumerate(tags):
        if i < len(lines) and lines[i]:
            values[t] = lines[i]
    return values

def get_best_datetime(path):
    """
    Returns (tag, 'YYYY:MM:DD HH:MM:SS') or (None, None)
    """
    md = read_metadata(path)  # your existing function
    # Order of preference: stills EXIF, then QuickTime dates, then XMP/Keys.
    candidates = [
        ("EXIF:DateTimeOriginal", md.get("EXIF:DateTimeOriginal")),
        ("EXIF:CreateDate",       md.get("EXIF:CreateDate")),
        ("QuickTime:CreationDate",md.get("QuickTime:CreationDate")),
        ("QuickTime:CreateDate",  md.get("QuickTime:CreateDate")),
        ("Keys:CreationDate",     md.get("Keys:CreationDate")),
        ("XMP:CreateDate",        md.get("XMP:CreateDate")),
        ("QuickTime:ModifyDate",  md.get("QuickTime:ModifyDate")),
    ]
    for tag, raw in candidates:
        val = _normalize_dt_string(raw)
        if val:
            return tag, val
    return None, None


def _mac_stat_times(path: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Lee birth time y mtime con os.stat (sólo macOS expone st_birthtime).
    """
    st = os.stat(path)
    created = getattr(st, "st_birthtime", None)
    modified = st.st_mtime
    c_dt = datetime.fromtimestamp(created) if created else None
    m_dt = datetime.fromtimestamp(modified) if modified else None
    return c_dt, m_dt

def _exif_to_setfile_fmt(dt: str) -> str:
    """
    'YYYY:MM:DD HH:MM:SS' -> 'MM/DD/YYYY HH:MM:SS' (hora local).
    """
    # dt viene sin zona (ya interpretado con QuickTimeUTC=1 al leer).
    y, mo, d = dt[0:4], dt[5:7], dt[8:10]
    return f"{mo}/{d}/{y} {dt[11:19]}"

def _close_enough(a: Optional[datetime], b: Optional[datetime], seconds: int = 2) -> bool:
    if not a or not b:
        return False
    return abs((a - b).total_seconds()) <= seconds

def set_file_times_from_best(path: str, dry_run: bool = False) -> Tuple[bool, str]:
    lower = path.lower()
    is_video = lower.endswith((".mov", ".mp4", ".m4v", ".mts", ".m2ts", ".3gp", ".avi"))

    tag, val = get_best_datetime(path)
    base = os.path.basename(path)
    if not tag or not val:
        return False, f"⚠️  {base} — sin fecha utilizable ({', '.join(TAG_CANDIDATES)})"

    if dry_run:
        what = "FileCreate/Modify + QuickTime" if is_video else "FileCreate/Modify + EXIF"
        return True, f"🛈 {base} → (dry-run) {what} = {val} (from {tag})"

    before_c, before_m = _mac_stat_times(path)

    # 1) Write metadata + filesystem via exiftool
    cmd = ["exiftool", "-overwrite_original"]
    cmd += [f"-FileCreateDate<{tag}", f"-FileModifyDate<{tag}"]
    if is_video:
        cmd += [
            f"-CreateDate<{tag}",
            f"-ModifyDate<{tag}",
            f"-MediaCreateDate<{tag}",
            f"-TrackCreateDate<{tag}",
        ]
    else:
        cmd += [
            f"-CreateDate<{tag}",
            f"-ModifyDate<{tag}",
            f"-AllDates<{tag}",
        ]
    cmd.append(path)

    try:
        subprocess.check_output([EXIFTOOL, "-overwrite_original", ... , path],
                        stderr=subprocess.STDOUT,
                        env=_subproc_env())
    except subprocess.CalledProcessError as e:
        return False, f"❌ {base} — {e.output.decode('utf-8', errors='ignore').strip()}"

    # 2) Try to parse target datetime; if it fails, we’re done (metadata OK; FS maybe not)
    try:
        target_dt = datetime.strptime(val, "%Y:%m:%d %H:%M:%S")
    except Exception:
        return True, f"✅ {base} → {val} (from {tag}); ⚠️ no se pudo forzar birth time del FS (fecha no parseable)"

    after_c, after_m = _mac_stat_times(path)
    need_fallback = not (_close_enough(after_c, target_dt) and _close_enough(after_m, target_dt))

    # 3) macOS fallback for birth time (SetFile), only if needed
    if need_fallback and has_setfile():
        setfile_date = _exif_to_setfile_fmt(val)
        try:
            subprocess.run([SETFILE, "-d", setfile_date, path], check=True, env=_subproc_env())
            subprocess.run([SETFILE, "-m", setfile_date, path], check=True, env=_subproc_env())
            after_c, after_m = _mac_stat_times(path)
        except subprocess.CalledProcessError:
            pass

    ok_fs = _close_enough(after_c, target_dt) and _close_enough(after_m, target_dt)
    suffix = " (SetFile fallback)" if need_fallback and ok_fs else ""
    if ok_fs:
        return True, f"✅ {base} → {val} (from {tag}){suffix}"
    else:
        return True, f"✅ {base} → {val} (from {tag}); ⚠️ birth time del FS puede no haber cambiado"

def fix_dates_in_folder(folder: str, recursive: bool = True, dry_run: bool = False) -> Tuple[int, int]:
    """
    Procesa todos los archivos en folder. Devuelve (ok, fallos).
    """
    if not has_exiftool():
        raise RuntimeError("ExifTool no encontrado. Instálalo con: brew install exiftool")

    ok = fail = 0
    for path in iter_files(folder, recursive=recursive):
        success, msg = set_file_times_from_best(path, dry_run=dry_run)
        print(msg)
        if success: ok += 1
        else: fail += 1
    return ok, fail
