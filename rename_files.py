# rename_files.py
import os
import re
from typing import Iterable, List, Tuple, Optional
from datetime import datetime

import fix_dates as fd  # reuse get_best_datetime() and EXTS

SAFE_CHARS = re.compile(r"[^A-Za-z0-9\-]+")

# Use the same extensions list as the rest of your toolkit
EXTS = fd.EXTS

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
    # fallback to filesystem mtime
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0.0
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

def _fs_datetime(path: str) -> datetime:
    st = os.stat(path)
    # birth time if available, else mtime
    created = getattr(st, "st_birthtime", None)
    ts = created if created else st.st_mtime
    return datetime.fromtimestamp(ts)

def best_datetime_for_sort(path: str) -> datetime:
    tag, val = fd.get_best_datetime(path)
    if tag and val and not val.startswith("0000:00:00"):
        try:
            return datetime.strptime(val, "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass
    return _fs_datetime(path)

def _clean_token(s: str) -> str:
    s = (s or "").strip()
    s = s.replace(" ", "")          # remove spaces
    s = s.replace("_", "-")         # normalize underscores to hyphens
    s = SAFE_CHARS.sub("", s)       # keep only A-Z a-z 0-9 and hyphen
    return s

def build_prefix(yyyymm: str, tag: str, camera: str, film: str) -> str:
    # yyyymm must be exactly 6 digits
    yyyymm = re.sub(r"\D", "", (yyyymm or ""))
    if len(yyyymm) != 6:
        raise ValueError("YYYYMM must be 6 digits (e.g., 202509).")
    parts = [yyyymm, _clean_token(tag), _clean_token(camera), _clean_token(film)]
    # drop empty trailing parts
    parts = [p for p in parts if p]
    return "-".join(parts)

def zero_pad_width(n_items: int) -> int:
    return max(2, len(str(n_items)))

def plan_new_names(files: List[str], prefix: str) -> List[Tuple[str, str]]:
    """Return list of (src, dst) with dst only the basename (no folder)."""
    # Sort by best date, then by filename to stabilize ties
    files_sorted = sorted(files, key=lambda p: (best_datetime_for_sort(p), os.path.basename(p).lower()))
    pad = zero_pad_width(len(files_sorted))
    plan: List[Tuple[str, str]] = []
    for i, src in enumerate(files_sorted, start=1):
        ext = os.path.splitext(src)[1].lower()
        dst_name = f"{prefix}-{i:0{pad}d}{ext}"
        plan.append((src, dst_name))
    return plan

def apply_plan(folder: str, plan: List[Tuple[str, str]], dry_run: bool = True) -> Tuple[int, int, List[str]]:
    """
    Rename in place inside 'folder'. Returns (ok, skipped, messages).
    If a target name exists, we skip and report.
    """
    ok = skipped = 0
    msgs: List[str] = []
    # Build a map for collision detection within the batch
    targets = set()
    for src, dst_name in plan:
        dst_path = os.path.join(os.path.dirname(src), dst_name)  # rename in place
        # avoid accidental cross-folder operations
        if os.path.dirname(src) != folder:
            # If user listed recursively, still rename in their own subfolder
            pass
        # Collision checks
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
