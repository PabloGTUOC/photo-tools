import os
import re
from typing import Iterable, List, Tuple
from datetime import datetime
import fix_dates as fd

SAFE_CHARS = re.compile(r"[^A-Za-z0-9\-]+")
EXTS = fd.EXTS

# ---------- utilities ----------
def _extract_number_from_name(name: str) -> int:
    """Return the first integer found in the filename or 0."""
    m = re.search(r"(\d{1,5})", os.path.basename(name))
    return int(m.group(1)) if m else 0

def _parse_dt(s):
    if not s:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None

def best_datetime_for_sort(path):
    tag, val = fd.get_best_datetime(path)
    dt = _parse_dt(val)
    if dt:
        return dt.timestamp()
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0.0

# ---------- list files ----------
def list_media(folder: str, recursive: bool = False, exts: Iterable[str] = EXTS) -> List[str]:
    out: List[str] = []
    exts_lower = tuple(e.lower() for e in exts)
    if recursive:
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(exts_lower):
                    out.append(os.path.join(root, f))
    else:
        for f in os.listdir(folder):
            p = os.path.join(folder, f)
            if os.path.isfile(p) and f.lower().endswith(exts_lower):
                out.append(p)
    return out

# ---------- ordering ----------
def sort_files(files: List[str], mode: str = "exif") -> List[str]:
    """
    mode='exif' → by metadata timestamp, then name
    mode='name' → by numeric order extracted from filename
    """
    if mode == "name":
        return sorted(files, key=lambda p: (_extract_number_from_name(p), os.path.basename(p).lower()))
    else:
        return sorted(files, key=lambda p: (best_datetime_for_sort(p), os.path.basename(p).lower()))

# ---------- renaming core ----------
def _clean_token(s: str) -> str:
    s = (s or "").strip()
    s = s.replace(" ", "")
    s = s.replace("_", "-")
    s = SAFE_CHARS.sub("", s)
    return s

def build_prefix(yyyymm: str, tag: str, camera: str, film: str) -> str:
    yyyymm = re.sub(r"\D", "", (yyyymm or ""))
    if len(yyyymm) != 6:
        raise ValueError("YYYYMM must be 6 digits (e.g., 202509).")
    parts = [yyyymm, _clean_token(tag), _clean_token(camera), _clean_token(film)]
    parts = [p for p in parts if p]
    return "-".join(parts)

def zero_pad_width(n_items: int) -> int:
    return max(2, len(str(n_items)))

def plan_new_names(files: List[str], prefix: str, mode: str = "exif") -> List[Tuple[str, str]]:
    """
    mode='exif' or 'name' (filename-number)
    Returns list of (src, new_basename)
    """
    files_sorted = sort_files(files, mode)
    pad = zero_pad_width(len(files_sorted))
    plan: List[Tuple[str, str]] = []
    for i, src in enumerate(files_sorted, start=1):
        ext = os.path.splitext(src)[1].lower()
        dst_name = f"{prefix}-{i:0{pad}d}{ext}"
        plan.append((src, dst_name))
    return plan

def apply_plan(folder: str, plan: List[Tuple[str, str]], dry_run: bool = True) -> Tuple[int, int, List[str]]:
    ok = skipped = 0
    msgs: List[str] = []
    targets = set()
    for src, dst_name in plan:
        dst_path = os.path.join(os.path.dirname(src), dst_name)
        if dst_name in targets:
            skipped += 1
            msgs.append(f"⚠️  {os.path.basename(src)} → {dst_name} skipped (duplicate in batch)")
            continue
        if os.path.exists(dst_path) and os.path.abspath(dst_path) != os.path.abspath(src):
            skipped += 1
            msgs.append(f"⚠️  {os.path.basename(src)} → {dst_name} skipped (already exists)")
            continue
        targets.add(dst_name)
        if dry_run:
            msgs.append(f"🛈 {os.path.basename(src)} → {dst_name} (dry-run)")
        else:
            try:
                os.rename(src, dst_path)
                ok += 1
                msgs.append(f"✅ {os.path.basename(src)} → {dst_name}")
            except Exception as e:
                skipped += 1
                msgs.append(f"❌ {os.path.basename(src)} → {dst_name}: {e}")
    return ok, skipped, msgs
