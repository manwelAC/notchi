import os
import io
import sys
import time
import json
import math
import hashlib
import base64
import ctypes
from ctypes import wintypes
import socket
import tempfile
import threading
import queue
import webbrowser
import urllib.request
import urllib.error
import urllib.parse
from types import SimpleNamespace
from pathlib import Path
from datetime import datetime
from collections import Counter
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk, ImageFont
from notchi_updater import APP_VERSION, check_release, download_release, launch_installer

# Enable Per-Monitor DPI awareness on Windows for razor-sharp typography & exact multi-monitor bounds
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi

SINGLE_INSTANCE_PORT = 47831
OVERFLOW_STATUS_KEY = "__notchi_other_statuses__"
WINDOW_CONTROL_COLORS = ("#ff5f57", "#febc2e", "#28c840")

TRANSPARENT_KEY = "#010203"
TRANSPARENT_RGB = (1, 2, 3)

# Authentic macOS Dark / Alcove Hardware Palette (Restrained, high-contrast monochrome + precise semantic dots)
NOTCH_BG = (9, 9, 11)             # True hardware bezel black (#09090b)
SURFACE_CARD = (20, 20, 24)       # Elevated dark card (#141418)
SURFACE_ELEVATED = (30, 30, 36)   # Active pill / hover card (#1e1e24)
BORDER_HAIRLINE = (38, 38, 46)    # 1px hairline border (#26262e)

TEXT_PRIMARY = (244, 244, 246)    # Crisp off-white (#f4f4f6)
TEXT_SECONDARY = (161, 161, 170)  # Neutral zinc grey (#a1a1aa)
TEXT_MUTED = (105, 105, 115)      # Subtle caption grey (#696973)

# Semantic status accents (used sparingly for 8px dots and progress ring segments only)
COLOR_DONE = (50, 215, 75)           # macOS System Green
COLOR_COMPLETED = (48, 209, 158)     # Mint Green
COLOR_IN_PROGRESS = (10, 132, 255)   # macOS System Blue
COLOR_APPROVAL = (100, 210, 255)     # macOS Cyan
COLOR_PREREQ = (94, 92, 230)         # macOS Indigo
COLOR_SELECTED = (212, 165, 116)     # Warm Sand
COLOR_ON_HOLD = (255, 159, 10)       # macOS Amber
COLOR_RETURNED = (255, 69, 58)       # macOS Coral Red
COLOR_BACKLOG = (142, 142, 147)      # macOS System Grey

KANBAN_STATUSES = [
    ("Backlog", "Backlog", COLOR_BACKLOG),
    ("On Hold", "On Hold", COLOR_ON_HOLD),
    ("Returned", "Returned", COLOR_RETURNED),
    ("Selected for Development", "Selected for Dev", COLOR_SELECTED),
    ("In Progress", "In Progress", COLOR_IN_PROGRESS),
    ("Prerequisite", "Prerequisite", COLOR_PREREQ),
    ("DEPLOYMENT/APPROVAL", "Approval / Deploy", COLOR_APPROVAL),
    ("COMPLETED", "Completed", COLOR_COMPLETED),
    ("Done", "Done", COLOR_DONE),
]

# Master semantic catalog for all Kanban workflow statuses across all 24 Jira spaces
STATUS_STYLE_CATALOG = {
    "BACKLOG": ("Backlog", COLOR_BACKLOG, 10),
    "TO DO": ("To Do", COLOR_BACKLOG, 12),
    "CREATED": ("Created", COLOR_BACKLOG, 14),
    "PARKING LOT": ("Parking Lot", COLOR_BACKLOG, 15),
    "DISCOVERY": ("Discovery", COLOR_BACKLOG, 16),
    "ON HOLD": ("On Hold", COLOR_ON_HOLD, 20),
    "RETURNED": ("Returned", COLOR_RETURNED, 30),
    "RETURNED WITH FINDINGS": ("Returned (Findings)", COLOR_RETURNED, 31),
    "SELECTED FOR DEVELOPMENT": ("Selected for Dev", COLOR_SELECTED, 40),
    "TASK": ("Task", COLOR_SELECTED, 42),
    "DRAFTING": ("Drafting", COLOR_SELECTED, 44),
    "READY FOR DELIVERY": ("Ready for Delivery", COLOR_SELECTED, 45),
    "IN PROGRESS": ("In Progress", COLOR_IN_PROGRESS, 50),
    "IN PROGRESS (DEVS)": ("In Progress (Dev)", COLOR_IN_PROGRESS, 51),
    "DELIVERY": ("Delivery", COLOR_IN_PROGRESS, 52),
    "IQA IN PROGRESS": ("IQA In Progress", COLOR_APPROVAL, 55),
    "FOR QA": ("For QA", COLOR_APPROVAL, 56),
    "IN REVIEW": ("In Review", COLOR_APPROVAL, 58),
    "PREREQUISITE": ("Prerequisite", COLOR_PREREQ, 60),
    "READY FOR LAUNCH": ("Ready for Launch", COLOR_PREREQ, 62),
    "DEPLOYMENT/APPROVAL": ("Approval / Deploy", COLOR_APPROVAL, 70),
    "READY FOR DEPLOYMENT": ("Ready for Deploy", COLOR_APPROVAL, 72),
    "APPROVED": ("Approved", COLOR_COMPLETED, 78),
    "COMPLETED": ("Completed", COLOR_COMPLETED, 80),
    "ACCOMPLISHED": ("Accomplished", COLOR_DONE, 88),
    "PRODUCTION": ("Production", COLOR_DONE, 89),
    "LAUNCHED": ("Launched", COLOR_DONE, 90),
    "DONE": ("Done", COLOR_DONE, 95),
}

FINISHED_STATUS_UPPER = {"DONE", "COMPLETED", "ACCOMPLISHED", "APPROVED", "PRODUCTION", "LAUNCHED", "CLOSED", "RESOLVED"}

# Built-in directory of all 24 workspace spaces so employees can select their Space from a dropdown before or after login
DEFAULT_WORKSPACE_SPACES = [
    ("SM360", "SM360"),
    ("AIRI", "AAIRI"),
    ("HRIS", "HRIS"),
    ("IPS", "Inventory and Procurement"),
    ("SDA", "SDA x SM360"),
    ("LIM", "LIMS"),
    ("LMS", "LMS"),
    ("RMS", "RMS"),
    ("CUSP", "CUSP"),
    ("AMS", "AMS"),
    ("PAR", "PartnerPay"),
    ("PUB", "Publication"),
    ("SP", "Student Portal"),
    ("OPH", "Ordinansa"),
    ("OPS", "OPS"),
    ("ACD", "AA Control Dashboard"),
    ("AD", "AA Docs"),
    ("AAD", "AA Directory"),
    ("PD", "PD"),
    ("TEAM", "Team"),
    ("REA", "REA"),
    ("JL2025", "2025"),
    ("DZ2025", "2025 Task"),
    ("GTMS", "Go to market sample"),
]



def get_status_display_and_color(api_status_name: str):
    key = api_status_name.strip().upper()
    if key in STATUS_STYLE_CATALOG:
        lbl, col, order = STATUS_STYLE_CATALOG[key]
        return lbl, col, order
    # Fallback for any custom status
    short = api_status_name.strip()
    if len(short) > 17:
        short = short[:16] + "…"
    if any(w in key for w in ("DONE", "COMPLET", "ACCOMPLISH", "PROD")):
        return short, COLOR_DONE, 92
    if any(w in key for w in ("QA", "REVIEW", "APPROV", "DEPLOY")):
        return short, COLOR_APPROVAL, 68
    if any(w in key for w in ("HOLD", "WAIT", "BLOCK")):
        return short, COLOR_ON_HOLD, 25
    if any(w in key for w in ("RETURN", "FAIL", "REJECT")):
        return short, COLOR_RETURNED, 32
    if any(w in key for w in ("PROG", "DEV", "ACTIVE")):
        return short, COLOR_IN_PROGRESS, 53
    return short, COLOR_BACKLOG, 48


def build_dynamic_kanban_statuses(project_workflow_statuses: list, issue_status_counts: dict) -> list:
    """
    Builds status tuples for the activity ring, preserving every populated status.
    The dashboard groups excess statuses into its ninth tile separately.
    """
    candidates = []
    seen = set()

    # 1. Include all statuses that actually have issues for this user in this space
    for st_name, cnt in issue_status_counts.items():
        if cnt > 0 and st_name not in seen:
            seen.add(st_name)
            candidates.append(st_name)

    # 2. Include the space's official workflow statuses
    for st_name in project_workflow_statuses:
        if st_name not in seen:
            seen.add(st_name)
            candidates.append(st_name)

    # 3. If still empty (or ALL spaces with 0 tasks), fall back to the 9 canonical statuses
    if not candidates:
        return list(KANBAN_STATUSES)

    # Sort by logical Kanban progression order (Backlog -> On Hold -> Returned -> Dev -> QA -> Approval -> Completed -> Done)
    scored = []
    for st_name in candidates:
        lbl, col, order = get_status_display_and_color(st_name)
        has_tasks = 1 if issue_status_counts.get(st_name, 0) > 0 else 0
        scored.append((order, -has_tasks, st_name, lbl, col))

    # If more than 9 statuses exist, keep all statuses with >0 tasks plus the most standard workflow statuses up to 9
    if len(scored) > 9:
        with_tasks = [item for item in scored if item[1] < 0]
        without_tasks = [item for item in scored if item[1] == 0]
        kept = with_tasks + without_tasks[:max(0, 9 - len(with_tasks))]
        kept.sort(key=lambda x: x[0])
    else:
        kept = sorted(scored, key=lambda x: x[0])

    return [(st_name, lbl, col) for _, _, st_name, lbl, col in kept]


# Appearance tokens shared by the raster notch and native task controls.
THEME_COLORS = {
    "Graphite": "#8e8e93", "iOS Blue": "#0a84ff", "iOS Indigo": "#5e5ce6",
    "iOS Purple": "#bf5af2", "iOS Pink": "#ff375f", "iOS Red": "#ff453a",
    "iOS Orange": "#ff9f0a", "iOS Yellow": "#ffd60a", "iOS Green": "#32d74b",
    "iOS Mint": "#63e6e2", "iOS Teal": "#40c8e0", "iOS Cyan": "#64d2ff",
}
THEME_NAME = "Graphite"
THEME_MODE = "dark"
THEME_NEUTRALS = (
    "#09090b", "#111115", "#141418", "#16161b", "#18181e", "#1b1b22",
    "#1e1e24", "#22222a", "#24242e", "#26262e", "#262630", "#30303a",
    "#202028", "#1a1a20", "#24242d", "#2a2a34", "#555560", "#1d1d26", "#1f1f27", "#2c2c38", "#121216", "#141419", "#1c1c22", "#24242d",
)
THEME_TEXT = ("#ffffff", "#f4f4f6", "#e4e4e7", "#dedee4", "#d4d4d8",
              "#a1a1aa", "#8b8b96", "#71717a", "#696973", "#6b6b75", "#52525b", "#c4c4ce", "#9696a2")


def theme_mix(first, second, amount):
    def rgb(value):
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(a + (b - a) * amount):02x}" for a, b in zip(rgb(first), rgb(second)))


def theme_color(color):
    if THEME_NAME == "Graphite" and THEME_MODE == "dark":
        return color
    accent = THEME_COLORS[THEME_NAME]
    light = THEME_MODE == "light"
    if color in THEME_TEXT:
        index = THEME_TEXT.index(color)
        return ("#15151b" if index < 5 else "#454553") if light else ("#f4f4f6" if index < 5 else "#b8b8c5")
    if color == "#0a84ff":
        # Filled actions retain strong contrast with their theme-aware text.
        return theme_mix(accent, "#ffffff", 0.55) if light else theme_mix(accent, "#000000", 0.38)
    if color not in THEME_NEUTRALS:
        return color
    level = int(color[1:3], 16)
    if light:
        return theme_mix("#ffffff", accent, 0.17 if color == "#09090b" else min(0.34, 0.06 + level / 300))
    return theme_mix("#08080e", accent, 0.19 if color == "#09090b" else min(0.42, 0.12 + level / 220))


def theme_gradient(size, name=None, mode=None):
    if (name or THEME_NAME) == "Graphite" and (mode or THEME_MODE) == "dark":
        return Image.new("RGB", size, "#09090b")
    accent = THEME_COLORS[name or THEME_NAME]
    light = (mode or THEME_MODE) == "light"
    start = theme_mix("#ffffff" if light else "#08080e", accent, 0.14 if light else 0.16)
    end = theme_mix("#ffffff" if light else "#08080e", accent, 0.43 if light else 0.48)
    # Draw once per content invalidation; animation frames reuse cached images.
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    for y in range(size[1]):
        draw.line((0, y, size[0], y), fill=theme_mix(start, end, y / max(1, size[1] - 1)))
    return image


def set_theme_palette(name, mode=None):
    global THEME_NAME, THEME_MODE, NOTCH_BG, SURFACE_CARD, SURFACE_ELEVATED, BORDER_HAIRLINE
    global TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED
    THEME_NAME = name if name in THEME_COLORS else "Graphite"
    if mode in ("light", "dark"):
        THEME_MODE = mode
    def rgb(value):
        value = theme_color(value)
        return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
    NOTCH_BG = rgb("#09090b")
    SURFACE_CARD = rgb("#141418")
    SURFACE_ELEVATED = rgb("#1e1e24")
    BORDER_HAIRLINE = rgb("#26262e")
    TEXT_PRIMARY = rgb("#f4f4f6")
    TEXT_SECONDARY = rgb("#a1a1aa")
    TEXT_MUTED = rgb("#696973")


def rgb_to_hex(rgb_tuple) -> str:
    return "#{:02x}{:02x}{:02x}".format(rgb_tuple[0], rgb_tuple[1], rgb_tuple[2])


def apply_windows11_rounded_shadow(toplevel_win: tk.Toplevel):
    """Applies native Windows 11 DWM rounded corners (DWMWCP_ROUND = 2) to a borderless Toplevel."""
    try:
        toplevel_win.update_idletasks()
        hwnd = user32.GetParent(toplevel_win.winfo_id()) or toplevel_win.winfo_id()
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        preference = ctypes.c_int(2)  # DWMWCP_ROUND
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(preference),
            ctypes.sizeof(preference),
        )
    except Exception:
        pass


def stop_ui_motion(widget, channel):
    job = getattr(widget, "_ui_motion_jobs", {}).pop(channel, None)
    if job is not None:
        try:
            widget.after_cancel(job)
        except tk.TclError:
            pass


def animate_ui(widget, channel, duration_ms, update, on_complete=None):
    """Coalesced visual feedback; never sleeps, rebuilds layout, or runs forever."""
    if not hasattr(widget, "_ui_motion_jobs"):
        widget._ui_motion_jobs = {}
        def destroyed(event):
            if event.widget is widget:
                for name in list(widget._ui_motion_jobs):
                    stop_ui_motion(widget, name)
        widget.bind("<Destroy>", destroyed, add="+")
    stop_ui_motion(widget, channel)
    start = time.perf_counter()
    def frame():
        if not widget.winfo_exists():
            return
        u = min(1.0, (time.perf_counter() - start) / max(duration_ms / 1000, 0.001))
        update(1 - (1 - u) ** 3)
        if u < 1:
            widget._ui_motion_jobs[channel] = widget.after(12, frame)
        else:
            widget._ui_motion_jobs.pop(channel, None)
            if on_complete:
                on_complete()
    frame()


def color_rgb(widget, color):
    return tuple(component // 257 for component in widget.winfo_rgb(color))


def blend_color(start, end, progress):
    return "#%02x%02x%02x" % tuple(round(a + (b - a) * progress) for a, b in zip(start, end))


def animate_bubble_window(
    root: tk.Tk,
    win: tk.Toplevel,
    start_rect: tuple,
    end_rect: tuple,
    start_alpha: float = 0.15,
    end_alpha: float = 1.0,
    duration_ms: int = 210,
    on_complete=None,
):
    """
    Slide and fade a panel without resizing its child controls on every frame.
    Set its final layout once, then animate only position and opacity.
    """
    sx, sy, sw, sh = start_rect
    ex, ey, ew, eh = end_rect
    t0 = time.perf_counter()
    dur_s = max(duration_ms / 1000.0, 0.05)
    stop_ui_motion(win, "window-action")
    if end_alpha < start_alpha:
        start_alpha = min(start_alpha, float(win.attributes("-alpha")))

    opening = end_alpha >= start_alpha
    layout_w, layout_h = (ew, eh) if opening else (sw, sh)
    if opening:
        sx = ex + max(-16, min(16, sx - ex))
        sy = ey + max(-20, min(20, sy - ey))
    else:
        ex = sx + max(-16, min(16, ex - sx))
        ey = sy + max(-20, min(20, ey - sy))
    last_position = None

    # Cancel any existing animation on this window
    prev_job = getattr(win, "_bubble_anim_job", None)
    if prev_job is not None:
        try:
            root.after_cancel(prev_job)
        except Exception:
            pass

    def _step():
        nonlocal last_position
        if not win.winfo_exists():
            return
        frame_started = time.perf_counter()
        elapsed = frame_started - t0
        u = min(1.0, elapsed / dur_s)

        # Apple-style spring-out curve (fast initial bubble bloom, gentle settle)
        ease = 1.0 - pow(1.0 - u, 3.4)
        alpha_ease = 1.0 - pow(1.0 - u, 2.2)

        cur_x = int(round(sx + (ex - sx) * ease))
        cur_y = int(round(sy + (ey - sy) * ease))
        cur_a = max(0.0, min(1.0, start_alpha + (end_alpha - start_alpha) * alpha_ease))

        try:
            if (cur_x, cur_y) != last_position:
                win.geometry(f"{layout_w}x{layout_h}+{cur_x}+{cur_y}")
                last_position = (cur_x, cur_y)
            win.attributes("-alpha", cur_a)
        except Exception:
            return

        if u < 1.0:
            delay_ms = max(1, round(1000 / 120 - (time.perf_counter() - frame_started) * 1000))
            win._bubble_anim_job = root.after(delay_ms, _step)
        else:
            win._bubble_anim_job = None
            try:
                win.geometry(f"{layout_w}x{layout_h}+{ex}+{ey}")
                win.attributes("-alpha", end_alpha)
            except Exception:
                pass
            if on_complete:
                on_complete()

    _step()


def get_virtual_screen_bounds():
    vx = user32.GetSystemMetrics(76)
    vy = user32.GetSystemMetrics(77)
    vw = user32.GetSystemMetrics(78)
    vh = user32.GetSystemMetrics(79)
    if vw <= 0 or vh <= 0:
        vw = user32.GetSystemMetrics(0)
        vh = user32.GetSystemMetrics(1)
    return vx, vy, vw, vh


def normalize_base_url(raw_url: str) -> str:
    url = raw_url.strip()
    if not url:
        return ""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    parts = url.split("/")
    if len(parts) >= 3:
        return f"{parts[0]}//{parts[2]}"
    return url.rstrip("/")


def extract_project_from_url(raw_url: str) -> str:
    parts = [p for p in raw_url.strip().split("/") if p]
    for i, part in enumerate(parts):
        if part.lower() == "projects" and i + 1 < len(parts):
            return parts[i + 1].upper()
    return ""


def parse_adf_to_text(node) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node.strip()
    if not isinstance(node, dict):
        return ""

    ntype = node.get("type", "")
    if ntype == "text":
        return node.get("text", "")
    if ntype == "hardBreak":
        return "\n"
    if ntype == "mention":
        return node.get("attrs", {}).get("text", "@user")
    if ntype == "inlineCard":
        return node.get("attrs", {}).get("url", "")

    children = node.get("content", [])
    parts = [parse_adf_to_text(c) for c in children]

    if ntype in ("paragraph", "heading"):
        line = "".join(parts).strip()
        return (line + "\n\n") if line else ""
    if ntype == "listItem":
        item_txt = "".join(parts).strip().replace("\n\n", "\n")
        return f"  • {item_txt}\n"
    if ntype in ("bulletList", "orderedList"):
        return "".join(parts) + "\n"
    if ntype == "codeBlock":
        return "".join(parts).strip() + "\n\n"

    return "".join(parts)


def format_file_size(num_bytes: int) -> str:
    if not num_bytes:
        return "0 KB"
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    return f"{max(1, num_bytes // 1024)} KB"


class JiraAuthExpiredError(Exception):
    """Raised when Jira returns HTTP 401/403 indicating the API key expired or was revoked."""
    pass


def jira_request(base_url, email, token, path, method="GET", body=None, auth_error_codes=(401, 403), timeout=15):
    url = f"{base_url.rstrip('/')}{path}"
    auth_str = f"{email}:{token}"
    b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        if e.code in auth_error_codes:
            raise JiraAuthExpiredError(f"HTTP {e.code}: API token expired or invalid")
        raise


def describe_sync_error(error, session):
    """Capture Jira's reason in the worker, without logging credentials."""
    if error is None:
        return ""
    message = f"{type(error).__name__}: {error}"
    if isinstance(error, urllib.error.HTTPError):
        try:
            body = json.loads(error.read(8192).decode("utf-8"))
            reasons = [str(value) for value in body.get("errorMessages", [])]
            reasons.extend(f"{key}: {value}" for key, value in (body.get("errors") or {}).items())
            if reasons:
                message += " — " + "; ".join(reasons)
        except Exception:
            pass
        finally:
            error.close()
    notes = getattr(error, "__notes__", [])
    if notes:
        message += " [" + "; ".join(str(note) for note in notes) + "]"
    for name in ("token", "email"):
        secret = session.get(name)
        if secret:
            message = message.replace(str(secret), "[redacted]")
    return message[:2000]


def download_jira_bytes(url: str, email: str, token: str) -> bytes:
    auth_str = f"{email}:{token}"
    b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {b64_auth}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


# In-memory cache of project metadata & per-project workflow statuses so we don't re-fetch every 30s
WORKSPACE_PROJECTS_CACHE = {}      # authenticated account scope -> {key: name}
PROJECT_STATUSES_CACHE = {}        # (authenticated account scope, project_key) -> statuses


def jira_account_scope(base_url, email, token=""):
    identity = [base_url.rstrip("/").lower(), email.strip().lower(), token]
    return hashlib.sha256(json.dumps(identity).encode("utf-8")).hexdigest()


def dashboard_view_key(session):
    view = [session.get("project", "AUTO"), session.get("role_mode", "AUTO"), bool(session.get("manual_space_locked"))]
    return hashlib.sha256(json.dumps(view).encode("utf-8")).hexdigest()[:16]


def get_workspace_projects(base_url: str, email: str, token: str, refresh=False, cache_result=True) -> dict:
    scope = jira_account_scope(base_url, email, token)
    if not refresh and WORKSPACE_PROJECTS_CACHE.get(scope):
        return WORKSPACE_PROJECTS_CACHE[scope]
    try:
        projs = jira_request(base_url, email, token, "/rest/api/3/project")
        mapping = {}
        if isinstance(projs, list):
            for p in projs:
                k = p.get("key", "").strip().upper()
                n = p.get("name", "").strip()
                if k:
                    mapping[k] = n or k
        if cache_result:
            WORKSPACE_PROJECTS_CACHE[scope] = mapping
        return mapping
    except Exception:
        raise


def resolve_project_input(user_input: str, proj_map: dict) -> str:
    """Resolves a project key, space name (e.g. 'AAIRI', 'LIMS'), or 'AUTO'/'ALL' to a canonical key."""
    raw = (user_input or "").strip()
    if not raw or raw.upper() in ("AUTO", "AUTOMATIC"):
        return "AUTO"
    if raw.upper() in ("ALL", "ALL SPACES", "ALL MY SPACES", "*"):
        return "ALL"
    up = raw.upper()
    if up in proj_map:
        return up
    # Match by project/space display name (case-insensitive)
    low = raw.lower()
    for k, name in proj_map.items():
        if name.lower() == low:
            return k
    # Partial prefix/substring match on space name (e.g. "Inventory" -> "IPS")
    for k, name in proj_map.items():
        if low in name.lower() or name.lower() in low:
            return k
    return up


def get_project_workflow_statuses(base_url: str, email: str, token: str, project_key: str, refresh=False, cache_result=True) -> list:
    if not project_key or project_key in ("ALL", "AUTO"):
        return [s[0] for s in KANBAN_STATUSES]
    cache_key = (jira_account_scope(base_url, email, token), project_key)
    if not refresh and cache_key in PROJECT_STATUSES_CACHE:
        return PROJECT_STATUSES_CACHE[cache_key]
    try:
        st_data = jira_request(base_url, email, token, f"/rest/api/3/project/{project_key}/statuses")
        statuses = []
        seen = set()
        if isinstance(st_data, list):
            for it in st_data:
                for s in it.get("statuses", []):
                    sname = s.get("name", "")
                    if sname and sname not in seen:
                        seen.add(sname)
                        statuses.append(sname)
        if statuses:
            if cache_result:
                PROJECT_STATUSES_CACHE[cache_key] = statuses
            return statuses
    except Exception:
        raise
    return []


def _run_jql_query(base_url: str, email: str, token: str, jql: str, requested_fields: list, reconcile_issues=None, deadline=None) -> list:
    issues = []
    next_page_token = None
    seen_page_tokens = set()
    while True:
        remaining = deadline - time.monotonic() if deadline is not None else 15
        if remaining <= 0:
            raise TimeoutError("Jira task search exceeded the refresh deadline")
        payload = {
            "jql": jql,
            "maxResults": 100,
            "fields": requested_fields,
        }
        if next_page_token:
            payload["nextPageToken"] = next_page_token
        if reconcile_issues:
            payload["reconcileIssues"] = reconcile_issues
        res = jira_request(base_url, email, token, "/rest/api/3/search/jql", method="POST", body=payload, timeout=min(15, remaining))
        batch = res.get("issues", [])
        issues.extend(batch)
        next_page_token = res.get("nextPageToken")
        if not next_page_token or res.get("isLast", True):
            break
        if next_page_token in seen_page_tokens:
            raise RuntimeError("Jira returned a repeated pagination token; refresh stopped")
        seen_page_tokens.add(next_page_token)
    return issues


def parse_jira_ticket(issue, details_loaded=True):
    fields = issue.get("fields", {})
    status_name = fields.get("status", {}).get("name", "Unknown")

    doc_id = fields.get("customfield_10278") or "—"

    team_obj = fields.get("customfield_10001")
    if isinstance(team_obj, dict):
        team_name = team_obj.get("name") or team_obj.get("title") or "—"
    elif isinstance(team_obj, str):
        team_name = team_obj
    else:
        team_name = "—"

    assignee_obj = fields.get("assignee")
    assignee_name = assignee_obj.get("displayName", "Unassigned") if isinstance(assignee_obj, dict) else "Unassigned"

    iqa_obj = fields.get("customfield_10179")
    iqa_name = iqa_obj.get("displayName", "—") if isinstance(iqa_obj, dict) else "—"

    consult_raw = fields.get("customfield_10311")
    if isinstance(consult_raw, list):
        consult_vals = [
            c.get("value") or c.get("displayName") or str(c)
            for c in consult_raw
            if isinstance(c, dict)
        ]
        consult_to = ", ".join(v for v in consult_vals if v) or "—"
    elif isinstance(consult_raw, dict):
        consult_to = consult_raw.get("value") or consult_raw.get("displayName") or "—"
    else:
        consult_to = str(consult_raw) if consult_raw else "—"

    desc_text = parse_adf_to_text(fields.get("description")).strip() or "No description provided."
    env_text = parse_adf_to_text(fields.get("environment")).strip() or "None"

    raw_atts = fields.get("attachment") or []
    attachments = []
    for att in raw_atts:
        if not isinstance(att, dict):
            continue
        author_name = (att.get("author") or {}).get("displayName", "")
        attachments.append({
            "id": att.get("id", ""),
            "filename": att.get("filename", "attachment"),
            "size": att.get("size", 0),
            "size_str": format_file_size(att.get("size", 0)),
            "mimeType": att.get("mimeType", ""),
            "content_url": att.get("content", ""),
            "thumbnail_url": att.get("thumbnail", ""),
            "author": author_name,
            "created": (att.get("created") or "")[:10],
        })

    ticket_obj = {
        "issue_id": issue.get("id", ""),
        "key": issue.get("key", ""),
        "summary": fields.get("summary", ""),
        "status": status_name,
        "issuetype": (fields.get("issuetype") or {}).get("name", "Task"),
        "priority": (fields.get("priority") or {}).get("name", ""),
        "doc_id": doc_id,
        "team": team_name,
        "assignee": assignee_name,
        "iqa_officer": iqa_name,
        "consult_to": consult_to,
        "description": desc_text,
        "environment": env_text,
        "attachments": attachments,
        "updated": (fields.get("updated") or "")[:10],
    }

    ticket_obj["details_loaded"] = details_loaded
    ticket_obj["updated_revision"] = fields.get("updated") or ""
    if not details_loaded:
        ticket_obj["description"] = ""
        ticket_obj["environment"] = ""
    return ticket_obj


def fetch_jira_ticket_details(session, key):
    fields = "summary,status,issuetype,priority,project,assignee,updated,description,environment,attachment,customfield_10278,customfield_10001,customfield_10311,customfield_10179"
    issue = jira_request(session["base_url"], session["email"], session["token"],
                         f"/rest/api/3/issue/{urllib.parse.quote(key, safe='')}?fields={fields}")
    return parse_jira_ticket(issue, details_loaded=True)


def apply_workflow_metadata(data, statuses):
    if data.get("project") == "ALL" and not statuses:
        statuses = [name for name, _, _ in KANBAN_STATUSES]
    layout = build_dynamic_kanban_statuses(statuses, data.get("counts", {}))
    buckets = data.setdefault("issues_by_status", {})
    buckets.pop(OVERFLOW_STATUS_KEY, None)
    for name, _, _ in layout:
        buckets.setdefault(name, [])
    tiles = list(layout)
    if len(layout) > 9:
        tiles = layout[:8] + [(OVERFLOW_STATUS_KEY, "Other statuses", COLOR_BACKLOG)]
        buckets[OVERFLOW_STATUS_KEY] = [ticket for name, _, _ in layout[8:] for ticket in buckets.get(name, [])]
    data["kanban_statuses"] = layout
    data["kanban_tiles"] = tiles


def fetch_jira_data(session: dict):
    """
    Dynamically fetches tasks for both Developers (assignee) and IQA Officers (IQA Officer cf[10179] / Watcher),
    discovers all Jira Spaces where the user has tasks, auto-selects their active space if needed,
    and builds the dynamic Kanban status grid for their selected space.
    """
    base_url = session["base_url"]
    email = session["email"]
    token = session["token"]
    raw_project = session.get("project", "AUTO")
    role_mode = session.get("role_mode", "AUTO")  # "AUTO", "DEV", "IQA", or "ALL"

    scope = jira_account_scope(base_url, email, token)
    proj_map = dict(session.get("_project_map") or WORKSPACE_PROJECTS_CACHE.get(scope) or {})

    requested_fields = [
        "summary",
        "status",
        "project",
        "updated",
        "customfield_10278",  # Document ID
    ]

    def run_query(jql):
        reconcile = session.get("_reconcile_issue_ids")
        return _run_jql_query(base_url, email, token, jql, requested_fields, reconcile_issues=reconcile, deadline=deadline)

    deadline = time.monotonic() + 45

    def query_iqa():
        try:
            return run_query("(cf[10179] = currentUser() OR watcher = currentUser()) AND (assignee != currentUser() OR assignee is EMPTY) ORDER BY updated DESC")
        except urllib.error.HTTPError as exc:
            if exc.code != 400:
                raise
            return run_query("watcher = currentUser() AND (assignee != currentUser() OR assignee is EMPTY) ORDER BY updated DESC")

    results = queue.Queue()
    def query_role(role, operation):
        try:
            results.put((role, operation(), None))
        except Exception as exc:
            exc.add_note(f"{role.upper()} task search")
            results.put((role, None, exc))

    # Only the two independent role searches run concurrently. Each search
    # still follows Jira's pagination tokens sequentially.
    operations = {"dev": lambda: run_query("assignee = currentUser() ORDER BY updated DESC"), "iqa": query_iqa}
    for role, operation in operations.items():
        threading.Thread(target=query_role, args=(role, operation), daemon=True).start()
    role_results = {}
    for _ in operations:
        try:
            role, issues, error = results.get(timeout=max(0.01, deadline - time.monotonic()))
        except queue.Empty:
            raise TimeoutError("Jira did not finish the task searches within 45 seconds") from None
        if error is not None:
            raise error
        role_results[role] = issues
    dev_issues, iqa_issues = role_results["dev"], role_results["iqa"]

    # 3. Fallback for PMs / Reporters who only create/report tickets (0 Dev and 0 IQA assignments)
    if not dev_issues and not iqa_issues:
        dev_issues = run_query("reporter = currentUser() ORDER BY updated DESC")

    for issue in dev_issues + iqa_issues:
        project = (issue.get("fields") or {}).get("project") or {}
        if project.get("key"):
            proj_map[project["key"].upper()] = project.get("name") or project["key"]
    resolved_proj = resolve_project_input(raw_project, proj_map)

    # Union of all issues (Dev + IQA) so we never miss any Space the employee participates in
    all_user_issues = []
    seen_all_keys = set()
    for iss in dev_issues + iqa_issues:
        k = iss.get("key")
        if k and k not in seen_all_keys:
            seen_all_keys.add(k)
            all_user_issues.append(iss)

    dev_by_space = Counter(
        iss.get("fields", {}).get("project", {}).get("key", "").upper()
        for iss in dev_issues
        if iss.get("fields", {}).get("project", {}).get("key")
    )
    iqa_by_space = Counter(
        iss.get("fields", {}).get("project", {}).get("key", "").upper()
        for iss in iqa_issues
        if iss.get("fields", {}).get("project", {}).get("key")
    )
    all_space_counts = Counter(
        iss.get("fields", {}).get("project", {}).get("key", "").upper()
        for iss in all_user_issues
        if iss.get("fields", {}).get("project", {}).get("key")
    )

    # Smart Space Auto-Selection across all of the user's tasks:
    if resolved_proj == "AUTO":
        if len(all_space_counts) >= 1:
            active_project = all_space_counts.most_common(1)[0][0]
        else:
            active_project = "SM360"
    elif resolved_proj == "ALL":
        active_project = "ALL"
    else:
        if all_space_counts.get(resolved_proj, 0) == 0 and len(all_space_counts) > 0 and not session.get("manual_space_locked", False):
            active_project = all_space_counts.most_common(1)[0][0]
        else:
            active_project = resolved_proj

    # Determine effective role ("DEV", "IQA", or "ALL"):
    # Compare task counts in the active space (and globally) so hybrid IQA officers with 1 Dev ticket and 50 IQA tickets get IQA!
    if role_mode == "DEV":
        effective_role = "DEV" if dev_issues or not iqa_issues else "IQA"
        role_issues = dev_issues if dev_issues else iqa_issues
    elif role_mode == "IQA":
        effective_role = "IQA" if iqa_issues or not dev_issues else "DEV"
        role_issues = iqa_issues if iqa_issues else dev_issues
    elif role_mode == "ALL":
        effective_role = "ALL"
        role_issues = all_user_issues
    else:
        if active_project not in ("ALL", "AUTO"):
            d_cnt = dev_by_space.get(active_project, 0)
            i_cnt = iqa_by_space.get(active_project, 0)
        else:
            d_cnt = len(dev_issues)
            i_cnt = len(iqa_issues)

        if d_cnt == 0 and i_cnt == 0:
            d_cnt = len(dev_issues)
            i_cnt = len(iqa_issues)

        if i_cnt > d_cnt:
            effective_role = "IQA"
            role_issues = iqa_issues
        else:
            effective_role = "DEV"
            role_issues = dev_issues

    # Count tasks per Space for the active role (falling back to all_space_counts so active spaces are always listed in the modal)
    space_counts = Counter()
    for iss in role_issues:
        pk = iss.get("fields", {}).get("project", {}).get("key", "").upper()
        if pk:
            space_counts[pk] += 1
    for pk, cnt in all_space_counts.items():
        if pk not in space_counts:
            space_counts[pk] = cnt

    # Filter issues to the active_project (or keep all if active_project == "ALL")
    if active_project == "ALL":
        filtered_issues = role_issues
        wf_statuses = [s[0] for s in KANBAN_STATUSES]
        project_display = "All Spaces"
    else:
        filtered_issues = [
            iss for iss in role_issues
            if iss.get("fields", {}).get("project", {}).get("key", "").upper() == active_project
        ]
        if not filtered_issues:
            # If the user has tasks in this space under their other role (e.g. IQA vs DEV), show those automatically
            alt_issues = [
                iss for iss in all_user_issues
                if iss.get("fields", {}).get("project", {}).get("key", "").upper() == active_project
            ]
            if alt_issues:
                filtered_issues = alt_issues
                effective_role = "IQA" if iqa_by_space.get(active_project, 0) > dev_by_space.get(active_project, 0) else "DEV"
        wf_statuses = (session.get("_workflow_statuses") or {}).get(active_project) or PROJECT_STATUSES_CACHE.get((scope, active_project), [])
        project_display = proj_map.get(active_project, active_project)

    status_counts = Counter()
    for iss in filtered_issues:
        st_name = iss.get("fields", {}).get("status", {}).get("name", "Unknown")
        status_counts[st_name] += 1

    dynamic_statuses = build_dynamic_kanban_statuses(wf_statuses, status_counts)
    issues_by_status = {api_name: [] for api_name, _, _ in dynamic_statuses}
    active_tickets = []
    finished = 0

    for issue in filtered_issues:
        fields = issue.get("fields", {})
        status_name = (fields.get("status") or {}).get("name", "Unknown")
        ticket_obj = parse_jira_ticket(issue, details_loaded=False)

        issues_by_status.setdefault(status_name, []).append(ticket_obj)

        category_key = ((fields.get("status") or {}).get("statusCategory") or {}).get("key")
        is_finished = (category_key.lower() in ("done", "completed")) if category_key else status_name.strip().upper() in FINISHED_STATUS_UPPER
        if is_finished:
            finished += 1
        else:
            active_tickets.append(ticket_obj)

    total = len(filtered_issues)
    active = total - finished
    pct = int(round((finished / total) * 100)) if total > 0 else 0

    # Keep nine tiles. The ninth opens a normal task list containing every
    # overflow ticket, each retaining its actual status in the detail panel.
    kanban_tiles = list(dynamic_statuses)
    if len(dynamic_statuses) > 9:
        kanban_tiles = dynamic_statuses[:8] + [(OVERFLOW_STATUS_KEY, "Other statuses", COLOR_BACKLOG)]
        issues_by_status[OVERFLOW_STATUS_KEY] = [
            ticket for name, _, _ in dynamic_statuses[8:]
            for ticket in issues_by_status.get(name, [])
        ]

    return {
        "total": total,
        "finished": finished,
        "active": active,
        "pct": pct,
        "counts": dict(status_counts),
        "kanban_statuses": dynamic_statuses,
        "kanban_tiles": kanban_tiles,
        "issues_by_status": issues_by_status,
        "active_tickets": active_tickets[:5],
        "project": active_project,
        "project_display": project_display,
        "effective_role": effective_role,
        "dev_total": len(dev_issues),
        "iqa_total": len(iqa_issues),
        "user_spaces": [(pk, proj_map.get(pk, pk), cnt) for pk, cnt in space_counts.most_common()],
        "all_spaces": sorted([(pk, pname) for pk, pname in proj_map.items()], key=lambda x: x[1].lower()),
        "role_total_all_spaces": len(role_issues),
        "base_url": base_url,
        "updated_at": datetime.now().strftime("%I:%M %p"),
        "fetched_at": time.time(),
        "_view_key": dashboard_view_key(session),
        "from_cache": False,
        "refreshing": False,
        "_project_map": proj_map,
        "_workflow_statuses": dict(session.get("_workflow_statuses") or {}),
        "error": None,
    }


def load_font(size: int, bold: bool = False):
    candidates = (
        ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf"]
        if bold
        else ["segoeui.ttf", "arial.ttf", "calibri.ttf"]
    )
    windir = os.environ.get("WINDIR", r"C:\Windows")
    for name in candidates:
        p = Path(windir) / "Fonts" / name
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default()


def draw_notch_mask(draw: ImageDraw.ImageDraw, cx: float, nw: float, nh: float, ear_r: float, bot_r: float, fill_val: int):
    left = cx - nw / 2
    right = cx + nw / 2
    draw.rounded_rectangle([left, -bot_r, right, nh], radius=bot_r, fill=fill_val)
    draw.rectangle([left - ear_r, 0, right + ear_r, ear_r], fill=fill_val)
    draw.ellipse([left - 2 * ear_r, 0, left, 2 * ear_r], fill=0)
    draw.ellipse([right, 0, right + 2 * ear_r, 2 * ear_r], fill=0)


def monitor_bounds_at(x, y):
    class MonitorInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
    monitor_from_point = user32.MonitorFromPoint
    monitor_from_point.argtypes = (wintypes.POINT, wintypes.DWORD)
    monitor_from_point.restype = wintypes.HANDLE
    get_info = user32.GetMonitorInfoW
    get_info.argtypes = (wintypes.HANDLE, ctypes.POINTER(MonitorInfo))
    get_info.restype = wintypes.BOOL
    info = MonitorInfo()
    info.cbSize = ctypes.sizeof(info)
    handle = monitor_from_point(wintypes.POINT(int(x), int(y)), 2)
    if get_info(handle, ctypes.byref(info)):
        r = info.rcMonitor
        return r.left, r.top, r.right, r.bottom
    vx, vy, vw, vh = get_virtual_screen_bounds()
    return vx, vy, vx + vw, vy + vh


def build_side_shape_mask(t, width, height, side):
    scale = 2
    w = 44 + (732 - 44) * t
    h = 180 + (304 - 180) * t
    x = 0 if side == "left" else width - w
    y = (height - h) / 2
    mask = Image.new("L", (width * scale, height * scale), 0)
    draw = ImageDraw.Draw(mask)
    radius = (16 + 10 * t) * scale
    draw.rounded_rectangle((x * scale, y * scale, (x + w) * scale, (y + h) * scale), radius=radius, fill=255)
    edge = x if side == "left" else x + w - 26
    draw.rectangle((edge * scale, y * scale, (edge + 26) * scale, (y + h) * scale), fill=255)
    return mask.resize((width, height), Image.Resampling.BILINEAR).point([0 if i < 128 else 255 for i in range(256)])


def build_notch_shape_mask(t, width, height, collapsed_w, collapsed_h, expanded_w, expanded_h):
    """Pure Pillow geometry; safe to prepare without touching Tk or account state."""
    scale = 2
    nw = collapsed_w + (expanded_w - collapsed_w) * t
    nh = collapsed_h + (expanded_h - collapsed_h) * t
    mask = Image.new("L", (width * scale, height * scale), 0)
    draw_notch_mask(
        ImageDraw.Draw(mask), width * scale / 2, nw * scale, nh * scale,
        (16 + 10 * t) * scale, (22 + 12 * t) * scale, 255,
    )
    mask = mask.resize((width, height), Image.Resampling.BILINEAR)
    return mask.point([0 if i < 128 else 255 for i in range(256)])


def add_window_controls(parent, close, minimize, zoom):
    canvas = tk.Canvas(parent, width=56, height=28, bg=theme_color("#09090b"), highlightthickness=0, bd=0)
    canvas.pack(side="left", padx=(0, 12))
    centers = (8, 26, 44)
    callbacks = (close, minimize, zoom)
    state = {"hover": False, "pressed": None}
    images = {}
    item = canvas.create_image(0, 0, anchor="nw")

    def paint(pressed=None, amount=3):
        key = (state["hover"], pressed, amount)
        if key not in images:
            scale = 4
            image = Image.new("RGB", (56 * scale, 28 * scale), theme_color("#09090b"))
            draw = ImageDraw.Draw(image)
            for index, (x, color) in enumerate(zip(centers, WINDOW_CONTROL_COLORS)):
                radius = 4.75 + 0.75 * amount / 3 if pressed == index else 5.5
                draw.ellipse(((x - radius) * scale, (14 - radius) * scale,
                              (x + radius) * scale, (14 + radius) * scale), fill=color)
            if state["hover"]:
                for points, color in (
                    ((5.5, 11.5, 10.5, 16.5), "#652321"),
                    ((10.5, 11.5, 5.5, 16.5), "#652321"),
                    ((22.5, 14, 29.5, 14), "#705018"),
                    ((40.5, 14, 47.5, 14), "#145d22"),
                    ((44, 10.5, 44, 17.5), "#145d22"),
                ):
                    draw.line(tuple(value * scale for value in points), fill=color, width=scale)
            images[key] = ImageTk.PhotoImage(image.resize((56, 28), Image.Resampling.LANCZOS), master=canvas)
        canvas.itemconfigure(item, image=images[key])

    def hover(event):
        state["hover"] = True
        paint(state["pressed"], 0 if state["pressed"] is not None else 3)

    def leave(event):
        state["hover"] = False
        paint(state["pressed"], 0 if state["pressed"] is not None else 3)

    def press(event):
        stop_ui_motion(canvas, "traffic-press")
        for index, x in enumerate(centers):
            if abs(event.x - x) <= 8 and 5 <= event.y <= 23:
                state["pressed"] = index
                paint(index, 0)
                return "break"

    def release(event):
        index, state["pressed"] = state["pressed"], None
        if index is None:
            return
        animate_ui(canvas, "traffic-press", 90, lambda progress: paint(index, round(progress * 3)), paint)
        if abs(event.x - centers[index]) <= 8 and 5 <= event.y <= 23:
            callbacks[index]()
        return "break"

    def refresh_theme():
        images.clear()
        canvas.configure(bg=theme_color("#09090b"))
        paint()
    canvas._refresh_theme = refresh_theme
    canvas._traffic_images = images
    paint()
    canvas.bind("<Enter>", hover)
    canvas.bind("<Leave>", leave)
    canvas.bind("<ButtonPress-1>", press)
    canvas.bind("<ButtonRelease-1>", release)
    canvas.configure(cursor="hand2")
    return canvas


def minimize_panel(panel):
    if getattr(panel, "open_dropdown", None) is not None:
        panel.open_dropdown.close(restore_focus=False)
    if panel.win is not None and panel.win.winfo_exists():
        job = getattr(panel.win, "_bubble_anim_job", None)
        if job is not None:
            panel.app.root.after_cancel(job)
            panel.win._bubble_anim_job = None
        window = panel.win
        alpha = float(window.attributes("-alpha"))
        def hide():
            window.withdraw()
            window.attributes("-alpha", 1.0)
        animate_ui(window, "window-action", 120, lambda progress: window.attributes("-alpha", alpha * (1 - progress)), hide)


def toggle_panel_zoom(panel):
    if panel.win is None or not panel.win.winfo_exists():
        return
    if getattr(panel, "open_dropdown", None) is not None:
        panel.open_dropdown.close(restore_focus=False)
    job = getattr(panel.win, "_bubble_anim_job", None)
    if job is not None:
        panel.app.root.after_cancel(job)
        panel.win._bubble_anim_job = None
    panel.win.attributes("-alpha", 1.0)
    original = getattr(panel, "normal_window_rect", None)
    if original is None:
        panel.normal_window_rect = (panel.pos_x, panel.pos_y, panel.W, panel.H)
        vx, vy, vw, vh = get_virtual_screen_bounds()
        panel.W = min(panel.W + 100, max(240, vw - 32))
        panel.H = min(panel.H + 160, max(240, vh - 80))
        panel.pos_x = max(vx + 16, min(panel.pos_x, vx + vw - panel.W - 16))
        panel.pos_y = max(vy + 16, min(panel.pos_y, vy + vh - panel.H - 48))
    else:
        panel.pos_x, panel.pos_y, panel.W, panel.H = original
        panel.normal_window_rect = None
    window = panel.win
    alpha = float(window.attributes("-alpha"))
    target = f"{panel.W}x{panel.H}+{panel.pos_x}+{panel.pos_y}"
    def resize():
        window.geometry(target)
        animate_ui(window, "window-action", 100, lambda progress: window.attributes("-alpha", 0.55 + 0.45 * progress))
    animate_ui(window, "window-action", 65, lambda progress: window.attributes("-alpha", alpha + (0.55 - alpha) * progress), resize)


class SpaceSwitcherModal:
    """
    Custom iOS/macOS-style floating popover modal for selecting a Jira Space / Kanban Board.
    Replaces the native Win32 tk.Menu with a DWM-rounded, bubble-animated dark popover
    featuring an instant search filter, 'All My Spaces', 'My Active Spaces' with pill count badges,
    and 'All Workspace Spaces'.
    """
    W = 310
    H = 380

    def __init__(self, parent_app):
        self.app = parent_app
        self.win = None
        self.scroll_canvas = None
        self.pos_x = 0
        self.pos_y = 0

    def is_open(self) -> bool:
        return self.win is not None and self.win.winfo_exists()

    def toggle_or_open(self, anchor_screen_x: int, anchor_screen_y: int):
        if self.is_open():
            self.close()
            return
        self.show(anchor_screen_x, anchor_screen_y)

    def show(self, anchor_screen_x: int, anchor_screen_y: int):
        if self.is_open():
            self.win.destroy()

        self.win = tk.Toplevel(self.app.root)
        self.win.title("Select Space")
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.0)
        self.win.configure(bg=theme_color("#09090b"))

        self.pos_x = int(anchor_screen_x)
        self.pos_y = int(anchor_screen_y + 6)
        apply_windows11_rounded_shadow(self.win)

        outer = tk.Frame(self.win, bg=theme_color("#09090b"), highlightbackground=theme_color("#262630"), highlightthickness=1, bd=0)
        outer.pack(fill="both", expand=True)

        # Top Header + Close
        top_bar = tk.Frame(outer, bg=theme_color("#09090b"), height=38)
        top_bar.pack(fill="x", padx=12, pady=(8, 2))
        top_bar.pack_propagate(False)

        add_window_controls(top_bar, self.close, self.close, lambda: toggle_panel_zoom(self))

        tk.Label(
            top_bar,
            text="SWITCH KANBAN SPACE",
            bg=theme_color("#09090b"),
            fg=theme_color("#696973"),
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", pady=8)

        # Search Filter Capsule
        search_box = tk.Frame(outer, bg="#141419", highlightbackground=theme_color("#24242e"), highlightthickness=1, padx=10, pady=5)
        search_box.pack(fill="x", padx=12, pady=(0, 8))

        search_var = tk.StringVar(value="")
        search_ent = tk.Entry(
            search_box,
            textvariable=search_var,
            bg="#141419",
            fg=theme_color("#f4f4f6"),
            insertbackground=theme_color("#0a84ff"),
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", 9),
        )
        search_ent.pack(fill="x")

        # Scrollable Spaces List
        list_wrap = tk.Frame(outer, bg=theme_color("#09090b"))
        list_wrap.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        canvas = tk.Canvas(list_wrap, bg=theme_color("#09090b"), highlightthickness=0, bd=0)
        self.scroll_canvas = canvas
        list_frame = tk.Frame(canvas, bg=theme_color("#09090b"))

        list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        c_win = canvas.create_window((0, 0), window=list_frame, anchor="nw", width=self.W - 28)
        canvas.bind("<Configure>", lambda e, cid=c_win: canvas.itemconfigure(cid, width=max(80, e.width - 4)))

        canvas.pack(side="left", fill="both", expand=True)

        def populate_rows(filter_txt: str = ""):
            for child in list_frame.winfo_children():
                child.destroy()

            q = filter_txt.strip().lower()
            cur_proj = (
                (self.app.proj_var.get().strip().upper() or "AUTO")
                if self.app.show_token_update_ui
                else self.app.data.get("project", "SM360")
            )
            total_all = self.app.data.get("role_total_all_spaces", self.app.data.get("total", 0))
            user_spaces = self.app.data.get("user_spaces", [])
            user_space_keys = {pk for pk, _, _ in user_spaces}
            all_spaces = self.app.data.get("all_spaces", []) or list(DEFAULT_WORKSPACE_SPACES)

            # 0. Auto-Detect My Space option (especially helpful for employees who don't know their Space key)
            if not q or "auto" in q or "detect" in q:
                self._add_space_row(
                    list_frame,
                    key="AUTO",
                    title="Auto-Detect My Space",
                    subtitle="Recommended",
                    count=0,
                    is_selected=(cur_proj == "AUTO"),
                    is_highlighted=True,
                )

            # 1. All My Spaces option
            if not q or "all" in q:
                self._add_space_row(
                    list_frame,
                    key="ALL",
                    title="All My Spaces",
                    subtitle="Combined view",
                    count=total_all,
                    is_selected=(cur_proj == "ALL"),
                    is_highlighted=True,
                )

            # 2. Active Spaces (with task counts)
            matching_user_spaces = [
                (pk, pname, cnt)
                for pk, pname, cnt in user_spaces
                if not q or q in pk.lower() or q in pname.lower()
            ]
            if matching_user_spaces:
                tk.Label(
                    list_frame,
                    text="YOUR ACTIVE SPACES",
                    bg=theme_color("#09090b"),
                    fg=theme_color("#52525b"),
                    font=("Segoe UI", 7, "bold"),
                    anchor="w",
                    padx=6,
                ).pack(fill="x", pady=(8, 2))
                for pk, pname, cnt in matching_user_spaces:
                    self._add_space_row(
                        list_frame,
                        key=pk,
                        title=pname,
                        subtitle=pk if pname.upper() != pk.upper() else "",
                        count=cnt,
                        is_selected=(cur_proj == pk),
                        is_highlighted=True,
                    )

            # 3. All Workspace Spaces
            other_spaces = [
                (pk, pname)
                for pk, pname in all_spaces
                if pk not in user_space_keys and (not q or q in pk.lower() or q in pname.lower())
            ]
            if other_spaces:
                tk.Label(
                    list_frame,
                    text="ALL WORKSPACE SPACES",
                    bg=theme_color("#09090b"),
                    fg=theme_color("#52525b"),
                    font=("Segoe UI", 7, "bold"),
                    anchor="w",
                    padx=6,
                ).pack(fill="x", pady=(10, 2))
                for pk, pname in other_spaces:
                    self._add_space_row(
                        list_frame,
                        key=pk,
                        title=pname,
                        subtitle=pk if pname.upper() != pk.upper() else "",
                        count=0,
                        is_selected=(cur_proj == pk),
                        is_highlighted=False,
                    )

            list_frame.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.yview_moveto(0.0)

        search_var.trace_add("write", lambda *_: populate_rows(search_var.get()))
        populate_rows("")

        start_r = (self.pos_x, self.pos_y - 10, 140, 36)
        end_r = (self.pos_x, self.pos_y, self.W, self.H)
        animate_bubble_window(
            self.app.root,
            self.win,
            start_r,
            end_r,
            start_alpha=0.15,
            end_alpha=1.0,
            duration_ms=175,
            on_complete=lambda: search_ent.focus_set() if search_ent.winfo_exists() else None,
        )

    def _add_space_row(self, parent, key: str, title: str, subtitle: str, count: int, is_selected: bool, is_highlighted: bool):
        bg_norm = "#181820" if is_selected else theme_color("#111115")
        border_norm = "#343442" if is_selected else "#1a1a21"

        row = tk.Frame(
            parent,
            bg=bg_norm,
            highlightbackground=border_norm,
            highlightthickness=1,
            padx=10,
            pady=7,
            cursor="hand2",
        )
        row.pack(fill="x", pady=2, padx=3)

        # Status dot on the left
        dot_c = tk.Canvas(row, width=10, height=10, bg=bg_norm, highlightthickness=0)
        dot_c.pack(side="left", padx=(2, 8))
        dot_col = "#32d74b" if is_selected else (theme_color("#0a84ff") if is_highlighted else "#3f3f46")
        dot_c.create_oval(2, 2, 8, 8, fill=dot_col, outline="")

        # Title + optional key badge
        lbl_text = f"{title} ({subtitle})" if subtitle else title
        if len(lbl_text) > 26:
            lbl_text = lbl_text[:25] + "…"
        title_lbl = tk.Label(
            row,
            text=lbl_text,
            bg=bg_norm,
            fg=theme_color("#f4f4f6") if (is_selected or is_highlighted) else theme_color("#a1a1aa"),
            font=("Segoe UI Semibold", 9, "bold" if is_selected else "normal"),
            anchor="w",
        )
        title_lbl.pack(side="left", fill="x", expand=True)

        # Count pill on the right
        cnt_lbl = None
        if count > 0 or is_selected:
            cnt_lbl = tk.Label(
                row,
                text=str(count),
                bg="#22222c" if is_selected else "#191921",
                fg=theme_color("#f4f4f6") if is_selected else theme_color("#a1a1aa"),
                font=("Consolas", 8, "bold"),
                padx=7,
                pady=1,
            )
            cnt_lbl.pack(side="right")

        def on_pick(e=None, k=key):
            self.close()
            self.app.select_or_switch_space(k)

        def on_enter(e):
            row.configure(bg=theme_color("#1d1d26"), highlightbackground="#3e3e4f")
            dot_c.configure(bg=theme_color("#1d1d26"))
            title_lbl.configure(bg=theme_color("#1d1d26"), fg=theme_color("#ffffff"))

        def on_leave(e):
            row.configure(bg=bg_norm, highlightbackground=border_norm)
            dot_c.configure(bg=bg_norm)
            title_lbl.configure(bg=bg_norm, fg=theme_color("#f4f4f6") if (is_selected or is_highlighted) else theme_color("#a1a1aa"))

        for w in [row, dot_c, title_lbl] + ([cnt_lbl] if cnt_lbl else []):
            w.bind("<Button-1>", on_pick)
        row.bind("<Enter>", on_enter)
        row.bind("<Leave>", on_leave)

    def close(self):
        if self.win and self.win.winfo_exists():
            w_ref = self.win
            self.win = None
            self.scroll_canvas = None
            if self.app.show_token_update_ui:
                self.app.invalidate_cache()
                self.app.display_progress(self.app.progress)
            start_r = (self.pos_x, self.pos_y, self.W, self.H)
            end_r = (self.pos_x + 40, self.pos_y - 6, 120, 32)
            animate_bubble_window(
                self.app.root,
                w_ref,
                start_r,
                end_r,
                start_alpha=1.0,
                end_alpha=0.0,
                duration_ms=120,
                on_complete=lambda: w_ref.destroy() if w_ref.winfo_exists() else None,
            )


# Native panel typography uses one UI family and explicit weights. Keep point
# sizes consistent so Windows DPI scaling applies equally to labels and inputs.
PANEL_BODY_FONT = ("Segoe UI", 10, "normal")
PANEL_SMALL_FONT = ("Segoe UI", 9, "normal")
PANEL_LABEL_FONT = ("Segoe UI", 9, "bold")
PANEL_CARD_TITLE_FONT = ("Segoe UI", 10, "normal")
PANEL_TITLE_FONT = ("Segoe UI", 12, "bold")
PANEL_HEADER_FONT = ("Segoe UI", 11, "bold")
PANEL_ID_FONT = ("Consolas", 9, "normal")
PANEL_BADGE_FONT = ("Segoe UI", 9, "normal")


def panel_label(parent, **options):
    options.setdefault("font", PANEL_BODY_FONT)
    options.setdefault("padx", 0)
    options.setdefault("pady", 0)
    return tk.Label(parent, **options)


def clean_ticket_summary(ticket: dict) -> str:
    """Remove only a redundant issue-key prefix, preserving the actual title."""
    summary = ticket.get("summary", "")
    prefix, separator, title = summary.partition("|")
    if separator and prefix.strip() == ticket.get("key", ""):
        return title.strip()
    return summary


class StatusTaskListWidget:
    """
    Minimalist macOS/Linear-inspired floating panel on the desktop.
    Opens with a smooth 120Hz bubble expansion from the clicked card and supports seamless mousewheel scrolling.
    """
    W = 420
    H = 540

    def __init__(self, parent_app):
        self.app = parent_app
        self.win = None
        self.scroll_canvas = None
        self.current_status = None
        self.selected_key = None
        self.row_styles = {}
        self.drag_x = 0
        self.drag_y = 0
        self.pos_x = 76
        self.pos_y = 240

    def show_status(self, status_api_name: str, display_label: str, accent_rgb: tuple, origin_screen_pt=None):
        if self.win is not None and self.win.winfo_exists() and not self.win.winfo_viewable() and self.current_status == status_api_name:
            self.win.geometry(f"{self.W}x{self.H}+{self.pos_x}+{self.pos_y}")
            self.win.deiconify()
            self.win.lift()
            animate_bubble_window(self.app.root, self.win, (self.pos_x, self.pos_y + 6, self.W, self.H), (self.pos_x, self.pos_y, self.W, self.H), start_alpha=0.0, end_alpha=1.0, duration_ms=130)
            return
        self.row_styles = {}
        self.current_status = status_api_name
        tickets = self.app.data.get("issues_by_status", {}).get(status_api_name, [])
        accent_hex = rgb_to_hex(accent_rgb)

        is_new_win = self.win is None or not self.win.winfo_exists()
        if is_new_win:
            self.win = tk.Toplevel(self.app.root)
            self.win.title(f"{display_label}")
            self.win.overrideredirect(True)
            self.win.attributes("-topmost", True)
            self.win.attributes("-alpha", 0.0)
            self.win.configure(bg=theme_color("#09090b"))

            primary_w = max(self.app.root.winfo_screenwidth(), 1)
            notch_cx = self.app.win_x + self.app.WIN_W // 2
            mon_idx = int((notch_cx - self.app.vx) // primary_w)
            mon_left = self.app.vx + mon_idx * primary_w
            self.pos_x = mon_left + 72
            self.pos_y = 230
            if self.app.placement != "top":
                left, top, right, bottom = self.app.dock_bounds
                self.pos_x = left + 24 if self.app.placement == "left" else right - self.W - 24
                self.pos_y = max(top + 24, min(bottom - self.H - 24, self.app.win_y))
            apply_windows11_rounded_shadow(self.win)
        else:
            self.win.deiconify()
            for child in self.win.winfo_children():
                child.destroy()
            self.win.lift()

        outer = tk.Frame(self.win, bg=theme_color("#09090b"), highlightbackground=theme_color("#22222a"), highlightthickness=1, bd=0)
        outer.pack(fill="both", expand=True)

        # Clean Header Bar
        header = tk.Frame(outer, bg=theme_color("#09090b"), height=52)
        header.pack(fill="x", side="top", padx=16, pady=(6, 0))
        header.pack_propagate(False)
        add_window_controls(header, self.close, lambda: minimize_panel(self), lambda: toggle_panel_zoom(self))

        dot_canvas = tk.Canvas(header, width=12, height=12, bg=theme_color("#09090b"), highlightthickness=0)
        dot_canvas.pack(side="left", padx=(2, 8), pady=20)
        dot_canvas.create_oval(2, 2, 10, 10, fill=accent_hex, outline="")

        title_lbl = panel_label(
            header,
            text=display_label,
            bg=theme_color("#09090b"),
            fg=theme_color("#f4f4f6"),
            font=PANEL_HEADER_FONT,
        )
        title_lbl.pack(side="left", pady=12)

        count_badge = panel_label(
            header,
            text=str(len(tickets)),
            bg=theme_color("#09090b"),
            fg=theme_color("#71717a"),
            font=PANEL_SMALL_FONT,
            padx=0,
            pady=1,
        )
        count_badge.pack(side="left", padx=8, pady=15)



        # 1px Hairline Divider
        tk.Frame(outer, bg="#1c1c22", height=1).pack(fill="x", padx=16, pady=(2, 6))

        for w in (header, title_lbl, count_badge):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

        # Scrollable Task List Area
        list_container = tk.Frame(outer, bg=theme_color("#09090b"))
        list_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        canvas = tk.Canvas(list_container, bg=theme_color("#09090b"), highlightthickness=0, bd=0, yscrollincrement=18)
        self.scroll_canvas = canvas
        scroll_frame = tk.Frame(canvas, bg=theme_color("#09090b"))

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=self.W - 36)
        canvas.bind("<Configure>", lambda e, cid=canvas_win_id: canvas.itemconfigure(cid, width=max(100, e.width - 4)))

        canvas.pack(side="left", fill="both", expand=True)

        if not tickets:
            panel_label(
                scroll_frame,
                text=f"No tasks in {display_label}",
                bg=theme_color("#09090b"),
                fg=theme_color("#696973"),
                font=PANEL_SMALL_FONT,
                pady=80,
            ).pack(fill="x")
        else:
            for t in tickets:
                self._create_task_card(scroll_frame, t, accent_hex)

        # Ensure scrollregion is computed immediately after populating cards
        scroll_frame.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.yview_moveto(0.0)

        # Smooth Bubble Open Animation
        end_rect = (self.pos_x, self.pos_y, self.W, self.H)
        if is_new_win:
            if origin_screen_pt:
                ox, oy = origin_screen_pt
                start_rect = (int(ox - 70), int(oy - 20), 140, 44)
            else:
                start_rect = (self.pos_x + self.W // 2 - 70, self.pos_y - 30, 140, 44)
            animate_bubble_window(self.app.root, self.win, start_rect, end_rect, start_alpha=0.12, end_alpha=1.0, duration_ms=220)
        else:
            # Subtle bubble morph pulse when switching status cards while already open
            pulse_start = (self.pos_x + 14, self.pos_y + 12, self.W - 28, self.H - 24)
            animate_bubble_window(self.app.root, self.win, pulse_start, end_rect, start_alpha=0.65, end_alpha=1.0, duration_ms=150)

    def select_ticket(self, key):
        self.selected_key = key
        for paint in self.row_styles.values():
            paint()

    def _create_task_card(self, parent, ticket: dict, accent_hex: str):
        row = tk.Frame(parent, bg=theme_color("#09090b"), cursor="hand2")
        row.pack(fill="x")
        marker = tk.Frame(row, width=2, bg=theme_color("#09090b"))
        marker.pack(side="left", fill="y")
        body = tk.Frame(row, bg=theme_color("#09090b"), padx=12, pady=12)
        body.pack(side="left", fill="both", expand=True)
        meta = tk.Frame(body, bg=theme_color("#09090b"))
        meta.pack(fill="x")
        key_label = panel_label(meta, text=ticket["key"], bg=theme_color("#09090b"), fg=theme_color("#8b8b96"), font=PANEL_ID_FONT)
        key_label.pack(side="left")
        document = ticket.get("doc_id")
        doc_label = None
        if document and document != "—":
            doc_label = panel_label(meta, text=document, bg=theme_color("#09090b"), fg=theme_color("#71717a"), font=PANEL_SMALL_FONT, wraplength=self.W - 210, justify="right")
            doc_label.pack(side="right", padx=(10, 0))
        summary = panel_label(
            body, text=clean_ticket_summary(ticket), bg=theme_color("#09090b"), fg=theme_color("#dedee4"),
            font=PANEL_CARD_TITLE_FONT, wraplength=self.W - 66, justify="left", anchor="w",
        )
        summary.pack(fill="x", pady=(6, 0))
        tk.Frame(parent, height=1, bg="#1c1c22").pack(fill="x", padx=14)
        state = {"hover": False}

        def paint():
            if not row.winfo_exists():
                return
            selected = self.selected_key == ticket["key"]
            background = theme_color("#18181e") if selected else (theme_color("#111115") if state["hover"] else theme_color("#09090b"))
            for widget in (row, body, meta, key_label, summary, doc_label):
                if widget is not None:
                    widget.configure(bg=background)
            marker.configure(bg=accent_hex if selected else background)
            summary.configure(fg=theme_color("#ffffff") if selected else theme_color("#dedee4"))
            key_label.configure(fg=theme_color("#c4c4ce") if selected else theme_color("#8b8b96"))

        def enter(event):
            state["hover"] = True
            paint()

        def leave(event):
            def settle():
                if not row.winfo_exists():
                    return
                px, py = row.winfo_pointerx(), row.winfo_pointery()
                state["hover"] = (row.winfo_rootx() <= px < row.winfo_rootx() + row.winfo_width()
                                  and row.winfo_rooty() <= py < row.winfo_rooty() + row.winfo_height())
                paint()
            self.app.root.after_idle(settle)

        def select(event=None):
            self.select_ticket(ticket["key"])
            origin = (event.x_root, event.y_root) if event else (self.pos_x + self.W // 2, self.pos_y + 120)
            detail_x = self.pos_x + self.W + 14
            if self.app.placement == "right":
                detail_x = self.pos_x - self.app.detail_widget.W - 14
            self.app.detail_widget.show_ticket(ticket, accent_hex, detail_x, self.pos_y, origin_screen_pt=origin)

        self.row_styles[ticket["key"]] = paint
        for widget in (row, marker, body, meta, key_label, summary, doc_label):
            if widget is not None:
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", select)
                widget.bind("<Enter>", enter)
                widget.bind("<Leave>", leave)
        paint()

    def _start_drag(self, event):
        self.drag_x = event.x_root - self.pos_x
        self.drag_y = event.y_root - self.pos_y

    def _on_drag(self, event):
        self.pos_x = event.x_root - self.drag_x
        self.pos_y = event.y_root - self.drag_y
        if self.win and self.win.winfo_exists():
            self.win.geometry(f"+{self.pos_x}+{self.pos_y}")

    def close(self):
        if self.win and self.win.winfo_exists():
            w_ref = self.win
            self.win = None
            self.scroll_canvas = None
            start_r = (self.pos_x, self.pos_y, self.W, self.H)
            end_r = (self.pos_x + self.W // 2 - 60, self.pos_y + 20, 120, 38)
            animate_bubble_window(
                self.app.root,
                w_ref,
                start_r,
                end_r,
                start_alpha=1.0,
                end_alpha=0.0,
                duration_ms=140,
                on_complete=lambda: w_ref.destroy() if w_ref.winfo_exists() else None,
            )


class MotionButton(tk.Button):
    """Subtle color easing and press feedback without changing control geometry."""
    def __init__(self, parent, **options):
        self._motion_ready = False
        super().__init__(parent, **options)
        self._normal_color = self.cget("background")
        self._hover_color = self.cget("activebackground")
        self._hovered = False
        self._focused = False
        self._pressed = False
        self._motion_ready = True
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<FocusIn>", lambda event: self._focus(True))
        self.bind("<FocusOut>", lambda event: self._focus(False))
        self.bind("<KeyPress-space>", self._press)
        self.bind("<KeyRelease-space>", self._keyboard_activate)
        self.bind("<Return>", self._keyboard_activate)

    def configure(self, cnf=None, **options):
        previous = self.cget("background") if self._motion_ready else None
        result = super().configure(cnf, **options)
        if self._motion_ready:
            if "bg" in options or "background" in options:
                self._normal_color = options.get("bg", options.get("background"))
            if "activebackground" in options:
                self._hover_color = options["activebackground"]
            if str(self.cget("state")) == "disabled":
                self._pressed = False
            if previous is not None:
                super().configure(background=previous)
            self._ease(self._target())
        return result

    def _target(self):
        if str(self.cget("state")) == "disabled":
            return self._normal_color
        if self._pressed:
            rgb = color_rgb(self, self._hover_color)
            return blend_color(rgb, (0, 0, 0), 0.2)
        return self._hover_color if self._hovered or self._focused else self._normal_color

    def _ease(self, target):
        start = color_rgb(self, self.cget("background"))
        end = color_rgb(self, target)
        if start == end:
            stop_ui_motion(self, "button-color")
            return
        def paint(progress):
            color = blend_color(start, end, progress)
            tk.Button.configure(self, background=color, activebackground=color)
        animate_ui(self, "button-color", 65 if self._pressed else 110, paint)

    def _enter(self, event):
        self._hovered = True
        self._ease(self._target())
        return "break"

    def _leave(self, event):
        self._hovered = False
        self._ease(self._target())
        return "break"

    def _focus(self, focused):
        self._focused = focused
        self._ease(self._target())

    def _press(self, event):
        if str(self.cget("state")) != "disabled":
            self._pressed = True
            self.focus_set()
            self._ease(self._target())
        return "break"

    def _release(self, event):
        pressed = self._pressed
        self._pressed = False
        inside = 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height()
        self._ease(self._target())
        if pressed and inside and str(self.cget("state")) != "disabled":
            self.invoke()
        return "break"

    def _keyboard_activate(self, event):
        self._pressed = False
        self._ease(self._target())
        if str(self.cget("state")) != "disabled":
            self.invoke()
        return "break"


class DropdownButton(MotionButton):
    """Keyboard-focusable selector without Windows' native menu decoration."""
    def __init__(self, parent, **options):
        self.dropdown = None
        show_chevron = options.pop("show_chevron", True)
        options.pop("indicatoron", None)
        if show_chevron:
            self.chevron_image = tk.PhotoImage(master=parent, width=12, height=8)
            for offset in range(4):
                self.chevron_image.put(theme_color("#a1a1aa"), to=(2 + offset, 2 + offset, 4 + offset, 3 + offset))
                self.chevron_image.put(theme_color("#a1a1aa"), to=(9 - offset, 2 + offset, 11 - offset, 3 + offset))
            options.setdefault("image", self.chevron_image)
            options.setdefault("compound", "right")
        options["command"] = self.open_dropdown
        options.setdefault("highlightthickness", 0)
        options.setdefault("cursor", "hand2")
        super().__init__(parent, **options)
        if show_chevron:
            def refresh_chevron():
                for offset in range(4):
                    self.chevron_image.put(theme_color("#a1a1aa"), to=(2 + offset, 2 + offset, 4 + offset, 3 + offset))
                    self.chevron_image.put(theme_color("#a1a1aa"), to=(9 - offset, 2 + offset, 11 - offset, 3 + offset))
            self._refresh_theme = refresh_chevron
        for key in ("<Down>", "<Alt-Down>"):
            self.bind(key, lambda event: self.open_dropdown() or "break")

    def configure(self, cnf=None, **options):
        if "menu" in options:
            self.dropdown = options.pop("menu")
        return super().configure(cnf, **options)

    def open_dropdown(self):
        if self.dropdown is not None and str(self.cget("state")) != "disabled":
            self.dropdown.tk_popup(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())


class PanelDropdown:
    """Shared dark popover for status, field choices, and person suggestions."""
    def __init__(self, owner, anchor):
        self.owner = owner
        self.anchor = anchor
        self.items = []
        self.win = None
        self.canvas = None
        self.rows = []
        self.active = 0

    def add_command(self, label, command, selected=False, color=None):
        self.items.append(dict(label=label, command=command, selected=selected, color=color))

    def add_checkbutton(self, label, variable, command):
        self.items.append(dict(label=label, command=command, variable=variable))

    def delete(self, first, last=None):
        self.close()
        self.items.clear()

    def is_selected(self, item):
        if "variable" in item:
            return bool(item["variable"].get())
        selected = item.get("selected", False)
        return bool(selected() if callable(selected) else selected)

    def tk_popup(self, x, y):
        if not self.items or not self.anchor.winfo_exists():
            return
        if self.owner.open_dropdown is not None:
            previous = self.owner.open_dropdown
            previous.close()
            if previous is self:
                return
        self.owner.open_dropdown = self
        self.win = tk.Toplevel(self.owner.win)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0)
        self.win.configure(bg=theme_color("#30303a"))
        width = max(240, self.anchor.winfo_width())
        vx, vy, vw, vh = get_virtual_screen_bounds()
        width = min(width, vw - 16)
        outer = tk.Frame(self.win, bg=theme_color("#16161b"), padx=5, pady=5)
        outer.pack(fill="both", expand=True, padx=1, pady=1)
        self.canvas = tk.Canvas(outer, width=width - 12, height=100, bg=theme_color("#16161b"), bd=0, highlightthickness=0, yscrollincrement=18)
        self.canvas.pack(fill="both", expand=True)
        content = tk.Frame(self.canvas, bg=theme_color("#16161b"))
        self.canvas.create_window((0, 0), window=content, anchor="nw", width=width - 12)
        self.rows = []
        for index, item in enumerate(self.items):
            row = tk.Frame(content, bg=theme_color("#16161b"), padx=8, pady=8, cursor="hand2")
            row.pack(fill="x", pady=1)
            dot = None
            if item.get("color"):
                dot = tk.Canvas(row, width=14, height=20, bg=theme_color("#16161b"), bd=0, highlightthickness=0)
                dot.pack(side="left", padx=(0, 7))
                dot.create_oval(3, 7, 9, 13, fill=rgb_to_hex(item["color"]), outline="")
            mark = tk.Canvas(row, width=22, height=20, bg=theme_color("#16161b"), bd=0, highlightthickness=0)
            mark.pack(side="right", padx=(6, 0))
            label = panel_label(row, text=item["label"], bg=theme_color("#16161b"), fg=theme_color("#e4e4e7"), font=PANEL_BODY_FONT,
                                anchor="w", justify="left", wraplength=width - (82 if dot else 60))
            label.pack(side="left", fill="x", expand=True)
            self.rows.append((row, label, dot, mark))
            for widget in (row, label, dot, mark):
                if widget is not None:
                    widget.bind("<Enter>", lambda event, index=index: self.set_active(index))
                    widget.bind("<Button-1>", lambda event, index=index: self.choose(index))
        self.win.update_idletasks()
        height = min(content.winfo_reqheight() + 12, 340, vh - 16)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        x = max(vx + 8, min(self.anchor.winfo_rootx(), vx + vw - width - 8))
        below = self.anchor.winfo_rooty() + self.anchor.winfo_height() + 5
        above = self.anchor.winfo_rooty() - height - 5
        y = above if below + height > vy + vh - 8 and above >= vy + 8 else below
        y = max(vy + 8, min(y, vy + vh - height - 8))
        self.win.geometry(f"{width}x{height}+{x}+{y}")
        apply_windows11_rounded_shadow(self.win)
        self.active = next((i for i, item in enumerate(self.items) if self.is_selected(item)), 0)
        self.paint()
        animate_bubble_window(self.owner.app.root, self.win, (x, y - 5, width, height), (x, y, width, height), start_alpha=0.0, end_alpha=1.0, duration_ms=120)
        self.win.bind("<Escape>", lambda event: self.close() or "break")
        self.win.bind("<Tab>", lambda event: self.close() or "break")
        self.win.bind("<Up>", lambda event: self.move(-1))
        self.win.bind("<Down>", lambda event: self.move(1))
        self.win.bind("<Return>", lambda event: self.choose(self.active))
        self.win.bind("<space>", lambda event: self.choose(self.active))
        self.win.bind("<MouseWheel>", self.scroll)
        self.win.bind("<Button-1>", self.dismiss_outside)
        self.win.bind("<FocusOut>", lambda event: self.owner.app.root.after_idle(self.dismiss_unfocused))
        self.win.grab_set()
        self.win.focus_set()
        self.ensure_visible()

    def paint(self):
        for index, (row, label, dot, mark) in enumerate(self.rows):
            background = "#292932" if index == self.active else theme_color("#16161b")
            for widget in (row, label, dot, mark):
                if widget is not None:
                    widget.configure(bg=background)
            mark.delete("all")
            if self.is_selected(self.items[index]):
                mark.create_line(5, 10, 9, 14, 17, 6, fill=theme_color("#f4f4f6"), width=2)

    def set_active(self, index):
        self.active = index
        self.paint()

    def ensure_visible(self):
        if not self.rows or self.canvas is None:
            return
        self.win.update_idletasks()
        row = self.rows[self.active][0]
        bounds = self.canvas.bbox("all")
        total = max(bounds[3], 1) if bounds else 1
        top = self.canvas.canvasy(0)
        if row.winfo_y() < top:
            self.canvas.yview_moveto(row.winfo_y() / total)
        elif row.winfo_y() + row.winfo_height() > top + self.canvas.winfo_height():
            self.canvas.yview_moveto((row.winfo_y() + row.winfo_height() - self.canvas.winfo_height()) / total)

    def move(self, direction):
        self.active = (self.active + direction) % len(self.items)
        self.paint()
        self.ensure_visible()
        return "break"

    def choose(self, index):
        item = self.items[index]
        if "variable" in item:
            item["variable"].set(not item["variable"].get())
            item["command"]()
            self.paint()
        else:
            self.close()
            item["command"]()
        return "break"

    def scroll(self, event):
        if self.win is not None:
            x, y = self.win.winfo_rootx(), self.win.winfo_rooty()
            if not (x <= event.x_root < x + self.win.winfo_width() and y <= event.y_root < y + self.win.winfo_height()):
                self.close()
                return "break"
        if self.canvas is not None:
            delta = int(-event.delta / 120) or (-1 if event.delta > 0 else 1)
            self.canvas.yview_scroll(delta * 2, "units")
        return "break"

    def dismiss_outside(self, event):
        if self.win is not None:
            x, y = self.win.winfo_rootx(), self.win.winfo_rooty()
            if not (x <= event.x_root < x + self.win.winfo_width() and y <= event.y_root < y + self.win.winfo_height()):
                self.close()
                return "break"

    def dismiss_unfocused(self):
        if self.win is None or not self.win.winfo_exists():
            return
        focused = self.win.focus_get()
        if focused is None or focused.winfo_toplevel() != self.win:
            self.close(restore_focus=False)

    def close(self, restore_focus=True):
        window, self.win = self.win, None
        self.canvas = None
        self.rows = []
        if self.owner.open_dropdown is self:
            self.owner.open_dropdown = None
        if window is not None and window.winfo_exists():
            if window.grab_current() == window:
                window.grab_release()
            window.destroy()
            if restore_focus and self.anchor.winfo_exists():
                self.anchor.focus_set()


class TaskDetailWidget:
    """
    Companion Task Inspector panel with restrained Apple/Linear dark mode design.
    Opens with a smooth 120Hz bubble expansion from the clicked task card.
    """
    W = 510
    H = 540

    def __init__(self, parent_app):
        self.app = parent_app
        self.win = None
        self.scroll_canvas = None
        self.pos_x = 510
        self.pos_y = 230
        self.drag_x = 0
        self.drag_y = 0
        self.preview_images = []
        self.current_ticket = None
        self.status_generation = 0
        self.status_results = queue.Queue()
        self.status_loading = False
        self.status_write_inflight = False
        self.status_options = []
        self.selected_transition = None
        self.transitions_account = None
        self.status_fields = {}
        self.status_saved = False
        self.detail_generation = 0
        self.detail_results = queue.Queue()
        self.detail_cache = {}
        self.detail_loading = False
        self.open_dropdown = None

    def show_ticket(self, ticket: dict, accent_hex: str, default_x: int, default_y: int, origin_screen_pt=None):
        if self.win is not None and self.win.winfo_exists() and not self.win.winfo_viewable() and self.current_ticket and self.current_ticket["key"] == ticket["key"]:
            self.win.geometry(f"{self.W}x{self.H}+{self.pos_x}+{self.pos_y}")
            self.win.deiconify()
            self.win.lift()
            animate_bubble_window(self.app.root, self.win, (self.pos_x, self.pos_y + 6, self.W, self.H), (self.pos_x, self.pos_y, self.W, self.H), start_alpha=0.0, end_alpha=1.0, duration_ms=130)
            return
        if self.open_dropdown is not None:
            self.open_dropdown.close(restore_focus=False)
        self.detail_generation += 1
        self.detail_loading = False
        self.status_saved = False
        self.app.task_list_widget.select_ticket(ticket["key"])
        self.current_ticket = dict(ticket)
        self.status_generation += 1
        self.status_loading = False
        self.status_options = []
        self.selected_transition = None
        self.transitions_account = None
        self.preview_images.clear()
        is_new_win = self.win is None or not self.win.winfo_exists()
        if is_new_win:
            self.win = tk.Toplevel(self.app.root)
            self.win.title(ticket["key"])
            self.win.overrideredirect(True)
            self.win.attributes("-topmost", True)
            self.win.attributes("-alpha", 0.0)
            self.win.configure(bg=theme_color("#09090b"))
            self.pos_x = default_x
            self.pos_y = default_y
            if self.app.placement != "top":
                left, top, right, bottom = self.app.dock_bounds
                self.pos_x = max(left + 16, min(right - self.W - 16, default_x))
                self.pos_y = max(top + 16, min(bottom - self.H - 24, default_y))
            apply_windows11_rounded_shadow(self.win)
        else:
            self.win.deiconify()
            for child in self.win.winfo_children():
                child.destroy()
            self.win.lift()

        outer = tk.Frame(self.win, bg=theme_color("#09090b"), highlightbackground=theme_color("#22222a"), highlightthickness=1, bd=0)
        outer.pack(fill="both", expand=True)

        # Header Bar: Breadcrumb Key + Status Pill + Open in Jira + Close
        header = tk.Frame(outer, bg=theme_color("#09090b"), height=52)
        header.pack(fill="x", side="top", padx=18, pady=(6, 0))
        header.pack_propagate(False)
        add_window_controls(header, self.close, lambda: minimize_panel(self), lambda: toggle_panel_zoom(self))

        identity = tk.Frame(header, bg=theme_color("#09090b"))
        identity.pack(side="left", fill="x", expand=True)
        status_row = tk.Frame(identity, bg=theme_color("#09090b"))

        key_badge = panel_label(
            identity,
            text=ticket["key"],
            bg=theme_color("#09090b"),
            fg=theme_color("#a1a1aa"),
            font=PANEL_ID_FONT,
        )
        key_badge.pack(anchor="w", pady=(1, 2))
        status_row.pack(fill="x")

        dot_c = tk.Canvas(status_row, width=10, height=10, bg=theme_color("#09090b"), highlightthickness=0)
        dot_c.pack(side="left", padx=(0, 5))
        dot_c.create_oval(2, 2, 8, 8, fill=accent_hex, outline="")
        self.status_dot = dot_c

        status_pill = panel_label(
            status_row,
            text=ticket["status"],
            bg=theme_color("#09090b"),
            fg=theme_color("#e4e4e7"),
            font=PANEL_LABEL_FONT,
        )
        status_pill.pack(side="left")
        self.status_badge = status_pill



        base_url = self.app.session.get("base_url") or "https://ascendensasia-team.atlassian.net"
        issue_url = f"{base_url}/browse/{ticket['key']}"
        open_btn = panel_label(
            header,
            text="Open in Jira",
            bg=theme_color("#09090b"),
            fg=theme_color("#8b8b96"),
            font=PANEL_SMALL_FONT,
            padx=4,
            pady=4,
            cursor="hand2",
        )
        open_btn.pack(side="right", padx=8, pady=13)
        open_btn.bind("<Enter>", lambda e: open_btn.configure(fg=theme_color("#f4f4f6")))
        open_btn.bind("<Leave>", lambda e: open_btn.configure(fg=theme_color("#8b8b96")))
        open_btn.bind("<Button-1>", lambda e, u=issue_url: webbrowser.open(u))

        tk.Frame(outer, bg="#1c1c22", height=1).pack(fill="x", padx=18, pady=(2, 6))

        for w in (header, key_badge, status_pill):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

        # Scrollable Content Body
        body_container = tk.Frame(outer, bg=theme_color("#09090b"))
        body_container.pack(fill="both", expand=True, padx=18, pady=(4, 14))

        canvas = tk.Canvas(body_container, bg=theme_color("#09090b"), highlightthickness=0, bd=0, yscrollincrement=18)
        self.scroll_canvas = canvas
        content = tk.Frame(canvas, bg=theme_color("#09090b"))

        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        c_win_id = canvas.create_window((0, 0), window=content, anchor="nw", width=self.W - 48)
        canvas.bind("<Configure>", lambda e, cid=c_win_id: canvas.itemconfigure(cid, width=max(100, e.width - 4)))

        canvas.pack(side="left", fill="both", expand=True)

        # 1. Task Title
        title_lbl = panel_label(
            content,
            text=clean_ticket_summary(ticket),
            bg=theme_color("#09090b"),
            fg=theme_color("#f4f4f6"),
            font=PANEL_TITLE_FONT,
            wraplength=self.W - 60,
            justify="left",
            anchor="w",
        )
        title_lbl.pack(fill="x", pady=(4, 16))
        self.build_status_editor(content)

        self.detail_body = tk.Frame(content, bg=theme_color("#09090b"))
        self.detail_body.pack(fill="x")
        if ticket.get("details_loaded"):
            self.render_detail_sections(self.detail_body, ticket)
        else:
            panel_label(self.detail_body, text="Loading task details…", bg=theme_color("#09090b"), fg=theme_color("#a1a1aa"), font=PANEL_SMALL_FONT, anchor="w").pack(fill="x", pady=(4, 16))

        content.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.yview_moveto(0.0)

        # Smooth Bubble Open Animation
        end_rect = (self.pos_x, self.pos_y, self.W, self.H)
        if is_new_win:
            if origin_screen_pt:
                ox, oy = origin_screen_pt
                start_rect = (int(ox - 60), int(oy - 22), 140, 48)
            else:
                start_rect = (self.pos_x - 40, self.pos_y + 40, 140, 48)
            animate_bubble_window(self.app.root, self.win, start_rect, end_rect, start_alpha=0.12, end_alpha=1.0, duration_ms=220)
        else:
            pulse_start = (self.pos_x + 14, self.pos_y + 12, self.W - 28, self.H - 24)
            animate_bubble_window(self.app.root, self.win, pulse_start, end_rect, start_alpha=0.65, end_alpha=1.0, duration_ms=150)

        self.load_status_options()
        if not ticket.get("details_loaded"):
            self.load_ticket_details()

    def load_ticket_details(self, force=False):
        if not self.current_ticket or self.win is None or not self.app.session.get("connected"):
            return
        self.detail_generation += 1
        generation = self.detail_generation
        account = dict(self.app.session)
        ticket = dict(self.current_ticket)
        key = ticket["key"]
        scope = jira_account_scope(account["base_url"], account["email"], account["token"])
        cache_key = (scope, key)
        cached = self.detail_cache.get(cache_key)
        if not force and cached and time.time() - cached[0] < 60 and cached[1].get("updated_revision") == ticket.get("updated_revision"):
            self.detail_loading = False
            self.show_loaded_details(cached[1])
            return
        self.detail_loading = True
        if not ticket.get("details_loaded"):
            for child in self.detail_body.winfo_children():
                child.destroy()
            panel_label(self.detail_body, text="Loading task details…", bg=theme_color("#09090b"), fg=theme_color("#a1a1aa"), font=PANEL_SMALL_FONT, anchor="w").pack(fill="x", pady=(4, 16))

        def worker():
            result, error = None, None
            try:
                result = fetch_jira_ticket_details(account, key)
            except Exception as exc:
                error = exc
            self.detail_results.put((generation, account, key, result, error))

        threading.Thread(target=worker, daemon=True).start()

    def show_loaded_details(self, ticket):
        # Status transitions have their own authoritative read/refresh flow.
        # A slower detail response must not revert the displayed status.
        status = self.current_ticket["status"]
        self.current_ticket.update(ticket)
        self.current_ticket["status"] = status
        for child in self.detail_body.winfo_children():
            child.destroy()
        self.render_detail_sections(self.detail_body, ticket)

    def drain_detail_results(self):
        while True:
            try:
                generation, account, key, ticket, error = self.detail_results.get_nowait()
            except queue.Empty:
                break
            if not self.account_matches(account) or generation != self.detail_generation:
                continue
            self.detail_loading = False
            if self.win is None or not self.win.winfo_exists() or not self.current_ticket or self.current_ticket["key"] != key:
                continue
            if error is None:
                scope = jira_account_scope(account["base_url"], account["email"], account["token"])
                self.detail_cache[(scope, key)] = (time.time(), ticket)
                while len(self.detail_cache) > 20:
                    self.detail_cache.pop(next(iter(self.detail_cache)))
                self.show_loaded_details(ticket)
            else:
                if not self.current_ticket.get("details_loaded"):
                    for child in self.detail_body.winfo_children():
                        child.destroy()
                panel_label(self.detail_body, text="Task details could not be refreshed.", bg=theme_color("#09090b"), fg="#ff9f0a", font=PANEL_SMALL_FONT, anchor="w").pack(fill="x", pady=(4, 8))
                MotionButton(self.detail_body, text="Retry details", command=lambda: self.load_ticket_details(force=True), bg=theme_color("#24242e"), fg=theme_color("#e4e4e7"), relief="flat", bd=0, padx=12, pady=6, font=PANEL_SMALL_FONT).pack(anchor="w", pady=(0, 16))

    def render_detail_sections(self, content, ticket):
        # 2. Key Details Section
        panel_label(
            content,
            text="Details",
            bg=theme_color("#09090b"),
            fg=theme_color("#a1a1aa"),
            font=PANEL_LABEL_FONT,
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        kd_card = tk.Frame(content, bg=theme_color("#09090b"), bd=0, padx=0, pady=0)
        kd_card.pack(fill="x", pady=(0, 16))

        details_rows = [
            ("Document ID", ticket.get("doc_id", "—")),
            ("Assignee (Dev)", ticket.get("assignee", "—")),
            ("IQA Officer", ticket.get("iqa_officer", "—")),
            ("Team", ticket.get("team", "—")),
            ("Consult To", ticket.get("consult_to", "—")),
            ("Environment", ticket.get("environment", "None")),
        ]
        kd_card.grid_columnconfigure(0, minsize=112)
        kd_card.grid_columnconfigure(1, weight=1)
        for row_index, (label_txt, val_txt) in enumerate(details_rows):
            panel_label(
                kd_card, text=label_txt, bg=theme_color("#09090b"), fg=theme_color("#8b8b96"),
                font=PANEL_SMALL_FONT, anchor="w",
            ).grid(row=row_index, column=0, sticky="nw", pady=5, padx=(0, 14))
            panel_label(
                kd_card, text=val_txt, bg=theme_color("#09090b"),
                fg=theme_color("#e4e4e7") if val_txt not in ("—", "None") else theme_color("#71717a"),
                font=PANEL_ID_FONT if label_txt == "Document ID" else PANEL_BODY_FONT, anchor="w",
                wraplength=self.W - 168, justify="left",
            ).grid(row=row_index, column=1, sticky="ew", pady=5)

        # 3. Description Section
        panel_label(
            content,
            text="Description",
            bg=theme_color("#09090b"),
            fg=theme_color("#a1a1aa"),
            font=PANEL_LABEL_FONT,
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        desc_card = tk.Frame(content, bg=theme_color("#09090b"), bd=0, padx=0, pady=2)
        desc_card.pack(fill="x", pady=(0, 16))

        panel_label(
            desc_card,
            text=ticket.get("description", "No description provided."),
            bg=theme_color("#09090b"),
            fg=theme_color("#d4d4d8"),
            font=PANEL_BODY_FONT,
            wraplength=self.W - 44,
            justify="left",
            anchor="w",
        ).pack(fill="x")

        # 4. Attachments Section
        atts = ticket.get("attachments", [])
        panel_label(
            content,
            text=f"Attachments ({len(atts)})",
            bg=theme_color("#09090b"),
            fg=theme_color("#a1a1aa"),
            font=PANEL_LABEL_FONT,
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        if not atts:
            panel_label(
                content,
                text="No files attached",
                bg=theme_color("#121216"),
                fg=theme_color("#52525b"),
                font=PANEL_SMALL_FONT,
                padx=14,
                pady=10,
                anchor="w",
            ).pack(fill="x", pady=(0, 10))
        else:
            for att in atts:
                self._create_attachment_row(content, att)


    def build_status_editor(self, parent):
        card = tk.Frame(parent, bg=theme_color("#09090b"), bd=0, padx=0, pady=10)
        card.pack(fill="x", pady=(0, 16))
        heading = tk.Frame(card, bg=theme_color("#09090b"))
        heading.pack(fill="x", pady=(0, 8))
        self.status_current = panel_label(
            heading, text="Move to",
            bg=theme_color("#09090b"), fg=theme_color("#8b8b96"), font=PANEL_SMALL_FONT, anchor="w",
        )
        self.status_current.pack(side="left", fill="x", expand=True)
        button_style = dict(
            bg=theme_color("#1f1f27"), fg=theme_color("#e4e4e7"), activebackground=theme_color("#2c2c38"), activeforeground=theme_color("#ffffff"),
            disabledforeground=theme_color("#696973"), relief="flat", bd=0, highlightthickness=0,
            font=PANEL_LABEL_FONT, padx=14, pady=8, cursor="hand2",
        )
        self.status_reload = MotionButton(
            heading, text="Refresh", command=self.load_status_options,
            bg=theme_color("#09090b"), fg=theme_color("#8b8b96"), activebackground=theme_color("#1b1b22"), activeforeground=theme_color("#ffffff"),
            disabledforeground=theme_color("#52525b"), relief="flat", bd=0, highlightthickness=0,
            font=PANEL_SMALL_FONT, padx=4, pady=0, cursor="hand2",
        )
        self.status_reload.pack(side="right", padx=(8, 0))
        controls = tk.Frame(card, bg=theme_color("#09090b"))
        controls.pack(fill="x")
        controls.grid_columnconfigure(0, weight=1)
        self.status_choice = tk.StringVar(value="Loading statuses…")
        select_wrap = tk.Frame(controls, bg=theme_color("#1b1b22"), highlightbackground=theme_color("#30303a"), highlightthickness=1)
        select_wrap.grid(row=0, column=0, sticky="ew")
        self.status_select = DropdownButton(
            select_wrap, textvariable=self.status_choice, bg=theme_color("#1b1b22"), fg=theme_color("#f4f4f6"),
            activebackground=theme_color("#262630"), activeforeground=theme_color("#ffffff"), disabledforeground=theme_color("#696973"),
            font=PANEL_BODY_FONT, relief="flat", bd=0, padx=10, pady=8,
            anchor="w", indicatoron=False, state="disabled", width=18, show_chevron=False,
        )
        self.status_menu = PanelDropdown(self, select_wrap)
        self.status_select.configure(menu=self.status_menu)
        chevron = tk.Canvas(select_wrap, width=26, height=30, bg=theme_color("#1b1b22"), highlightthickness=0, cursor="hand2")
        chevron.pack(side="right", padx=(0, 3))
        chevron.create_line(8, 12, 12, 16, 16, 12, fill=theme_color("#a1a1aa"), width=2)
        chevron.bind("<Button-1>", lambda e: self.status_menu.tk_popup(self.status_select.winfo_rootx(), self.status_select.winfo_rooty() + self.status_select.winfo_height()) if self.status_options and not self.status_loading and not self.status_write_inflight else None)
        self.status_select.pack(side="left", fill="x", expand=True)
        button_style.update(bg=theme_color("#0a84ff"), activebackground=theme_color("#0a84ff"), fg=theme_color("#ffffff"), disabledforeground=theme_color("#a1a1aa"))
        self.status_apply = MotionButton(controls, text="Save", command=self.apply_status_change, state="disabled", **button_style)
        self.status_apply.grid(row=0, column=1, padx=(8, 0))
        self.status_field_host = tk.Frame(card, bg=theme_color("#09090b"))
        self.status_field_host.pack(fill="x")
        self.status_fields = {}
        self.status_note = panel_label(
            card, text="Loading available statuses…",
            bg=theme_color("#09090b"), fg=theme_color("#a1a1aa"), font=PANEL_SMALL_FONT,
            anchor="w", justify="left", wraplength=self.W - 90,
        )
        self.set_status_note("")
        tk.Frame(parent, height=1, bg="#1c1c22").pack(fill="x", pady=(0, 18))
        self.update_status_controls()

    def set_status_note(self, text, fg=theme_color("#8b8b96")):
        self.status_note.configure(text=text, fg=fg)
        if text:
            self.status_note.pack(fill="x", pady=(8, 0))
        else:
            self.status_note.pack_forget()

    def account_matches(self, account):
        return bool(account) and self.app.session.get("connected", False) and all(
            self.app.session.get(key) == account.get(key) for key in ("base_url", "email", "token")
        )

    def update_status_controls(self):
        if self.win is None or not self.win.winfo_exists():
            return
        busy = self.status_loading or self.status_write_inflight
        connected = self.app.session.get("connected", False)
        self.status_reload.configure(state="disabled" if busy or not connected else "normal")
        self.status_select.configure(state="normal" if self.status_options and not busy else "disabled")
        can_save = bool(self.selected_transition) and not busy and connected
        self.status_apply.configure(state="normal" if can_save else "disabled", bg=theme_color("#0a84ff") if can_save else theme_color("#24242e"), text="Saving…" if self.status_write_inflight else "Save")
        for model in self.status_fields.values():
            for widget in model["widgets"]:
                widget.configure(state="disabled" if busy else "normal")

    def clear_status_options(self):
        if self.open_dropdown is not None:
            self.open_dropdown.close()
        self.status_options = []
        self.selected_transition = None
        self.transitions_account = None
        self.status_choice.set("Select status")
        self.status_menu.delete(0, "end")
        self.status_apply.configure(text="Save")
        self.status_fields = {}
        for child in self.status_field_host.winfo_children():
            child.destroy()

    @staticmethod
    def required_transition_fields(transition):
        return [meta.get("name", name) for name, meta in (transition.get("fields") or {}).items()
                if meta.get("required") and not meta.get("hasDefaultValue")]

    def select_status_option(self, transition):
        self.status_generation += 1
        self.status_loading = False
        self.status_saved = False
        self.selected_transition = transition
        destination = (transition.get("to") or {}).get("name", transition.get("name", "Status"))
        self.status_choice.set(destination)
        self.render_transition_fields(transition)
        self.status_apply.configure(text="Save")
        self.set_status_note(text="Complete the required fields." if self.status_fields else "", fg=theme_color("#a1a1aa"))
        self.update_status_controls()

    @staticmethod
    def transition_option_value(option, schema):
        if not isinstance(option, dict):
            return option
        if option.get("accountId"):
            return {"accountId": option["accountId"]}
        if option.get("id") is not None:
            value = {"id": str(option["id"])}
            if isinstance(option.get("child"), dict):
                value["child"] = TaskDetailWidget.transition_option_value(option["child"], schema)
            return value
        if schema.get("type") == "string" or schema.get("items") == "string":
            return option.get("value", option.get("name", ""))
        return {"value": option["value"]} if "value" in option else option

    @staticmethod
    def text_to_adf(text):
        return {"type": "doc", "version": 1, "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": line}] if line else []}
            for line in text.splitlines()
        ]}

    def render_transition_fields(self, transition, extra_fields=None):
        if extra_fields is None:
            for child in self.status_field_host.winfo_children():
                child.destroy()
            self.status_fields = {}
        metadata = transition.get("fields") or {}
        extra_fields = set(extra_fields or ())
        for key, meta in metadata.items():
            if key in self.status_fields or not (meta.get("required") or key in extra_fields):
                continue
            schema = meta.get("schema") or {}
            field_type = schema.get("type", "string")
            options = meta.get("allowedValues") or []
            default = meta.get("defaultValue")
            row = tk.Frame(self.status_field_host, bg=theme_color("#09090b"))
            row.pack(fill="x", pady=(12, 0))
            required = bool(meta.get("required") or key in extra_fields)
            panel_label(row, text=meta.get("name", key) + (" *" if required else ""), bg=theme_color("#09090b"), fg=theme_color("#d4d4d8"), font=PANEL_SMALL_FONT, anchor="w").pack(fill="x", pady=(0, 5))
            model = {"meta": meta, "schema": schema, "required": required, "widgets": []}
            self.status_fields[key] = model
            entry_style = dict(bg=theme_color("#1b1b22"), fg=theme_color("#f4f4f6"), insertbackground=theme_color("#f4f4f6"), relief="flat", bd=0, highlightthickness=1, highlightbackground=theme_color("#30303a"), highlightcolor=theme_color("#0a84ff"), font=PANEL_BODY_FONT)
            if options:
                choice = tk.StringVar(value="Choose " + meta.get("name", "value").lower())
                picker = DropdownButton(row, textvariable=choice, bg=theme_color("#1b1b22"), fg=theme_color("#f4f4f6"), activebackground=theme_color("#262630"), activeforeground=theme_color("#ffffff"), relief="flat", bd=0, padx=10, pady=7, anchor="w", font=PANEL_BODY_FONT)
                picker.pack(fill="x")
                menu = PanelDropdown(self, picker)
                picker.configure(menu=menu)
                model.update(value=[] if field_type == "array" else None, widgets=[picker])
                def choose(value, label, model=model, choice=choice):
                    model["value"] = value
                    choice.set(label)
                selected_checks = []
                for option in options:
                    label = str(option.get("value") or option.get("name") or option.get("displayName") or option.get("id", "Value")) if isinstance(option, dict) else str(option)
                    value = self.transition_option_value(option, schema)
                    if field_type == "array":
                        checked = tk.BooleanVar(value=value in [self.transition_option_value(v, schema) for v in (default or [])])
                        selected_checks.append((checked, value, label))
                        def update_many(model=model, choice=choice, checks=selected_checks):
                            model["value"] = [value for checked, value, _ in checks if checked.get()]
                            choice.set(", ".join(label for checked, _, label in checks if checked.get()) or "Choose values")
                        menu.add_checkbutton(label=label, variable=checked, command=update_many)
                    else:
                        menu.add_command(label=label, command=lambda value=value, label=label, choose=choose: choose(value, label))
                        if default is not None and value == self.transition_option_value(default, schema):
                            choose(value, label)
                        if isinstance(option, dict) and option.get("id") is not None:
                            for child in option.get("children", []):
                                if child.get("id") is None:
                                    continue
                                child_label = label + " / " + str(child.get("value") or child.get("name") or child["id"])
                                child_value = {"id": str(option["id"]), "child": {"id": str(child["id"])}}
                                menu.add_command(label=child_label, command=lambda value=child_value, label=child_label, choose=choose: choose(value, label))
                                if default is not None and child_value == self.transition_option_value(default, schema):
                                    choose(child_value, child_label)
                if field_type == "array":
                    update_many()
                model["get"] = lambda model=model: model["value"]
            elif field_type == "user" or (field_type == "array" and schema.get("items") == "user"):
                search = tk.Frame(row, bg=theme_color("#09090b"))
                search.pack(fill="x")
                query = tk.Entry(search, **entry_style)
                query.pack(side="left", fill="x", expand=True, ipady=6)
                button = MotionButton(search, text="Find", command=lambda key=key: self.find_transition_user(key), bg=theme_color("#24242e"), fg=theme_color("#e4e4e7"), relief="flat", bd=0, padx=12, pady=7, font=PANEL_SMALL_FONT)
                button.pack(side="right", padx=(8, 0))
                people = default if isinstance(default, list) else ([default] if isinstance(default, dict) else [])
                people = [person for person in people if person.get("accountId")]
                picked = tk.StringVar(value=", ".join(person.get("displayName", person["accountId"]) for person in people) or "Find a person by name or email")
                panel_label(row, textvariable=picked, bg=theme_color("#09090b"), fg=theme_color("#a1a1aa"), font=PANEL_SMALL_FONT, anchor="w", wraplength=self.W - 100, justify="left").pack(fill="x", pady=(4, 0))
                model.update(people=people, query=query, picked=picked, anchor=button, widgets=[query, button])
                model["get"] = lambda model=model, many=field_type == "array": ([{"accountId": p["accountId"]} for p in model["people"]] if many else ({"accountId": model["people"][0]["accountId"]} if model["people"] else None))
            elif field_type == "boolean":
                value = tk.BooleanVar(value=bool(default))
                control = tk.Checkbutton(row, text=meta.get("name", key), variable=value, bg=theme_color("#09090b"), fg=theme_color("#e4e4e7"), selectcolor=theme_color("#24242e"), activebackground=theme_color("#09090b"), activeforeground=theme_color("#ffffff"), font=PANEL_BODY_FONT)
                control.pack(anchor="w")
                model.update(get=value.get, widgets=[control])
            else:
                custom = schema.get("custom", "")
                if custom.endswith(":datepicker"):
                    field_type = "date"
                elif custom.endswith(":datetime"):
                    field_type = "datetime"
                rich_text = key in ("description", "environment", "comment") or custom.endswith(":textarea")
                structured = field_type not in ("string", "number", "integer", "date", "datetime", "array") or (field_type == "array" and schema.get("items") not in ("string", "number", "integer"))
                if rich_text or structured:
                    control = tk.Text(row, height=3, wrap="word", **entry_style)
                    control.pack(fill="x")
                    initial = parse_adf_to_text(default).strip() if rich_text else (json.dumps(default) if default is not None else "")
                    control.insert("1.0", initial)
                    raw_value = lambda control=control: control.get("1.0", "end-1c").strip()
                else:
                    control = tk.Entry(row, **entry_style)
                    control.pack(fill="x", ipady=6)
                    initial = ", ".join(str(v) for v in default) if isinstance(default, list) else (str(default) if default is not None else "")
                    control.insert(0, initial)
                    raw_value = lambda control=control: control.get().strip()
                hint = "YYYY-MM-DD" if field_type == "date" else ("YYYY-MM-DDTHH:MM:SS.000+0000" if field_type == "datetime" else ("Structured value (JSON)" if structured else ("Separate multiple values with commas" if field_type == "array" else "")))
                if hint:
                    panel_label(row, text=hint, bg=theme_color("#09090b"), fg=theme_color("#a1a1aa"), font=PANEL_BADGE_FONT, anchor="w").pack(fill="x", pady=(4, 0))
                def read_value(raw_value=raw_value, field_type=field_type, rich_text=rich_text, structured=structured, schema=schema):
                    raw = raw_value()
                    if not raw:
                        return None
                    if rich_text:
                        return self.text_to_adf(raw)
                    if structured:
                        return json.loads(raw)
                    if field_type in ("number", "integer"):
                        number = float(raw)
                        if not math.isfinite(number) or (field_type == "integer" and not number.is_integer()):
                            raise ValueError("Enter a valid number")
                        return int(number) if field_type == "integer" else number
                    if field_type == "date":
                        datetime.strptime(raw, "%Y-%m-%d")
                    if field_type == "datetime":
                        datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S.%f%z")
                    if field_type == "array":
                        values = [v.strip() for v in raw.split(",") if v.strip()]
                        if schema.get("items") in ("number", "integer"):
                            numbers = [float(v) for v in values]
                            if not all(math.isfinite(number) for number in numbers):
                                raise ValueError("Enter valid numbers")
                            if schema.get("items") == "integer":
                                if not all(number.is_integer() for number in numbers):
                                    raise ValueError("Enter whole numbers")
                                return [int(number) for number in numbers]
                            return numbers
                        return values
                    return raw
                model.update(get=read_value, widgets=[control])

    def collect_transition_fields(self):
        fields = {}
        for key, model in self.status_fields.items():
            label = model["meta"].get("name", key)
            try:
                value = model["get"]()
            except (ValueError, TypeError):
                raise ValueError(f"Check the value for {label}.") from None
            empty = value is None or value == "" or value == [] or value == {}
            if empty and model["required"]:
                raise ValueError(f"Please fill in {label}.")
            if not empty:
                fields[key] = value
        return fields

    def find_transition_user(self, field_key):
        if self.status_loading or self.status_write_inflight or not self.account_matches(self.transitions_account):
            return
        model = self.status_fields.get(field_key)
        if not model:
            return
        query = model["query"].get().strip()
        if not query:
            self.set_status_note(text="Enter a person’s name or email, then click Find.", fg="#ff9f0a")
            return
        generation = self.status_generation
        account = dict(self.app.session)
        key = self.current_ticket["key"]
        params = {"query": query, "maxResults": 20}
        endpoint = "/rest/api/3/user/search"
        if field_key == "assignee":
            endpoint = "/rest/api/3/user/assignable/search"
            params["issueKey"] = key
        path = endpoint + "?" + urllib.parse.urlencode(params)
        self.status_loading = True
        self.set_status_note(text="Finding people in Jira…", fg=theme_color("#a1a1aa"))
        self.update_status_controls()

        def worker():
            result, error = None, None
            try:
                users = jira_request(account["base_url"], account["email"], account["token"], path, auth_error_codes=(401,))
                result = {"field": field_key, "users": users}
            except Exception as exc:
                error = exc
            self.status_results.put((generation, account, key, "people", result, error, False))

        threading.Thread(target=worker, daemon=True).start()

    def show_transition_people(self, result):
        model = self.status_fields.get(result["field"])
        if not model:
            return
        people = [person for person in result["users"] if person.get("accountId") and person.get("active", True)]
        if not people:
            self.set_status_note(text="No matching people were returned. Try another name or email.", fg="#ff9f0a")
            return
        menu = PanelDropdown(self, model["query"].master)
        def choose(person):
            if model["schema"].get("type") == "array":
                existing = model["people"]
                model["people"] = [p for p in existing if p["accountId"] != person["accountId"]] if any(p["accountId"] == person["accountId"] for p in existing) else existing + [person]
            else:
                model["people"] = [person]
            model["picked"].set(", ".join(p.get("displayName", p["accountId"]) for p in model["people"]) or "No person selected")
            self.set_status_note(text="Person selected. Save status when ready.", fg=theme_color("#a1a1aa"))
        for person in people:
            label = person.get("displayName", person["accountId"])
            email = person.get("emailAddress")
            if email:
                label += " · " + email
            menu.add_command(label=label, command=lambda person=person: choose(person), selected=lambda person=person: any(p["accountId"] == person["accountId"] for p in model["people"]))
        self.status_user_menu = menu
        anchor = model["anchor"]
        menu.tk_popup(anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height())

    def load_status_options(self):
        if self.status_loading or self.status_write_inflight or not self.current_ticket or not self.app.session.get("connected"):
            return
        self.status_generation += 1
        generation = self.status_generation
        account = dict(self.app.session)
        key = self.current_ticket["key"]
        self.clear_status_options()
        self.status_loading = True
        self.status_choice.set("Loading statuses…")
        self.set_status_note(text="Saved to Jira." if self.status_saved else "", fg=theme_color("#a1a1aa"))
        self.update_status_controls()

        def worker():
            result, error = None, None
            try:
                result = jira_request(
                    account["base_url"], account["email"], account["token"],
                    f"/rest/api/3/issue/{urllib.parse.quote(key, safe='')}/transitions?expand=transitions.fields",
                    auth_error_codes=(401,),
                )
            except Exception as exc:
                error = exc
            self.status_results.put((generation, account, key, "load", result, error, False))

        threading.Thread(target=worker, daemon=True).start()

    def apply_status_change(self):
        transition = self.selected_transition
        if not transition or self.status_loading or self.status_write_inflight or not self.current_ticket:
            return
        if not self.account_matches(self.transitions_account):
            self.clear_status_options()
            self.set_status_note(text="Reload available statuses for the current account.", fg="#ff9f0a")
            self.update_status_controls()
            return
        key = self.current_ticket["key"]
        account = dict(self.app.session)
        try:
            fields = self.collect_transition_fields()
        except ValueError as exc:
            self.set_status_note(text=str(exc), fg="#ff9f0a")
            return
        body = {"transition": {"id": str(transition["id"])}}
        comment = fields.pop("comment", None)
        if fields:
            body["fields"] = fields
        if comment is not None:
            body["update"] = {"comment": [{"add": {"body": comment}}]}
        self.status_generation += 1
        generation = self.status_generation
        cancel_event = self.app.status_write_cancel
        issue_id = self.current_ticket.get("issue_id", "")
        self.status_write_inflight = True
        self.set_status_note(text="Saving status to Jira…", fg=theme_color("#a1a1aa"))
        self.update_status_controls()

        def worker():
            result = {"issue_id": issue_id, "issue": None}
            error, accepted = None, False
            path = f"/rest/api/3/issue/{urllib.parse.quote(key, safe='')}"
            try:
                if cancel_event.is_set():
                    raise RuntimeError("Status update canceled")
                jira_request(
                    account["base_url"], account["email"], account["token"], path + "/transitions",
                    method="POST", body=body, auth_error_codes=(401,),
                )
                accepted = True
                # Failure to read back must not turn an accepted write into a
                # retryable failure: the board refresh will fetch it again.
                try:
                    result["issue"] = jira_request(
                        account["base_url"], account["email"], account["token"], path + "?fields=status",
                        auth_error_codes=(401,),
                    )
                except Exception:
                    pass
            except Exception as exc:
                error = exc
                if isinstance(exc, urllib.error.HTTPError):
                    try:
                        result["validation"] = json.loads(exc.read().decode("utf-8"))
                    except (ValueError, UnicodeError, OSError):
                        pass
            self.status_results.put((generation, account, key, "write", result, error, accepted))

        threading.Thread(target=worker, daemon=True).start()

    def update_displayed_status(self, status):
        name = status.get("name")
        if not name:
            return
        self.current_ticket["status"] = name
        self.status_badge.configure(text=name)
        _, color, _ = get_status_display_and_color(name)
        self.status_dot.itemconfigure("all", fill=rgb_to_hex(color))

    def refresh_status_from_data(self, data):
        if self.win is None or not self.win.winfo_exists() or not self.current_ticket:
            return
        key = self.current_ticket["key"]
        for tickets in data.get("issues_by_status", {}).values():
            for ticket in tickets:
                if ticket["key"] == key:
                    if ticket["status"] != self.current_ticket["status"]:
                        self.status_generation += 1
                        self.status_loading = False
                        self.update_displayed_status({"name": ticket["status"]})
                        self.clear_status_options()
                        self.set_status_note(text="Status refreshed from Jira.", fg=theme_color("#a1a1aa"))
                        self.update_status_controls()
                        self.load_status_options()
                    if ticket.get("updated_revision") != self.current_ticket.get("updated_revision") and not self.detail_loading and not self.status_write_inflight:
                        self.load_ticket_details(force=True)
                    return

    def drain_status_results(self):
        while True:
            try:
                generation, account, key, kind, result, error, accepted = self.status_results.get_nowait()
            except queue.Empty:
                break
            if kind == "write":
                self.status_write_inflight = False
            matches_account = self.account_matches(account)
            if kind == "write" and matches_account:
                # Even a timeout can occur after a write has reached Jira.
                # Refresh authoritative state; never automatically repeat POST.
                issue_id = (result.get("issue") or {}).get("id") or result.get("issue_id")
                if accepted:
                    self.app.invalidate_dashboard_snapshots()
                self.app.refresh_after_status_change(issue_id)
            visible = self.win is not None and self.win.winfo_exists()
            if not visible or generation != self.status_generation or not matches_account or not self.current_ticket or self.current_ticket["key"] != key:
                if visible:
                    self.update_status_controls()
                    if kind == "write" and not self.status_loading and not self.status_options:
                        self.load_status_options()
                continue
            self.status_loading = False
            if kind == "people":
                self.update_status_controls()
                if error is None and self.win.winfo_viewable():
                    self.show_transition_people(result)
                elif error is None:
                    self.set_status_note(text="Click Find again to view matching people.", fg=theme_color("#a1a1aa"))
                else:
                    self.set_status_note(text="People could not be loaded. Check your connection or search permission and try again.", fg="#ff9f0a")
                continue
            if kind == "load" and error is None:
                self.status_options = [item for item in result.get("transitions", []) if item.get("id")]
                self.transitions_account = account
                for transition in sorted(self.status_options, key=lambda item: get_status_display_and_color((item.get("to") or {}).get("name", item.get("name", "")))[2]):
                    destination = (transition.get("to") or {}).get("name", transition.get("name", "Status"))
                    action = transition.get("name", destination)
                    label = destination if action == destination else f"{destination} ({action})"
                    _, color, _ = get_status_display_and_color(destination)
                    self.status_menu.add_command(label=label, command=lambda item=transition: self.select_status_option(item),
                        selected=lambda item=transition: bool(self.selected_transition and self.selected_transition["id"] == item["id"]), color=color)
                self.status_choice.set("Select status" if self.status_options else "No available changes")
                self.set_status_note(text=("Saved to Jira." if self.status_saved else "") if self.status_options else "No available status changes.", fg="#32d74b" if self.status_saved else theme_color("#9696a2"))
            elif kind == "write" and accepted:
                status = (((result.get("issue") or {}).get("fields") or {}).get("status") or {})
                self.update_displayed_status(status)
                self.clear_status_options()
                self.status_saved = True
                self.set_status_note(text="Saved to Jira. Refreshing board counts…", fg="#32d74b")
                self.detail_cache.clear()
                self.load_ticket_details(force=True)
                self.load_status_options()
            else:
                validation = (result or {}).get("validation") or {}
                field_errors = validation.get("errors") or {}
                if kind == "write" and isinstance(error, urllib.error.HTTPError) and error.code in (400, 422) and self.selected_transition:
                    self.render_transition_fields(self.selected_transition, extra_fields=tuple(field_errors))
                    messages = list(validation.get("errorMessages") or []) + [str(message) for message in field_errors.values()]
                    self.set_status_note(text=" ".join(messages)[:700] or "Jira needs more information. Check the fields and save again.", fg="#ff9f0a")
                    self.update_status_controls()
                    continue
                self.clear_status_options()
                if isinstance(error, JiraAuthExpiredError):
                    message = "Your API key is no longer valid. Update it in account settings."
                elif isinstance(error, urllib.error.HTTPError) and error.code == 403:
                    message = "Your Jira account does not have permission for this change."
                elif kind == "write":
                    message = "The change could not be confirmed. Refreshing the board; reload statuses before trying again."
                else:
                    message = "Could not load statuses. Click Refresh to try again."
                self.set_status_note(text=message, fg="#ff9f0a")
            self.update_status_controls()

    def _create_attachment_row(self, parent, att: dict):
        att_card = tk.Frame(
            parent,
            bg=theme_color("#121216"),
            highlightbackground="#1e1e26",
            highlightthickness=1,
            padx=14,
            pady=10,
        )
        att_card.pack(fill="x", pady=4)

        top = tk.Frame(att_card, bg=theme_color("#121216"))
        top.pack(fill="x")

        fname_lbl = panel_label(
            top,
            text=att["filename"],
            bg=theme_color("#121216"),
            fg=theme_color("#f4f4f6"),
            font=PANEL_CARD_TITLE_FONT,
            anchor="w",
            wraplength=315,
            justify="left",
        )
        fname_lbl.pack(side="left", fill="x", expand=True)

        open_att_btn = panel_label(
            top,
            text="Open ↗",
            bg=theme_color("#1f1f27"),
            fg=theme_color("#e4e4e7"),
            font=PANEL_LABEL_FONT,
            padx=10,
            pady=4,
            cursor="hand2",
        )
        open_att_btn.pack(side="right", padx=(8, 0))
        open_att_btn.bind("<Enter>", lambda e: open_att_btn.configure(bg=theme_color("#2c2c38"), fg=theme_color("#ffffff")))
        open_att_btn.bind("<Leave>", lambda e: open_att_btn.configure(bg=theme_color("#1f1f27"), fg=theme_color("#e4e4e7")))

        meta_txt = f"{att['size_str']}   ·   {att['created']}   ·   {att['author']}"
        panel_label(
            att_card,
            text=meta_txt,
            bg=theme_color("#121216"),
            fg=theme_color("#a1a1aa"),
            font=PANEL_SMALL_FONT,
            wraplength=self.W - 80,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        mime = (att.get("mimeType") or "").lower()
        if mime.startswith("image/") and att.get("content_url"):
            preview_holder = panel_label(att_card, bg=theme_color("#121216"), text="Loading preview…", fg=theme_color("#52525b"), font=PANEL_BADGE_FONT)
            preview_holder.pack(fill="x", pady=(8, 2))
            self._load_image_preview_async(att["content_url"], preview_holder)

        def _download_and_open(e=None, a=att, btn=open_att_btn):
            url = a.get("content_url")
            if not url:
                return
            btn.configure(text="Opening…")

            def worker():
                try:
                    email = self.app.session.get("email", "")
                    token = self.app.session.get("token", "")
                    raw_bytes = download_jira_bytes(url, email, token)
                    safe_name = "".join(c for c in a["filename"] if c.isalnum() or c in (" ", ".", "_", "-")).strip() or "attachment"
                    tmp_dir = Path(tempfile.gettempdir()) / "jira_notch_preview"
                    tmp_dir.mkdir(parents=True, exist_ok=True)
                    tmp_file = tmp_dir / safe_name
                    tmp_file.write_bytes(raw_bytes)
                    os.startfile(str(tmp_file))
                except Exception:
                    webbrowser.open(url)
                finally:
                    if btn.winfo_exists():
                        self.app.root.after(0, lambda: btn.configure(text="Open ↗"))

            threading.Thread(target=worker, daemon=True).start()

        open_att_btn.bind("<Button-1>", _download_and_open)

    def _load_image_preview_async(self, url: str, label_widget: tk.Label):
        def worker():
            try:
                email = self.app.session.get("email", "")
                token = self.app.session.get("token", "")
                raw = download_jira_bytes(url, email, token)
                pil_img = Image.open(io.BytesIO(raw))
                pil_img.thumbnail((430, 220), Image.Resampling.LANCZOS)
                tk_im = ImageTk.PhotoImage(pil_img)
                self.preview_images.append(tk_im)
                if label_widget.winfo_exists():
                    self.app.root.after(0, lambda: label_widget.configure(image=tk_im, text=""))
            except Exception:
                if label_widget.winfo_exists():
                    self.app.root.after(0, lambda: label_widget.destroy())

        threading.Thread(target=worker, daemon=True).start()

    def _start_drag(self, event):
        self.drag_x = event.x_root - self.pos_x
        self.drag_y = event.y_root - self.pos_y

    def _on_drag(self, event):
        self.pos_x = event.x_root - self.drag_x
        self.pos_y = event.y_root - self.drag_y
        if self.win and self.win.winfo_exists():
            self.win.geometry(f"+{self.pos_x}+{self.pos_y}")

    def close(self):
        if self.open_dropdown is not None:
            self.open_dropdown.close(restore_focus=False)
        if self.win and self.win.winfo_exists():
            w_ref = self.win
            self.win = None
            self.scroll_canvas = None
            start_r = (self.pos_x, self.pos_y, self.W, self.H)
            end_r = (self.pos_x + self.W // 2 - 60, self.pos_y + 20, 120, 38)
            animate_bubble_window(
                self.app.root,
                w_ref,
                start_r,
                end_r,
                start_alpha=1.0,
                end_alpha=0.0,
                duration_ms=140,
                on_complete=lambda: w_ref.destroy() if w_ref.winfo_exists() else None,
            )


class NotchDesktopWidget:
    WIN_W = 800
    WIN_H = 328

    COLLAPSED_W = 340
    COLLAPSED_H = 44
    EXPANDED_W = 732
    EXPANDED_H = 304

    NUM_STEPS = 61

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Notchi")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=TRANSPARENT_KEY)
        self.root.wm_attributes("-transparentcolor", TRANSPARENT_KEY)

        # Store per-user state & cached credentials in %LOCALAPPDATA%\Notchi so the standalone .exe never bundles personal tokens
        local_appdata = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        self.base_dir = local_appdata / "Notchi"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.base_dir / "widget_state.json"
        self.account_cache_file = self.base_dir / "account_cache.json"
        self.appearance_file = self.base_dir / "appearance.json"
        self.settings_win = None
        try:
            appearance = json.loads(self.appearance_file.read_text(encoding="utf-8"))
            set_theme_palette(appearance.get("colorway", "Graphite"), appearance.get("mode", "dark"))
        except (OSError, ValueError, AttributeError):
            set_theme_palette("Graphite", "dark")

        self.vx, self.vy, self.vw, self.vh = get_virtual_screen_bounds()
        primary_w = self.root.winfo_screenwidth()

        saved_x = self.load_saved_position()
        if saved_x is not None:
            self.win_x = self.clamp_x(saved_x)
        else:
            self.win_x = (primary_w - self.WIN_W) // 2
        self.win_y = 0
        self.placement = "top"
        self.side_docking_enabled = False
        self.settings_panel = None
        self.top_win_x = self.win_x
        self.side_shape_masks = {}
        try:
            position = json.loads(self.state_file.read_text(encoding="utf-8"))
            placement = position.get("placement", "top")
            self.side_docking_enabled = bool(position.get("side_docking_enabled", placement in ("left", "right")))
            if not self.side_docking_enabled:
                placement = "top"
            if placement in ("left", "right"):
                self.placement = placement
                self.top_win_x = position.get("top_win_x", self.win_x)
                center_x = position.get("monitor_x", self.win_x + self.WIN_W // 2)
                center_y = position.get("monitor_y", self.WIN_H // 2)
                self.dock_bounds = monitor_bounds_at(center_x, center_y)
                left, top, right, bottom = self.dock_bounds
                self.win_x = left if placement == "left" else right - self.WIN_W
                self.win_y = max(top, min(bottom - self.WIN_H, position.get("win_y", (top + bottom - self.WIN_H) // 2)))
        except (OSError, ValueError, TypeError, AttributeError):
            self.placement = "top"

        self.root.geometry(f"{self.WIN_W}x{self.WIN_H}+{self.win_x}+{self.win_y}")

        self.canvas = tk.Canvas(
            self.root,
            width=self.WIN_W,
            height=self.WIN_H,
            bg=TRANSPARENT_KEY,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas_image_id = self.canvas.create_image(0, 0, anchor="nw")
        self.control_feedback_item = None
        self.control_feedback_bounds = None
        self.control_feedback_color = theme_color("#09090b")
        self.control_feedback_target = theme_color("#09090b")
        self.control_feedback_pressed = False

        self.task_list_widget = StatusTaskListWidget(self)
        self.detail_widget = TaskDetailWidget(self)
        self.space_modal = SpaceSwitcherModal(self)

        # Load permanently cached account credentials (persisted forever until token expires or user updates key)
        self.session = self.load_cached_account()

        self.progress = 0.0
        self.target_progress = 0.0
        self.pinned = False
        self.collapsed_by_user = False
        self.active_tab = "nook"
        self.show_token_update_ui = not self.session.get("connected", False)
        self.is_syncing = False
        self.request_generation = 0
        self.sync_results = queue.Queue()
        self.metadata_results = queue.Queue()
        self.metadata_generation = 0
        self.metadata_busy = False
        self.metadata_attempts = {}
        self.metadata_checked_at = 0
        self.project_map = {}
        self.workflow_statuses = {}
        self.pending_reconcile_ids = set()
        self.status_write_cancel = threading.Event()
        self.manual_sync_active = False
        self.last_sync_epoch = 0.0
        self.last_sync_attempt_epoch = 0.0
        self.sync_failure_count = 0
        self.next_auto_sync_epoch = 0.0
        self.last_sync_error = ""
        self.sync_timeout_job = None
        self.last_data_signature = None
        self.login_status_msg = "Account cached permanently · Only update when API key expires"
        self.login_status_color = TEXT_MUTED
        self.hit_boxes = []
        self.account_transition = None

        self.dragging = False
        self.drag_moved = False
        self.drag_start_mouse_x = 0
        self.drag_start_win_x = 0

        self.frame_cache = {}
        self.transition_cache = {}
        self.content_cache = {}
        self.shape_masks = {}
        self.shape_results = queue.Queue()
        self.neutral_content = None
        self.content_warm_job = None
        self.current_step_idx = -1

        # Typography (2x supersampled scale)
        self.f_xxs = load_font(19, bold=False)
        self.f_xxs_b = load_font(19, bold=True)
        self.f_xs = load_font(22, bold=False)
        self.f_xs_b = load_font(22, bold=True)
        self.f_sm = load_font(25, bold=False)
        self.f_sm_b = load_font(26, bold=True)
        self.f_md = load_font(34, bold=True)
        self.f_lg = load_font(48, bold=True)

        self.data = {
            "total": 0,
            "finished": 0,
            "active": 0,
            "pct": 0,
            "counts": {},
            "kanban_statuses": list(KANBAN_STATUSES),
            "issues_by_status": {},
            "active_tickets": [],
            "project": self.session.get("project", "AUTO"),
            "project_display": self.session.get("project", "SM360"),
            "effective_role": self.session.get("role_mode", "AUTO"),
            "dev_total": 0,
            "iqa_total": 0,
            "user_spaces": [],
            "all_spaces": [],
            "role_total_all_spaces": 0,
            "base_url": self.session.get("base_url", ""),
            "updated_at": "Syncing…",
            "error": None,
        }

        if self.session.get("connected"):
            self.restore_dashboard_cache()

        self.login_widgets_visible = False
        self.focused_login_field = None
        self.show_token_plain = False
        self.build_login_entries()

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Motion>", self.on_control_motion)
        self.canvas.bind("<Leave>", self.on_control_leave)

        # Global pointer-aware mousewheel router so both Task List & Task Detail scroll anywhere inside their bounds
        self.root.bind_all("<MouseWheel>", self.on_global_mousewheel)

        self.menu = tk.Menu(self.root, tearoff=0, bg=theme_color("#141418"), fg=theme_color("#f4f4f6"), activebackground=theme_color("#262630"))
        self.menu.add_command(label="Refresh Jira Now", command=lambda: self.trigger_sync(manual=True))
        self.menu.add_command(label="Settings · Appearance & Updates…", command=self.open_settings)
        self.menu.add_command(label="View Last Sync Error", command=self.show_last_sync_error)
        self.menu.add_command(label="Open SM360 Board in Browser", command=self.open_board)
        self.menu.add_command(label="Toggle Pin Expanded", command=self.toggle_pin)
        self.menu.add_command(label="Update API Key / Account…", command=self.open_api_key_settings)
        self.menu.add_command(label="Sign Out (Clear Cached Account)", command=self.sign_out)
        self.menu.add_separator()
        self.menu.add_command(label="Snap to Center of Monitor 1", command=lambda: self.snap_to_monitor(0))
        self.menu.add_command(label="Snap to Center of Monitor 2", command=lambda: self.snap_to_monitor(1))
        self.menu.add_separator()
        self.menu.add_command(label="Quit Notch Widget", command=self.close_app)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        self.last_time = time.perf_counter()
        self.flash_until = time.perf_counter() + 2.2
        self.invalidate_cache()
        self.display_progress(0.0)
        self.prepare_animation_shapes()
        if self.session.get("connected"):
            self.trigger_sync()
        self.schedule_periodic_sync()
        self.tick()

    def dashboard_cache_path(self, session):
        account = jira_account_scope(session.get("base_url", ""), session.get("email", ""))[:24]
        view_key = dashboard_view_key(session)
        return self.base_dir / f"dashboard_{account}_{view_key}.json"

    def restore_dashboard_cache(self):
        try:
            path = self.dashboard_cache_path(self.session)
            saved = json.loads(path.read_text(encoding="utf-8"))
            scope = jira_account_scope(self.session["base_url"], self.session["email"], self.session["token"])
            if saved.get("version") != 1 or saved.get("auth_scope") != scope:
                return False
            data = saved["data"]
            if not isinstance(data, dict) or any(not isinstance(data.get(name), int) or data[name] < 0 for name in ("total", "active", "finished", "pct")):
                return False
            if data["active"] + data["finished"] != data["total"] or data["pct"] > 100:
                return False
            if not isinstance(data.get("counts"), dict) or any(not isinstance(name, str) or not isinstance(count, int) or count < 0 for name, count in data["counts"].items()):
                return False
            buckets = data.get("issues_by_status")
            if not isinstance(buckets, dict) or any(not isinstance(items, list) or any(not isinstance(ticket, dict) or any(not isinstance(ticket.get(key), str) for key in ("key", "summary", "status")) for ticket in items) for items in buckets.values()):
                return False
            projects = saved.get("projects") or {}
            workflows = saved.get("workflows") or {}
            if not isinstance(projects, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in projects.items()):
                return False
            if not isinstance(workflows, dict) or any(not isinstance(key, str) or not isinstance(values, list) or any(not isinstance(value, str) for value in values) for key, values in workflows.items()):
                return False
            if not isinstance(data.get("active_tickets"), list) or any(not isinstance(ticket, dict) or any(not isinstance(ticket.get(key), str) for key in ("key", "summary", "status")) for ticket in data["active_tickets"]):
                return False
            if any(not isinstance(data.get(key), str) for key in ("project", "project_display", "effective_role", "updated_at", "base_url")):
                return False
            if not isinstance(data.get("fetched_at"), (int, float)) or not math.isfinite(data["fetched_at"]) or data["fetched_at"] <= 0:
                return False
            if not isinstance(data.get("all_spaces"), list) or any(not isinstance(item, (list, tuple)) or len(item) != 2 or any(not isinstance(value, str) for value in item) for item in data["all_spaces"]):
                return False
            if not isinstance(data.get("user_spaces"), list) or any(not isinstance(item, (list, tuple)) or len(item) != 3 or not isinstance(item[0], str) or not isinstance(item[1], str) or not isinstance(item[2], int) for item in data["user_spaces"]):
                return False
            checked_at = float(saved.get("metadata_checked_at", 0))
            if not math.isfinite(checked_at):
                return False
            self.project_map = projects
            self.workflow_statuses = workflows
            self.metadata_checked_at = checked_at
            apply_workflow_metadata(data, self.workflow_statuses.get(data.get("project"), []))
            data.update(from_cache=True, refreshing=True, error=None)
            data["_view_key"] = dashboard_view_key(self.session)
            self.data = data
            return True
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            return False

    def save_dashboard_cache(self):
        if not self.session.get("connected") or self.data.get("error") or self.data.get("from_cache") or self.data.get("refreshing") or not self.data.get("fetched_at"):
            return
        if self.data.get("_view_key") != dashboard_view_key(self.session):
            return
        path = self.dashboard_cache_path(self.session)
        temporary = path.with_suffix(".tmp")
        envelope = {
            "version": 1,
            "auth_scope": jira_account_scope(self.session["base_url"], self.session["email"], self.session["token"]),
            "projects": self.project_map, "workflows": self.workflow_statuses,
            "metadata_checked_at": self.metadata_checked_at,
            "data": {key: value for key, value in self.data.items() if not key.startswith("_")},
        }
        try:
            temporary.write_text(json.dumps(envelope, separators=(",", ":")), encoding="utf-8")
            temporary.replace(path)
        except (OSError, ValueError, TypeError):
            pass

    def prepare_selected_view(self):
        if self.restore_dashboard_cache():
            return
        project = self.session.get("project", "AUTO")
        self.data = {
            "total": 0, "finished": 0, "active": 0, "pct": 0,
            "counts": {}, "issues_by_status": {}, "active_tickets": [],
            "kanban_statuses": list(KANBAN_STATUSES), "kanban_tiles": list(KANBAN_STATUSES),
            "project": project, "project_display": self.project_map.get(project, project),
            "effective_role": self.session.get("role_mode", "AUTO"),
            "dev_total": 0, "iqa_total": 0, "user_spaces": [],
            "all_spaces": sorted(self.project_map.items(), key=lambda item: item[1].lower()),
            "role_total_all_spaces": 0, "base_url": self.session.get("base_url", ""),
            "updated_at": "Loading…", "fetched_at": 0, "error": None,
            "from_cache": False, "refreshing": True,
            "_view_key": dashboard_view_key(self.session),
        }

    def invalidate_dashboard_snapshots(self):
        account = jira_account_scope(self.session.get("base_url", ""), self.session.get("email", ""))[:24]
        for path in self.base_dir.glob(f"dashboard_{account}_*"):
            if path.suffix in (".json", ".tmp"):
                try:
                    path.unlink()
                except OSError:
                    pass

    def clear_dashboard_cache(self):
        self.invalidate_dashboard_snapshots()
        scope = jira_account_scope(self.session.get("base_url", ""), self.session.get("email", ""), self.session.get("token", ""))
        WORKSPACE_PROJECTS_CACHE.pop(scope, None)
        for key in list(PROJECT_STATUSES_CACHE):
            if key[0] == scope:
                PROJECT_STATUSES_CACHE.pop(key, None)
        self.metadata_generation += 1
        self.metadata_busy = False
        self.metadata_checked_at = 0
        self.metadata_attempts.clear()
        self.project_map.clear()
        self.workflow_statuses.clear()
        self.detail_widget.detail_generation += 1
        self.detail_widget.detail_loading = False
        self.detail_widget.detail_cache.clear()

    def start_metadata_refresh(self):
        if self.metadata_busy or not self.session.get("connected"):
            return
        project = self.data.get("project", "ALL")
        due = time.time() - self.metadata_checked_at > 6 * 60 * 60
        missing = project not in ("ALL", "AUTO") and project not in self.workflow_statuses
        if not (due or missing) or time.time() - self.metadata_attempts.get(project, 0) < 60:
            return
        self.metadata_attempts[project] = time.time()
        self.metadata_busy = True
        generation = self.metadata_generation
        account = dict(self.session)
        previous_projects = dict(self.project_map)

        def worker():
            projects, statuses, error = previous_projects, [], None
            try:
                if due:
                    projects = get_workspace_projects(account["base_url"], account["email"], account["token"], refresh=True, cache_result=False)
                if project not in ("ALL", "AUTO"):
                    statuses = get_project_workflow_statuses(account["base_url"], account["email"], account["token"], project, refresh=due, cache_result=False)
            except Exception as exc:
                error = exc
            self.metadata_results.put((generation, account, project, projects, statuses, due, error))

        threading.Thread(target=worker, daemon=True).start()

    def drain_metadata_results(self):
        while True:
            try:
                generation, account, project, projects, statuses, directory_refreshed, error = self.metadata_results.get_nowait()
            except queue.Empty:
                break
            if generation != self.metadata_generation or not self.detail_widget.account_matches(account):
                continue
            self.metadata_busy = False
            if error is not None:
                continue
            self.project_map.update(projects)
            scope = jira_account_scope(account["base_url"], account["email"], account["token"])
            WORKSPACE_PROJECTS_CACHE[scope] = dict(self.project_map)
            if statuses:
                self.workflow_statuses[project] = statuses
                PROJECT_STATUSES_CACHE[(scope, project)] = list(statuses)
            if directory_refreshed:
                self.metadata_checked_at = time.time()
            self.data["all_spaces"] = sorted(self.project_map.items(), key=lambda item: item[1].lower())
            active_project = self.data.get("project")
            if active_project != "ALL":
                self.data["project_display"] = self.project_map.get(active_project, active_project)
            apply_workflow_metadata(self.data, self.workflow_statuses.get(active_project, []))
            self._on_sync_done()
            self.save_dashboard_cache()
            self.start_metadata_refresh()

    def load_cached_account(self) -> dict:
        """Loads permanently cached account from %LOCALAPPDATA%\\Notchi\\account_cache.json."""
        default_session = {
            "connected": False,
            "base_url": "https://ascendensasia-team.atlassian.net",
            "email": "",
            "token": "",
            "project": "AUTO",
            "role_mode": "AUTO",
            "manual_space_locked": False,
            "display_name": "",
            "initials": "NC",
        }
        try:
            if self.account_cache_file.exists():
                raw = json.loads(self.account_cache_file.read_text(encoding="utf-8"))
                tok = base64.b64decode(raw.get("token_b64", "").encode("ascii")).decode("utf-8") if raw.get("token_b64") else ""
                if raw.get("base_url") and raw.get("email") and tok:
                    return {
                        "connected": True,
                        "base_url": raw["base_url"],
                        "email": raw["email"],
                        "token": tok,
                        "project": raw.get("project", "AUTO"),
                        "role_mode": raw.get("role_mode", "AUTO"),
                        "manual_space_locked": raw.get("manual_space_locked", False),
                        "display_name": raw.get("display_name", raw["email"]),
                        "initials": raw.get("initials", "NC"),
                    }
        except Exception:
            pass
        return default_session

    def save_cached_account(self):
        """Persists account credentials permanently so the user never has to log in again unless the API key expires."""
        try:
            tok_b64 = base64.b64encode(self.session.get("token", "").encode("utf-8")).decode("ascii")
            payload = {
                "base_url": self.session.get("base_url", ""),
                "email": self.session.get("email", ""),
                "token_b64": tok_b64,
                "project": self.session.get("project", "AUTO"),
                "role_mode": self.session.get("role_mode", "AUTO"),
                "manual_space_locked": self.session.get("manual_space_locked", False),
                "display_name": self.session.get("display_name", ""),
                "initials": self.session.get("initials", "JC"),
            }
            self.account_cache_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            pass

    def build_login_entries(self):
        # Borderless iOS-style text inputs (zero inner rectangular border; the capsule itself renders the focus ring)
        entry_style = dict(
            bg="#15151a",
            fg=theme_color("#f4f4f6"),
            insertbackground=theme_color("#0a84ff"),
            insertwidth=2,
            selectbackground="#264f78",
            selectforeground=theme_color("#ffffff"),
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", 10),
        )
        self.url_var = tk.StringVar(value=self.session.get("base_url", "https://ascendensasia-team.atlassian.net"))
        self.email_var = tk.StringVar(value=self.session.get("email", ""))
        self.token_var = tk.StringVar(value=self.session.get("token", ""))
        self.proj_var = tk.StringVar(value=self.session.get("project", "AUTO"))

        self.ent_url = tk.Entry(self.canvas, textvariable=self.url_var, **entry_style)
        self.ent_proj = tk.Entry(self.canvas, textvariable=self.proj_var, **entry_style)
        self.ent_email = tk.Entry(self.canvas, textvariable=self.email_var, **entry_style)
        self.ent_token = tk.Entry(self.canvas, textvariable=self.token_var, show="•", **entry_style)

        field_map = [
            (self.ent_url, "url"),
            (self.ent_proj, "proj"),
            (self.ent_email, "email"),
            (self.ent_token, "token"),
        ]
        for ent, fname in field_map:
            ent.bind("<Return>", lambda e: self.connect_live())
            ent.bind("<FocusIn>", lambda e, fn=fname: self._on_login_field_focus(fn))
            ent.bind("<FocusOut>", lambda e, fn=fname: self._on_login_field_blur(fn))

    def _on_login_field_focus(self, field_name: str):
        self.focused_login_field = field_name
        # Match Entry background to the elevated active capsule fill (#1b1b22)
        for ent, fn in ((self.ent_url, "url"), (self.ent_proj, "proj"), (self.ent_email, "email"), (self.ent_token, "token")):
            ent.configure(bg=theme_color("#1b1b22") if fn == field_name else "#15151a")
        self.invalidate_cache()
        self.display_progress(self.progress)

    def _on_login_field_blur(self, field_name: str):
        if self.focused_login_field == field_name:
            self.focused_login_field = None
        for ent in (self.ent_url, self.ent_proj, self.ent_email, self.ent_token):
            ent.configure(bg="#15151a")
        self.invalidate_cache()
        self.display_progress(self.progress)

    def toggle_token_visibility(self):
        self.show_token_plain = not self.show_token_plain
        self.ent_token.configure(show="" if self.show_token_plain else "•")
        self.invalidate_cache()
        self.display_progress(self.progress)

    def set_login_widgets_visibility(self, visible: bool):
        if visible == self.login_widgets_visible:
            return
        self.login_widgets_visible = visible
        if visible:
            cx = self.WIN_W // 2
            left = cx - self.EXPANDED_W // 2 + 28
            # Vertically centered inside the 44px-tall iOS rounded capsules (Row 1: y=86..130, Row 2: y=160..204)
            # Note: KANBAN SPACE (top-right capsule) is now an interactive dropdown selector pill rather than a text box
            dx, dy = self.side_content_offset()
            self.ent_url.place(x=left + 16 + dx, y=97 + dy, width=460, height=22)
            self.ent_proj.place_forget()
            self.ent_email.place(x=left + 16 + dx, y=171 + dy, width=306, height=22)
            self.ent_token.place(x=left + 364 + dx, y=171 + dy, width=250, height=22)
            self.root.lift()
            if not self.email_var.get():
                self.ent_email.focus_set()
            else:
                self.ent_token.focus_set()
        else:
            for ent in (self.ent_url, self.ent_proj, self.ent_email, self.ent_token):
                ent.place_forget()

    def open_api_key_settings(self):
        """Opens the API Key renewal view inside the Notch (with existing account pre-filled)."""
        self.account_transition = None
        self.show_token_update_ui = True
        self.login_status_msg = "Account cached · Paste a new API key below if your key expired"
        self.login_status_color = TEXT_SECONDARY
        self.invalidate_cache()
        self.display_progress(self.progress)

    def cancel_api_key_settings(self):
        if self.session.get("connected"):
            self.cancel_pending_sync()
            self.show_token_update_ui = False
            self.invalidate_cache()
            self.display_progress(self.progress)

    def sign_out(self):
        """Signs out of the current account, deletes the cached credentials file, and returns to the login view."""
        self.cancel_pending_sync()
        self.clear_dashboard_cache()
        self.status_write_cancel.set()
        self.status_write_cancel = threading.Event()
        self.pending_reconcile_ids.clear()
        self.task_list_widget.close()
        self.detail_widget.close()
        try:
            if self.account_cache_file.exists():
                self.account_cache_file.unlink()
        except Exception:
            pass

        self.session = {
            "connected": False,
            "base_url": "https://ascendensasia-team.atlassian.net",
            "email": "",
            "token": "",
            "project": "AUTO",
            "role_mode": "AUTO",
            "manual_space_locked": False,
            "display_name": "",
            "initials": "NC",
        }
        self.email_var.set("")
        self.token_var.set("")
        self.proj_var.set("AUTO")
        self.last_data_signature = None
        self.data = {
            "total": 0,
            "finished": 0,
            "active": 0,
            "pct": 0,
            "counts": {},
            "kanban_statuses": list(KANBAN_STATUSES),
            "issues_by_status": {},
            "active_tickets": [],
            "project": "AUTO",
            "project_display": "Auto",
            "effective_role": "DEV",
            "dev_total": 0,
            "iqa_total": 0,
            "user_spaces": [],
            "all_spaces": [],
            "role_total_all_spaces": 0,
            "base_url": "",
            "updated_at": "--:--",
            "error": None,
        }
        self.show_token_update_ui = True
        self.login_status_msg = "Signed out · Cached account removed from this device"
        self.login_status_color = TEXT_SECONDARY
        self.start_account_transition(show_login=True)
        self.invalidate_cache()
        self.display_progress(self.progress)

    def connect_live(self):
        if self.is_syncing or self.account_transition is not None:
            return
        raw_url = self.url_var.get().strip()
        base_url = normalize_base_url(raw_url)
        auto_proj = extract_project_from_url(raw_url)
        project = (self.proj_var.get().strip() or auto_proj or "AUTO")
        self.proj_var.set(project)
        email = self.email_var.get().strip()
        token = self.token_var.get().strip()

        if not base_url or not email or not token:
            self.login_status_msg = "Please enter your Jira URL, Email, and API Token."
            self.login_status_color = COLOR_RETURNED
            self.invalidate_cache()
            self.display_progress(self.progress)
            return

        self.is_syncing = True
        self.login_status_msg = "Verifying account & discovering your Jira spaces…"
        self.login_status_color = COLOR_APPROVAL
        self.invalidate_cache()
        self.display_progress(self.progress)

        self.request_generation += 1
        generation = self.request_generation
        candidate = {
            "connected": True,
            "base_url": base_url,
            "email": email,
            "token": token,
            "project": project,
            "role_mode": self.session.get("role_mode", "AUTO"),
            "manual_space_locked": project not in ("AUTO", "ALL"),
        }

        def worker():
            fresh, error = None, None
            try:
                me = jira_request(base_url, email, token, "/rest/api/3/myself")
                disp_name = me.get("displayName", email)
                parts = [p[0].upper() for p in disp_name.split() if p]
                initials = "".join(parts[:2]) if parts else "JC"
                candidate.update(display_name=disp_name, initials=initials)
                fresh = fetch_jira_data(candidate)
            except Exception as e:
                error = e
            self.sync_results.put((generation, candidate, fresh, error, True, describe_sync_error(error, candidate)))

        threading.Thread(target=worker, daemon=True).start()

    def summon_to_cursor_monitor(self):
        self.collapsed_by_user = False
        self.root.deiconify()
        if self.placement != "top":
            self.dock_to_point(self.root.winfo_pointerx(), self.root.winfo_pointery())
            self.flash_until = time.perf_counter() + 2.5
            self.root.lift()
            return
        primary_w = max(self.root.winfo_screenwidth(), 1)
        mx = self.root.winfo_pointerx()
        mon_idx = int((mx - self.vx) // primary_w)
        mon_cx = self.vx + mon_idx * primary_w + primary_w // 2
        self.win_x = self.clamp_x(mon_cx - self.WIN_W // 2)
        self.root.geometry(f"{self.WIN_W}x{self.WIN_H}+{self.win_x}+{self.win_y}")
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.flash_until = time.perf_counter() + 2.5
        self.save_position()

    def clamp_x(self, x: int) -> int:
        self.vx, self.vy, self.vw, self.vh = get_virtual_screen_bounds()
        min_x = self.vx - (self.WIN_W - self.COLLAPSED_W) // 2 + 10
        max_x = self.vx + self.vw - (self.WIN_W + self.COLLAPSED_W) // 2 - 10
        return max(min_x, min(max_x, int(x)))

    def load_saved_position(self):
        try:
            if self.state_file.exists():
                st = json.loads(self.state_file.read_text(encoding="utf-8"))
                return st.get("win_x")
        except Exception:
            pass
        return None

    def save_position(self):
        try:
            self.state_file.write_text(json.dumps({"win_x": self.win_x if self.placement == "top" else self.top_win_x,
                                                     "top_win_x": self.top_win_x, "placement": self.placement,
                                                     "side_docking_enabled": self.side_docking_enabled,
                                                     "win_y": self.win_y,
                                                     "monitor_x": self.win_x + self.WIN_W // 2,
                                                     "monitor_y": self.win_y + self.WIN_H // 2}), encoding="utf-8")
        except Exception:
            pass

    def snap_to_monitor(self, monitor_index: int):
        if self.placement != "top":
            self.dock_to_point(monitor_index * self.root.winfo_screenwidth() + self.root.winfo_screenwidth() // 2, 100)
            return
        primary_w = self.root.winfo_screenwidth()
        target_cx = monitor_index * primary_w + primary_w // 2
        self.win_x = self.clamp_x(target_cx - self.WIN_W // 2)
        self.root.geometry(f"{self.WIN_W}x{self.WIN_H}+{self.win_x}+{self.win_y}")
        self.save_position()

    def on_double_click(self, event):
        if self.placement != "top":
            self.dock_to_point(self.win_x + self.WIN_W // 2, self.win_y + self.WIN_H // 2)
            return
        primary_w = max(self.root.winfo_screenwidth(), 1)
        notch_cx = self.win_x + self.WIN_W // 2
        mon_idx = int((notch_cx - self.vx) // primary_w)
        mon_cx = self.vx + mon_idx * primary_w + primary_w // 2
        self.win_x = self.clamp_x(mon_cx - self.WIN_W // 2)
        self.root.geometry(f"{self.WIN_W}x{self.WIN_H}+{self.win_x}+{self.win_y}")
        self.save_position()

    def on_global_mousewheel(self, event):
        """Routes mousewheel scrolling to whichever floating panel the cursor is currently over."""
        px = self.root.winfo_pointerx()
        py = self.root.winfo_pointery()
        dropdown = self.detail_widget.open_dropdown
        if dropdown is not None and dropdown.win is not None:
            window = dropdown.win
            if window.winfo_rootx() <= px < window.winfo_rootx() + window.winfo_width() and window.winfo_rooty() <= py < window.winfo_rooty() + window.winfo_height():
                return dropdown.scroll(event)
            dropdown.close()
        steps = int(-1 * (event.delta / 120))
        if steps == 0:
            steps = -1 if event.delta > 0 else 1

        # Check SpaceSwitcherModal, TaskDetailWidget, and StatusTaskListWidget
        for panel in (self.space_modal, self.detail_widget, self.task_list_widget, self.settings_panel):
            if panel is None:
                continue
            w = panel.win
            c = panel.scroll_canvas
            if w is not None and c is not None and w.winfo_exists() and w.winfo_viewable() and c.winfo_exists():
                wx, wy = panel.pos_x, panel.pos_y
                if wx <= px <= wx + panel.W and wy <= py <= wy + panel.H:
                    c.yview_scroll(steps, "units")
                    return

    def clear_control_feedback(self):
        stop_ui_motion(self.canvas, "notch-feedback")
        if self.control_feedback_item is not None:
            self.canvas.delete(self.control_feedback_item)
        self.control_feedback_item = None
        self.control_feedback_bounds = None
        self.control_feedback_color = theme_color("#09090b")
        self.control_feedback_target = theme_color("#09090b")
        self.canvas.configure(cursor="")

    def fade_control_feedback(self, target, remove=False):
        item = self.control_feedback_item
        if item is None:
            return
        if target == self.control_feedback_target:
            return
        self.control_feedback_target = target
        start = color_rgb(self.canvas, self.control_feedback_color)
        end = color_rgb(self.canvas, target)
        def paint(progress):
            self.control_feedback_color = blend_color(start, end, progress)
            self.canvas.itemconfigure(item, outline=self.control_feedback_color)
        animate_ui(self.canvas, "notch-feedback", 100, paint, self.clear_control_feedback if remove else None)

    def on_control_motion(self, event, pressed=False):
        if self.progress < 0.98 or self.drag_moved:
            self.clear_control_feedback()
            return
        hit = None
        for x1, y1, x2, y2, callback in self.hit_boxes:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                if self.account_transition is not None and callback not in (self.close_app, self.collapse_notch, self.toggle_pin):
                    continue
                hit = (x1, y1, x2, y2, callback)
                break
        if hit is None:
            self.on_control_leave(event)
            return
        x1, y1, x2, y2, callback = hit
        bounds = (x1, y1, x2, y2)
        if bounds != self.control_feedback_bounds:
            self.clear_control_feedback()
            self.control_feedback_bounds = bounds
            if (x2 - x1 < 24 and y2 - y1 < 28) or getattr(callback, "__name__", "") == "open_board":
                self.control_feedback_item = self.canvas.create_oval(x1, y1, x2, y2, outline=theme_color("#09090b"), width=1)
            else:
                radius = min((y2 - y1) / 2, 10)
                points = (x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
                          x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
                          x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1)
                self.control_feedback_item = self.canvas.create_polygon(points, smooth=True, splinesteps=12, fill="", outline=theme_color("#09090b"), width=1)
        self.canvas.configure(cursor="hand2")
        self.fade_control_feedback(theme_color("#a1a1aa") if pressed or self.control_feedback_pressed else theme_color("#555560"))

    def on_control_leave(self, event):
        self.canvas.configure(cursor="")
        if self.control_feedback_item is not None:
            self.fade_control_feedback(theme_color("#09090b"), remove=True)

    def on_mouse_down(self, event):
        self.control_feedback_pressed = True
        self.on_control_motion(event, pressed=True)
        if self.account_transition is not None:
            return
        self.dragging = True
        self.drag_moved = False
        self.drag_start_mouse_x = self.root.winfo_pointerx()
        self.drag_start_win_x = self.win_x
        self.drag_start_mouse_y = self.root.winfo_pointery()
        self.drag_start_win_y = self.win_y

    def on_mouse_drag(self, event):
        if not self.dragging:
            return
        if self.side_docking_enabled:
            dx = self.root.winfo_pointerx() - self.drag_start_mouse_x
            dy = self.root.winfo_pointery() - self.drag_start_mouse_y
            if abs(dx) > 4 or abs(dy) > 4:
                self.drag_moved = True
            if self.drag_moved:
                self.clear_control_feedback()
                self.win_x = self.drag_start_win_x + dx
                self.win_y = self.drag_start_win_y + dy
                self.root.geometry(f"{self.WIN_W}x{self.WIN_H}{self.win_x:+d}{self.win_y:+d}")
            return
        if self.placement != "top":
            dy = self.root.winfo_pointery() - self.drag_start_mouse_y
            if abs(dy) > 4:
                self.drag_moved = True
            if self.drag_moved:
                self.clear_control_feedback()
                left, top, right, bottom = self.dock_bounds
                self.win_y = max(top, min(bottom - self.WIN_H, self.drag_start_win_y + dy))
                self.root.geometry(f"{self.WIN_W}x{self.WIN_H}{self.win_x:+d}{self.win_y:+d}")
            return
        cur_mouse_x = self.root.winfo_pointerx()
        dx = cur_mouse_x - self.drag_start_mouse_x
        if abs(dx) > 4:
            self.drag_moved = True
        if self.drag_moved:
            self.clear_control_feedback()
            new_x = self.clamp_x(self.drag_start_win_x + dx)
            if new_x != self.win_x:
                self.win_x = new_x
                self.root.geometry(f"+{self.win_x}+{self.win_y}")

    def on_mouse_up(self, event):
        self.control_feedback_pressed = False
        was_drag = self.drag_moved
        self.dragging = False
        self.drag_moved = False
        if was_drag:
            self.clear_control_feedback()
            if self.side_docking_enabled:
                self.finish_drag_docking()
            self.save_position()
            return

        self.on_control_motion(event)
        mx, my = event.x, event.y
        for x1, y1, x2, y2, cb in self.hit_boxes:
            if x1 <= mx <= x2 and y1 <= my <= y2:
                if self.account_transition is not None and cb not in (self.close_app, self.collapse_notch, self.toggle_pin):
                    return
                cb()
                return

    def invalidate_cache(self):
        self.frame_cache.clear()
        # Mid-animation silhouettes contain no account/UI content and can be
        # reused across syncs, focus changes, tab switches, and login changes.
        self.frame_cache.update(self.transition_cache)
        self.content_cache.clear()
        self.current_step_idx = -1
        if self.content_warm_job is None:
            self.content_warm_job = self.root.after(32, self.warm_expanded_content)

    def prepare_animation_shapes(self):
        results = self.shape_results
        steps = self.NUM_STEPS
        dimensions = (
            self.WIN_W, self.WIN_H, self.COLLAPSED_W, self.COLLAPSED_H,
            self.EXPANDED_W, self.EXPANDED_H,
        )

        def worker():
            # Tk images and hit boxes stay on the UI thread. Only immutable
            # silhouette masks are prepared here, once for the app's lifetime.
            for idx in range(1, steps):
                results.put((idx, build_notch_shape_mask(idx / (steps - 1), *dimensions)))

        threading.Thread(target=worker, daemon=True).start()

    def drain_animation_shapes(self):
        while True:
            try:
                idx, mask = self.shape_results.get_nowait()
            except queue.Empty:
                break
            self.shape_masks.setdefault(idx, mask)

    def warm_expanded_content(self):
        self.content_warm_job = None
        if abs(self.target_progress - self.progress) > 0.003:
            # Do not schedule supersampled text/card drawing in a moving frame.
            self.content_warm_job = self.root.after(32, self.warm_expanded_content)
            return
        self.get_content_layer(True)

    def get_content_layer(self, expanded):
        if expanded not in self.content_cache:
            self.content_cache[expanded] = self.render_content_layer(1.0 if expanded else 0.0)
        return self.content_cache[expanded]

    def cancel_pending_sync(self):
        """Invalidate old workers; they may finish but cannot change this session."""
        self.request_generation += 1
        self.is_syncing = False
        self.manual_sync_active = False
        self.account_transition = None
        self.cancel_sync_timeout()

    def cancel_sync_timeout(self):
        if self.sync_timeout_job is not None:
            self.root.after_cancel(self.sync_timeout_job)
            self.sync_timeout_job = None

    def start_account_transition(self, show_login: bool, hold_ms: int = 0):
        """Pause briefly, collapse, then reveal the destination view on reopen."""
        self.account_transition = {
            "show_login": show_login,
            "phase": "hold" if hold_ms else "collapse",
            "until": time.perf_counter() + hold_ms / 1000,
        }
        self.dragging = False
        self.set_login_widgets_visibility(False)
        self.canvas.focus_set()
        self.space_modal.close()

    def advance_account_transition(self):
        transition = self.account_transition
        if transition is None:
            return False
        now = time.perf_counter()
        if transition["phase"] == "hold":
            self.target_progress = 1.0
            if now >= transition["until"]:
                transition["phase"] = "collapse"
        if transition["phase"] == "collapse":
            self.target_progress = 0.0
            if self.progress <= 0.003:
                self.progress = 0.0
                self.show_token_update_ui = transition["show_login"]
                transition["phase"] = "pause"
                transition["until"] = now + 0.12
                self.invalidate_cache()
                self.display_progress(0.0)
        elif transition["phase"] == "pause":
            self.target_progress = 0.0
            if now >= transition["until"]:
                self.account_transition = None
                self.target_progress = 1.0
                self.flash_until = now + 1.5
        return True

    def side_content_offset(self):
        if self.placement == "top":
            return 0, 0
        return (-34 if self.placement == "left" else 34), (self.WIN_H - self.EXPANDED_H) // 2

    def set_placement(self, placement, bounds=None, pointer_y=None):
        if placement not in ("top", "left", "right"):
            return
        if self.placement == "top" and bounds is None:
            self.top_win_x = self.win_x
        bounds = bounds or monitor_bounds_at(self.win_x + self.WIN_W // 2, self.win_y + self.WIN_H // 2)
        self.placement = placement
        self.dock_bounds = bounds
        left, top, right, bottom = bounds
        if placement == "top":
            self.win_x = self.clamp_x(self.top_win_x)
            self.win_y = top
        else:
            self.win_x = left if placement == "left" else right - self.WIN_W
            center_y = (top + bottom) // 2 if pointer_y is None else pointer_y
            self.win_y = max(top, min(bottom - self.WIN_H, center_y - self.WIN_H // 2))
        self.space_modal.close()
        if self.detail_widget.open_dropdown is not None:
            self.detail_widget.open_dropdown.close(restore_focus=False)
        self.clear_control_feedback()
        self.set_login_widgets_visibility(False)
        self.root.geometry(f"{self.WIN_W}x{self.WIN_H}{self.win_x:+d}{self.win_y:+d}")
        self.neutral_content = None
        self.transition_cache.clear()
        self.invalidate_cache()
        self.display_progress(self.progress)
        self.save_position()

    def dock_to_point(self, x, y):
        self.dock_bounds = monitor_bounds_at(x, y)
        left, top, right, bottom = self.dock_bounds
        self.win_x = left if self.placement == "left" else right - self.WIN_W
        self.win_y = max(top, (top + bottom - self.WIN_H) // 2)
        self.root.geometry(f"{self.WIN_W}x{self.WIN_H}{self.win_x:+d}{self.win_y:+d}")
        self.save_position()

    def finish_drag_docking(self):
        x, y = self.root.winfo_pointerx(), self.root.winfo_pointery()
        bounds = monitor_bounds_at(x, y)
        left, top, right, bottom = bounds
        distances = {"left": abs(x - left), "right": abs(right - x), "top": abs(y - top)}
        placement = min(distances, key=distances.get)
        if placement == "top":
            self.top_win_x = max(left - 34, min(right - self.WIN_W + 34, x - self.WIN_W // 2))
        elif self.placement == "top":
            self.top_win_x = self.drag_start_win_x
        self.set_placement(placement, bounds=bounds, pointer_y=y)

    def toggle_side_docking(self):
        self.side_docking_enabled = not self.side_docking_enabled
        if not self.side_docking_enabled and self.placement != "top":
            self.set_placement("top")
        self.refresh_side_toggle()
        self.save_position()

    def refresh_side_toggle(self):
        toggle = getattr(self, "side_toggle", None)
        if toggle is None or not toggle.winfo_exists():
            return
        image = Image.new("RGB", (192, 112), theme_color("#09090b"))
        draw = ImageDraw.Draw(image)
        color = theme_color("#0a84ff") if self.side_docking_enabled else theme_color("#30303a")
        draw.rounded_rectangle((8, 12, 184, 100), radius=44, fill=color)
        cx = 140 if self.side_docking_enabled else 52
        draw.ellipse((cx - 34, 22, cx + 34, 90), fill=theme_color("#f4f4f6"))
        toggle._switch_image = ImageTk.PhotoImage(image.resize((48, 28), Image.Resampling.LANCZOS), master=toggle)
        toggle.itemconfigure(toggle._switch_item, image=toggle._switch_image)
        self.side_toggle_note.set("Drag the notch to the left, right, or top edge." if self.side_docking_enabled else "Off · The notch stays at the top.")

    def refresh_update_controls(self):
        button = getattr(self, "update_button", None)
        if button is not None and button.winfo_exists():
            busy = getattr(self, "update_busy", False)
            button.configure(state="disabled" if busy else "normal",
                             text="Please wait…" if busy else "Update and restart" if getattr(self, "available_release", None) else "Check for updates")
            self.update_note.set(getattr(self, "update_message", "Check for a new version of Notchi."))

    def handle_update(self):
        if getattr(self, "update_busy", False):
            return
        release = getattr(self, "available_release", None)
        if release and not getattr(sys, "frozen", False):
            self.update_message = "Run the packaged Notchi.exe to install updates."
            self.refresh_update_controls()
            return
        self.update_busy = True
        self.update_message = "Downloading and verifying update…" if release else "Checking for updates…"
        self.refresh_update_controls()
        results = queue.Queue()
        def work():
            try:
                results.put((True, download_release(release) if release else check_release()))
            except Exception as exc:
                results.put((False, str(exc)))
        threading.Thread(target=work, daemon=True).start()
        def poll():
            try:
                success, result = results.get_nowait()
            except queue.Empty:
                self.root.after(100, poll)
                return
            self.update_busy = False
            if not success:
                self.update_message = "Update failed: " + result
            elif release:
                try:
                    launch_installer(result, sys.executable, os.getpid())
                except Exception as exc:
                    self.update_message = "Could not start update: " + str(exc)
                else:
                    self.close_app()
                    return
            else:
                self.available_release = result
                self.update_message = (f"Version {result['version']} is available. Updating will restart Notchi." if result
                                       else f"You're up to date · Version {APP_VERSION}")
            self.refresh_update_controls()
        self.root.after(100, poll)

    def open_settings(self):
        if self.settings_win is not None and self.settings_win.winfo_exists():
            self.settings_win.deiconify()
            self.settings_win.lift()
            self.settings_win.focus_set()
            return
        win = self.settings_win = tk.Toplevel(self.root)
        win.title("Notchi · Settings")
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", 0.0)
        win.configure(bg=theme_color("#09090b"))
        left, top, right, bottom = monitor_bounds_at(self.win_x + self.WIN_W // 2, self.win_y + self.WIN_H // 2)
        width, height = 460, min(660, bottom - top - 64)
        x = max(left + 16, min(right - width - 16, self.win_x + 140))
        y = top + max(24, (bottom - top - height) // 2)
        panel = self.settings_panel = SimpleNamespace(app=self, win=win, W=width, H=height, pos_x=x, pos_y=y, open_dropdown=None, scroll_canvas=None)
        outer = tk.Frame(win, bg=theme_color("#09090b"), highlightbackground=theme_color("#22222a"), highlightthickness=1)
        outer.pack(fill="both", expand=True)
        header = tk.Frame(outer, bg=theme_color("#09090b"), height=52)
        header.pack(fill="x", padx=18, pady=(6, 0))
        header.pack_propagate(False)
        add_window_controls(header, win.destroy, lambda: minimize_panel(panel), lambda: toggle_panel_zoom(panel))
        title = panel_label(header, text="Settings", bg=theme_color("#09090b"), fg=theme_color("#f4f4f6"), font=PANEL_TITLE_FONT, anchor="w")
        title.pack(side="left", fill="y")
        def start_drag(event):
            panel.drag_offset = (event.x_root - win.winfo_x(), event.y_root - win.winfo_y())
        def drag(event):
            if not hasattr(panel, "drag_offset"):
                return
            panel.pos_x = event.x_root - panel.drag_offset[0]
            panel.pos_y = event.y_root - panel.drag_offset[1]
            win.geometry(f"{panel.pos_x:+d}{panel.pos_y:+d}")
        for widget in (header, title):
            widget.bind("<ButtonPress-1>", start_drag)
            widget.bind("<B1-Motion>", drag)
        tk.Frame(outer, height=1, bg=theme_color("#22222a")).pack(fill="x", padx=18)
        canvas = panel.scroll_canvas = tk.Canvas(outer, bg=theme_color("#09090b"), highlightthickness=0, bd=0, yscrollincrement=18)
        canvas.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        body = tk.Frame(canvas, bg=theme_color("#09090b"), padx=4, pady=18)
        item = canvas.create_window(0, 0, window=body, anchor="nw")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(item, width=event.width))
        body.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        panel_label(body, text=f"Notchi {APP_VERSION}", bg=theme_color("#09090b"), fg=theme_color("#f4f4f6"), font=PANEL_TITLE_FONT, anchor="w").pack(fill="x")
        self.update_note = tk.StringVar()
        panel_label(body, textvariable=self.update_note, bg=theme_color("#09090b"), fg=theme_color("#a1a1aa"), font=PANEL_SMALL_FONT, anchor="w", wraplength=390).pack(fill="x", pady=(6, 10))
        self.update_button = MotionButton(body, text="Check for updates", command=self.handle_update,
                                         bg=theme_color("#141418"), fg=theme_color("#f4f4f6"),
                                         activebackground=theme_color("#24242e"), activeforeground=theme_color("#f4f4f6"),
                                         relief="flat", bd=0, padx=16, pady=10, font=PANEL_SMALL_FONT)
        self.update_button.pack(anchor="w", pady=(0, 18))
        self.refresh_update_controls()
        tk.Frame(body, height=1, bg=theme_color("#22222a")).pack(fill="x", pady=(0, 18))
        dock_row = tk.Frame(body, bg=theme_color("#09090b"))
        dock_row.pack(fill="x", pady=(0, 4))
        panel_label(dock_row, text="Side docking", bg=theme_color("#09090b"), fg=theme_color("#f4f4f6"), font=PANEL_BODY_FONT, anchor="w").pack(side="left")
        toggle = self.side_toggle = tk.Canvas(dock_row, width=48, height=28, bg=theme_color("#09090b"), bd=0, highlightthickness=0, takefocus=True, cursor="hand2")
        toggle.pack(side="right")
        toggle._switch_item = toggle.create_image(0, 0, anchor="nw")
        toggle._refresh_theme = self.refresh_side_toggle
        toggle.bind("<Button-1>", lambda event: self.toggle_side_docking())
        toggle.bind("<space>", lambda event: self.toggle_side_docking() or "break")
        toggle.bind("<Return>", lambda event: self.toggle_side_docking() or "break")
        toggle.bind("<FocusIn>", lambda event: toggle.configure(highlightthickness=1, highlightbackground=theme_color("#0a84ff")))
        toggle.bind("<FocusOut>", lambda event: toggle.configure(highlightthickness=0))
        self.side_toggle_note = tk.StringVar()
        panel_label(body, textvariable=self.side_toggle_note, bg=theme_color("#09090b"), fg=theme_color("#a1a1aa"), font=PANEL_SMALL_FONT, anchor="w", wraplength=400).pack(fill="x", pady=(0, 20))
        self.refresh_side_toggle()
        tk.Frame(body, height=1, bg=theme_color("#22222a")).pack(fill="x", pady=(0, 18))
        panel_label(body, text="Appearance", bg=theme_color("#09090b"), fg=theme_color("#f4f4f6"), font=PANEL_TITLE_FONT, anchor="w").pack(fill="x", pady=(0, 6))
        panel_label(body, text="Choose a mode and colorway", bg=theme_color("#09090b"), fg=theme_color("#a1a1aa"), font=PANEL_SMALL_FONT, anchor="w").pack(fill="x", pady=(0, 14))
        modes = tk.Frame(body, bg=theme_color("#09090b"))
        modes.pack(fill="x", pady=(0, 14))
        self.theme_mode_buttons = {}
        for mode in ("light", "dark"):
            button = MotionButton(modes, text=mode.title(), command=lambda mode=mode: self.apply_colorway(THEME_NAME, mode),
                                  bg=theme_color("#141418"), fg=theme_color("#f4f4f6"),
                                  activebackground=theme_color("#24242e"), activeforeground=theme_color("#f4f4f6"),
                                  relief="flat", bd=0, padx=24, pady=8, font=PANEL_SMALL_FONT,
                                  highlightthickness=1, highlightbackground=THEME_COLORS[THEME_NAME] if mode == THEME_MODE else theme_color("#26262e"))
            button.pack(side="left", expand=True, fill="x", padx=(0, 6))
            self.theme_mode_buttons[mode] = button
        grid = tk.Frame(body, bg=theme_color("#09090b"))
        grid.pack(fill="x")
        self.theme_buttons = {}
        self.theme_previews = {}
        for index, (name, accent) in enumerate(THEME_COLORS.items()):
            preview = ImageTk.PhotoImage(theme_gradient((24, 24), name), master=win)
            self.theme_previews[name] = preview
            button = MotionButton(grid, image=preview, compound="left", text="  " + name, command=lambda name=name: self.apply_colorway(name),
                                  bg=theme_color("#141418"), fg=theme_color("#f4f4f6"), activebackground=theme_color("#24242e"),
                                  activeforeground=theme_color("#f4f4f6"), relief="flat", bd=0, padx=10, pady=8,
                                  font=PANEL_SMALL_FONT, anchor="w", highlightthickness=1,
                                  highlightbackground=accent if name == THEME_NAME else theme_color("#26262e"))
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 8) if index % 2 == 0 else (0, 0), pady=(0, 8))
            self.theme_buttons[name] = button
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        self.theme_note = tk.StringVar(value=f"{THEME_NAME} · {THEME_MODE.title()} · Saved automatically")
        panel_label(body, textvariable=self.theme_note, bg=theme_color("#09090b"), fg=theme_color("#a1a1aa"), font=PANEL_SMALL_FONT, anchor="w", wraplength=370).pack(fill="x", pady=(10, 0))
        panel_label(body, text="Task status colors keep their meaning across themes.", bg=theme_color("#09090b"), fg=theme_color("#a1a1aa"), font=PANEL_SMALL_FONT, anchor="w", wraplength=370).pack(fill="x", pady=(8, 0))
        win.bind("<Escape>", lambda event: win.destroy())
        win.geometry(f"{width}x{height}{x:+d}{y:+d}")
        apply_windows11_rounded_shadow(win)
        animate_bubble_window(self.root, win, (x, y + 8, width, height), (x, y, width, height), start_alpha=0.0, end_alpha=1.0, duration_ms=160)

    def apply_colorway(self, name, mode=None):
        if name not in THEME_COLORS:
            return
        source_colors = (*THEME_NEUTRALS, *THEME_TEXT, "#0a84ff")
        previous = {color: theme_color(color) for color in source_colors}
        set_theme_palette(name, mode)
        remap = {previous[color]: theme_color(color) for color in source_colors}
        surfaces = {previous[color]: theme_color(color) for color in (*THEME_NEUTRALS, *THEME_TEXT)}
        def recolor(widget):
            if isinstance(widget, MotionButton):
                stop_ui_motion(widget, "button-color")
                widget._normal_color = remap.get(widget._normal_color, widget._normal_color)
                widget._hover_color = remap.get(widget._hover_color, widget._hover_color)
            for option in ("background", "activebackground", "foreground", "activeforeground", "highlightbackground", "highlightcolor", "selectbackground", "selectforeground", "disabledforeground", "insertbackground", "selectcolor"):
                try:
                    current = str(widget.cget(option))
                    mapping = surfaces if option in ("foreground", "activeforeground", "selectforeground", "disabledforeground") else remap
                    if current in mapping:
                        widget.configure(**{option: mapping[current]})
                except tk.TclError:
                    pass
            if isinstance(widget, tk.Canvas):
                for item in widget.find_all():
                    for option in ("fill", "outline"):
                        try:
                            current = widget.itemcget(item, option)
                            if current in surfaces:
                                widget.itemconfigure(item, **{option: surfaces[current]})
                        except tk.TclError:
                            pass
            if hasattr(widget, "_refresh_theme"):
                widget._refresh_theme()
            for child in widget.winfo_children():
                recolor(child)
        recolor(self.root)
        for colorway, button in getattr(self, "theme_buttons", {}).items():
            if button.winfo_exists():
                preview = ImageTk.PhotoImage(theme_gradient((24, 24), colorway), master=button)
                self.theme_previews[colorway] = preview
                button.configure(image=preview, highlightbackground=THEME_COLORS[colorway] if colorway == name else theme_color("#26262e"))
        for appearance, button in getattr(self, "theme_mode_buttons", {}).items():
            if button.winfo_exists():
                button.configure(highlightbackground=THEME_COLORS[name] if appearance == THEME_MODE else theme_color("#26262e"))
        try:
            temporary = self.appearance_file.with_suffix(".tmp")
            temporary.write_text(json.dumps({"colorway": name, "mode": THEME_MODE}), encoding="utf-8")
            temporary.replace(self.appearance_file)
            note = f"{name} · {THEME_MODE.title()} · Saved automatically"
        except OSError:
            note = f"Selected: {name} · Could not save preference"
        if hasattr(self, "theme_note"):
            self.theme_note.set(note)
        self.clear_control_feedback()
        self.neutral_content = None
        self.transition_cache.clear()
        self.invalidate_cache()
        self.display_progress(self.progress)

    def trigger_sync(self, manual: bool = False):
        if not self.session.get("connected") or self.is_syncing:
            return
        if not manual and time.time() < self.next_auto_sync_epoch:
            return
        self.last_sync_attempt_epoch = time.time()
        self.is_syncing = True
        self.manual_sync_active = manual
        self.request_generation += 1
        generation = self.request_generation
        snapshot = dict(self.session)
        snapshot["_project_map"] = dict(self.project_map)
        snapshot["_workflow_statuses"] = dict(self.workflow_statuses)
        if self.pending_reconcile_ids:
            snapshot["_reconcile_issue_ids"] = sorted(self.pending_reconcile_ids)
        self.data["refreshing"] = True
        self.data["error"] = None

        def worker():
            fresh, error = None, None
            try:
                fresh = fetch_jira_data(snapshot)
            except Exception as e:
                error = e
            self.sync_results.put((generation, snapshot, fresh, error, False, describe_sync_error(error, snapshot)))

        threading.Thread(target=worker, daemon=True).start()
        self.cancel_sync_timeout()
        self.sync_timeout_job = self.root.after(50_000, lambda: self.expire_sync(generation))
        self._on_sync_done()

    def expire_sync(self, generation):
        self.sync_timeout_job = None
        if generation != self.request_generation or not self.is_syncing:
            return
        self.request_generation += 1
        self.is_syncing = False
        self.manual_sync_active = False
        self.data["refreshing"] = False
        error = TimeoutError("Jira refresh did not finish within 50 seconds; the last successful data was kept")
        self.record_sync_error(error, str(error))
        self.data["error"] = self.last_sync_error
        self._on_sync_done()

    def record_sync_error(self, error, detail):
        self.sync_failure_count += 1
        delay = min(120, 10 * 2 ** min(self.sync_failure_count - 1, 4))
        if isinstance(error, urllib.error.HTTPError) and error.code == 429:
            try:
                delay = max(delay, min(900, float(error.headers.get("Retry-After", delay))))
            except (ValueError, TypeError):
                pass
        self.next_auto_sync_epoch = time.time() + delay
        self.last_sync_error = detail or type(error).__name__
        try:
            (self.base_dir / "sync_error.log").write_text(
                datetime.now().isoformat(timespec="seconds") + "\n" + self.last_sync_error + "\n", encoding="utf-8")
        except OSError:
            pass

    def show_last_sync_error(self):
        path = self.base_dir / "sync_error.log"
        if path.exists():
            os.startfile(str(path))

    def refresh_after_status_change(self, issue_id):
        if not self.session.get("connected"):
            return
        if str(issue_id).isdigit():
            self.pending_reconcile_ids.add(int(issue_id))
        # Discard an older read that could overwrite the newly changed status.
        self.request_generation += 1
        self.is_syncing = False
        self.manual_sync_active = False
        self.trigger_sync(manual=True)

    def drain_sync_results(self):
        """Apply worker results on the Tk thread, only for the current request."""
        while True:
            try:
                generation, snapshot, fresh, error, connecting, detail = self.sync_results.get_nowait()
            except queue.Empty:
                break
            if generation != self.request_generation:
                continue
            self.cancel_sync_timeout()
            self.is_syncing = False
            self.manual_sync_active = False
            self.data["refreshing"] = False
            if error is not None:
                self.record_sync_error(error, detail)
            if isinstance(error, JiraAuthExpiredError):
                self.clear_dashboard_cache()
                self.task_list_widget.close()
                self.detail_widget.close()
                self.space_modal.close()
                self.session["connected"] = False
                self.show_token_update_ui = True
                self.login_status_msg = "API Token expired or invalid · Click 'Get New API Key' below"
                self.login_status_color = COLOR_RETURNED
            elif error is not None:
                if connecting:
                    self.login_status_msg = f"Connection error: {error}"
                    self.login_status_color = COLOR_RETURNED
                else:
                    self.data["error"] = detail or str(error)
            else:
                if connecting:
                    self.clear_dashboard_cache()
                    self.status_write_cancel.set()
                    self.status_write_cancel = threading.Event()
                    self.pending_reconcile_ids.clear()
                    self.session = snapshot
                    self.proj_var.set(snapshot.get("project", "AUTO"))
                    self.save_cached_account()
                    self.show_token_update_ui = True
                    self.login_status_msg = "Connected · Opening your dashboard…"
                    self.login_status_color = COLOR_DONE
                    self.task_list_widget.close()
                    self.detail_widget.close()
                    self.start_account_transition(show_login=False, hold_ms=350)
                self.project_map.update(fresh.pop("_project_map", {}))
                self.workflow_statuses.update(fresh.pop("_workflow_statuses", {}))
                self.session["effective_role"] = fresh.get("effective_role", "DEV")
                self.data = fresh
                self.pending_reconcile_ids.difference_update(snapshot.get("_reconcile_issue_ids", []))
                self.last_sync_epoch = time.time()
                self.sync_failure_count = 0
                self.next_auto_sync_epoch = 0.0
                self.save_dashboard_cache()
                self.start_metadata_refresh()
            self._on_sync_done()

    def _on_sync_done(self):
        # Compute data signature so we ONLY clear the 25-frame render cache when Jira data actually changed!
        active_statuses = self.data.get("kanban_tiles", self.data.get("kanban_statuses", KANBAN_STATUSES))
        sig = json.dumps(
            {k: v for k, v in self.data.items() if not k.startswith("_") and k not in ("updated_at", "error", "fetched_at", "from_cache", "refreshing")},
            sort_keys=True,
        )
        ui_sig = (
            self.show_token_update_ui, self.login_status_msg, self.login_status_color,
            self.manual_sync_active, self.data.get("error"), self.data.get("updated_at"),
            self.data.get("from_cache"), self.data.get("refreshing"),
        )
        ui_changed = ui_sig != getattr(self, "last_ui_signature", None)
        self.last_ui_signature = ui_sig
        data_changed = sig != self.last_data_signature
        if data_changed:
            self.detail_widget.refresh_status_from_data(self.data)
        if data_changed or ui_changed:
            self.last_data_signature = sig
            self.invalidate_cache()
            self.display_progress(self.progress)

            tlw = self.task_list_widget
            if data_changed and tlw.win is not None and tlw.win.winfo_exists() and tlw.current_status:
                for api_name, display_label, accent in active_statuses:
                    if api_name == tlw.current_status:
                        tlw.show_status(api_name, display_label, accent)
                        break
                else:
                    tlw.close()
        else:
            # Data unchanged: keep all 25 pre-rendered 120FPS frames cached (zero CPU re-render)
            self.display_progress(self.progress)

    def schedule_periodic_sync(self):
        """Continuously auto-syncs Jira tasks in the background every 30 seconds with zero re-render if unchanged."""
        if self.session.get("connected") and not self.show_token_update_ui:
            self.trigger_sync(manual=False)
        self.root.after(30_000, self.schedule_periodic_sync)

    def get_space_selector_label(self, raw_key: str) -> str:
        """Returns a friendly display label for the selected Kanban space key."""
        k = (raw_key or "AUTO").strip().upper()
        if k == "AUTO":
            return "Auto-Detect"
        if k == "ALL":
            return "All Spaces"
        all_sp = self.data.get("all_spaces", []) or list(DEFAULT_WORKSPACE_SPACES)
        for pk, pname in all_sp:
            if pk.upper() == k or pname.upper() == k:
                if pname.upper() == pk.upper():
                    return pk
                short_name = pname if len(pname) <= 13 else pname[:12] + "…"
                return f"{short_name}"
        return k[:13]

    def select_or_switch_space(self, new_project_key: str):
        """Handles selecting a space from SpaceSwitcherModal (works both on the Login screen and in the Nook)."""
        self.proj_var.set(new_project_key)
        self.session["project"] = new_project_key
        self.session["manual_space_locked"] = new_project_key not in ("AUTO",)
        if self.show_token_update_ui:
            # On the Login / Account Setup screen: update the selector capsule immediately
            if self.is_syncing:
                self.cancel_pending_sync()
                self.login_status_msg = "Space selected · Click Save & Connect"
                self.login_status_color = TEXT_SECONDARY
            if self.session.get("connected"):
                self.save_cached_account()
            self.invalidate_cache()
            self.display_progress(self.progress)
        else:
            self.switch_space(new_project_key)

    def switch_space(self, new_project_key: str):
        """Switches the active Kanban space/project and triggers an immediate sync."""
        self.cancel_pending_sync()
        self.session["project"] = new_project_key
        self.session["manual_space_locked"] = new_project_key not in ("AUTO",)
        self.proj_var.set(new_project_key)
        self.save_cached_account()
        self.task_list_widget.close()
        self.detail_widget.close()
        self.prepare_selected_view()
        self.last_data_signature = None
        self.trigger_sync(manual=True)

    def cycle_role_mode(self):
        """Cycles role mode between AUTO (Dev/IQA auto-detect) -> DEV -> IQA -> ALL."""
        self.cancel_pending_sync()
        cur_eff = self.data.get("effective_role", "DEV")
        cur_mode = self.session.get("role_mode", "AUTO")
        if cur_mode == "AUTO":
            next_mode = "IQA" if cur_eff == "DEV" else "DEV"
        elif cur_mode == "DEV":
            next_mode = "IQA"
        elif cur_mode == "IQA":
            next_mode = "ALL"
        else:
            next_mode = "AUTO"
        self.session["role_mode"] = next_mode
        self.session["manual_space_locked"] = False
        self.save_cached_account()
        self.task_list_widget.close()
        self.detail_widget.close()
        self.prepare_selected_view()
        self.last_data_signature = None
        self.trigger_sync(manual=True)

    def open_space_switcher_menu(self, anchor_x=None, anchor_y=None):
        """Opens the custom iOS/macOS Space Switcher popover modal aligned under the board pill."""
        sx = anchor_x if anchor_x is not None else self.root.winfo_pointerx()
        sy = anchor_y if anchor_y is not None else self.root.winfo_pointery()
        self.space_modal.toggle_or_open(sx, sy)
        if self.show_token_update_ui:
            self.invalidate_cache()
            self.display_progress(self.progress)

    def open_board(self):
        base = self.session.get("base_url") or "https://ascendensasia-team.atlassian.net"
        proj = self.data.get("project") or "SM360"
        if proj in ("ALL", "AUTO"):
            user_spaces = self.data.get("user_spaces", [])
            proj = user_spaces[0][0] if user_spaces else "SM360"
        webbrowser.open(f"{base}/jira/software/projects/{proj}/boards/")

    def close_app(self):
        self.save_dashboard_cache()
        self.status_write_cancel.set()
        if self.detail_widget.open_dropdown is not None:
            self.detail_widget.open_dropdown.close(restore_focus=False)
        self.root.destroy()

    def collapse_notch(self):
        self.pinned = False
        self.collapsed_by_user = True
        self.flash_until = 0
        self.target_progress = 0.0
        self.space_modal.close()
        self.set_login_widgets_visibility(False)
        self.canvas.focus_set()
        self.invalidate_cache()
        self.display_progress(self.progress)

    def toggle_pin(self):
        if self.pinned:
            self.collapse_notch()
            return
        self.collapsed_by_user = False
        self.pinned = True
        self.target_progress = 1.0
        self.invalidate_cache()
        self.display_progress(self.progress)

    def switch_tab(self, tab_name: str):
        if self.active_tab != tab_name:
            self.active_tab = tab_name
            self.invalidate_cache()
            self.display_progress(self.progress)

    def on_right_click(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def get_box_for_progress(self, t: float):
        if self.placement != "top":
            nw = 44 + (self.EXPANDED_W - 44) * t
            nh = 180 + (self.EXPANDED_H - 180) * t
            x = 0 if self.placement == "left" else self.WIN_W - nw
            y = (self.WIN_H - nh) / 2
            return x, y, x + nw, y + nh, nw, nh
        nw = self.COLLAPSED_W + (self.EXPANDED_W - self.COLLAPSED_W) * t
        nh = self.COLLAPSED_H + (self.EXPANDED_H - self.COLLAPSED_H) * t
        cx = self.WIN_W / 2
        return cx - nw / 2, 0, cx + nw / 2, nh, nw, nh

    def check_pointer_hover(self):
        if self.advance_account_transition():
            return
        if self.dragging:
            return
        px = self.root.winfo_pointerx() - self.win_x
        py = self.root.winfo_pointery() - self.win_y
        x1, y1, x2, y2, _, _ = self.get_box_for_progress(self.progress)
        pad = 16 if self.progress > 0.25 else 8
        inside = (x1 - pad <= px <= x2 + pad) and (y1 - pad <= py <= y2 + pad)

        if self.collapsed_by_user:
            self.target_progress = 0.0
            if not inside:
                self.collapsed_by_user = False
            return

        focus_w = self.root.focus_get()
        typing_login = self.show_token_update_ui and (focus_w in (self.ent_url, self.ent_proj, self.ent_email, self.ent_token))
        space_modal_open = self.space_modal.is_open()
        flashing = time.perf_counter() < getattr(self, "flash_until", 0)
        new_target = 1.0 if (inside or self.pinned or flashing or typing_login or space_modal_open) else 0.0

        # Trigger an automatic background sync when the user hovers to expand if >10s since last sync
        if new_target == 1.0 and self.target_progress == 0.0:
            if self.session.get("connected") and not self.show_token_update_ui and (time.time() - max(self.last_sync_epoch, self.last_sync_attempt_epoch) > 10.0):
                self.trigger_sync(manual=False)

        self.target_progress = new_target

    def tick(self):
        frame_started = time.perf_counter()
        self.drain_animation_shapes()
        self.drain_sync_results()
        self.drain_metadata_results()
        self.detail_widget.drain_detail_results()
        self.detail_widget.drain_status_results()
        now = time.perf_counter()
        dt = min(now - self.last_time, 0.05)
        self.last_time = now

        previous_target = self.target_progress
        self.check_pointer_hover()
        if self.target_progress != previous_target:
            # An idle polling interval happened before the hover transition;
            # it must not advance the new animation by a whole idle interval.
            dt = min(dt, 1 / 120)
        diff = self.target_progress - self.progress

        if abs(diff) > 0.001:
            rate = 18.0 if self.target_progress > self.progress else 14.0
            step = 1.0 - pow(2.718281828, -rate * dt)
            self.progress += diff * step
            if abs(self.target_progress - self.progress) < 0.003:
                self.progress = self.target_progress
            self.display_progress(self.progress)

        should_show_entries = self.show_token_update_ui and self.account_transition is None and not self.collapsed_by_user and self.target_progress > 0 and (self.progress > 0.88)
        self.set_login_widgets_visibility(should_show_entries)

        moving = abs(self.target_progress - self.progress) > 0.001
        interval_ms = 1000 / 120 if moving else 24
        delay_ms = max(1, round(interval_ms - (time.perf_counter() - frame_started) * 1000))
        self.root.after(delay_ms, self.tick)

    def display_progress(self, t: float):
        if t < 0.98:
            self.clear_control_feedback()
        step_idx = int(round(t * (self.NUM_STEPS - 1)))
        step_idx = max(0, min(self.NUM_STEPS - 1, step_idx))
        if step_idx == self.current_step_idx and step_idx in self.frame_cache:
            return

        self.current_step_idx = step_idx
        quantized_t = step_idx / (self.NUM_STEPS - 1)

        if step_idx not in self.frame_cache:
            self.frame_cache[step_idx] = self.build_photo_image(quantized_t)

        tk_img, boxes = self.frame_cache[step_idx]
        self.tk_img = tk_img
        self.hit_boxes = boxes
        self.canvas.itemconfigure(self.canvas_image_id, image=self.tk_img)

    def build_photo_image(self, t: float):
        idx = int(round(t * (self.NUM_STEPS - 1)))
        if idx not in self.shape_masks:
            self.shape_masks[idx] = build_notch_shape_mask(
                t, self.WIN_W, self.WIN_H, self.COLLAPSED_W, self.COLLAPSED_H,
                self.EXPANDED_W, self.EXPANDED_H,
            )
        if t < 0.15:
            content, boxes = self.get_content_layer(False)
        elif t > 0.82:
            content, boxes = self.get_content_layer(True)
        else:
            if self.neutral_content is None:
                self.neutral_content, _ = self.render_content_layer(0.5, draw_content=False)
            content, boxes = self.neutral_content, []

        # Composite cached content against a cached shape at screen resolution.
        # The animation no longer redraws fonts/cards or runs Lanczos per step.
        final_img = Image.new("RGB", (self.WIN_W, self.WIN_H), TRANSPARENT_RGB)
        if self.placement == "top":
            mask = self.shape_masks[idx]
        else:
            key = (self.placement, idx)
            if key not in self.side_shape_masks:
                self.side_shape_masks[key] = build_side_shape_mask(t, self.WIN_W, self.WIN_H, self.placement)
            mask = self.side_shape_masks[key]
        final_img.paste(content, (0, 0), mask)
        frame = ImageTk.PhotoImage(final_img), boxes
        if 0.15 <= t <= 0.82:
            self.transition_cache[idx] = frame
        return frame

    def render_content_layer(self, t: float, draw_content: bool = True):
        S = 2
        W, H = self.WIN_W * S, self.WIN_H * S

        content_hi = theme_gradient((W, H))
        draw = ImageDraw.Draw(content_hi)

        nw = self.COLLAPSED_W + (self.EXPANDED_W - self.COLLAPSED_W) * t
        nh = self.COLLAPSED_H + (self.EXPANDED_H - self.COLLAPSED_H) * t
        cx = W / 2
        nw_s = nw * S
        nh_s = nh * S

        # Subtle hardware drag pill at top center
        grip_w = 34 * S
        draw.rounded_rectangle(
            [cx - grip_w / 2, 5 * S, cx + grip_w / 2, 7.5 * S],
            radius=2 * S,
            fill=theme_color("#2a2a34"),
        )

        boxes = []
        if draw_content and t < 0.15:
            self.draw_collapsed_content(draw, cx, nw_s, nh_s, S)
        elif draw_content and t > 0.82:
            if self.show_token_update_ui:
                self.draw_login_interface(draw, cx, nw_s, nh_s, S, boxes)
            else:
                self.draw_expanded_content(draw, cx, nw_s, nh_s, S, boxes)

        if self.placement != "top":
            if t < 0.15 and draw_content:
                content_hi = theme_gradient((W, H))
                strip = theme_gradient((180 * S, 44 * S))
                strip_draw = ImageDraw.Draw(strip)
                label = "Notchi" if self.show_token_update_ui else f"Notchi   {self.data.get('pct', 0)}%"
                strip_draw.text((90 * S, 22 * S), label, font=self.f_xs_b, fill=TEXT_PRIMARY, anchor="mm")
                strip = strip.transpose(Image.Transpose.ROTATE_90 if self.placement == "left" else Image.Transpose.ROTATE_270)
                content_hi.paste(strip, (0 if self.placement == "left" else W - 44 * S, (self.WIN_H - 180) * S // 2))
                boxes = []
            elif t > 0.82 and draw_content:
                dx, dy = self.side_content_offset()
                shifted = theme_gradient((W, H))
                shifted.paste(content_hi, (dx * S, dy * S))
                content_hi = shifted
                boxes = [(x1 + dx, y1 + dy, x2 + dx, y2 + dy, cb) for x1, y1, x2, y2, cb in boxes]
        content_1x = content_hi.resize((self.WIN_W, self.WIN_H), Image.Resampling.LANCZOS)
        return content_1x, boxes

    def draw_collapsed_content(self, draw: ImageDraw.ImageDraw, cx: float, nw_s: float, nh_s: float, S: int):
        left = cx - nw_s / 2
        right = cx + nw_s / 2
        cy = nh_s / 2 + 1 * S

        if self.show_token_update_ui:
            dot_x = left + 26 * S
            dot_r = 4.5 * S
            draw.ellipse([dot_x - dot_r, cy - dot_r, dot_x + dot_r, cy + dot_r], fill=COLOR_ON_HOLD)
            draw.text((dot_x + 12 * S, cy), "Notchi", font=self.f_xs_b, fill=TEXT_PRIMARY, anchor="lm")
            draw.text((right - 22 * S, cy), "API Key Setup", font=self.f_xs, fill=TEXT_SECONDARY, anchor="rm")
            return

        dot_x = left + 26 * S
        dot_r = 4.5 * S
        dot_col = COLOR_ON_HOLD if self.manual_sync_active or self.data.get("error") or self.data.get("from_cache") or self.data.get("refreshing") else COLOR_DONE
        draw.ellipse([dot_x - dot_r, cy - dot_r, dot_x + dot_r, cy + dot_r], fill=dot_col)

        first_fetch = self.data.get("refreshing") and not self.data.get("fetched_at")
        proj_label = self.data['project'] if first_fetch else f"{self.data['project']}   {self.data['total']}"
        draw.text((dot_x + 12 * S, cy), proj_label, font=self.f_xs_b, fill=TEXT_PRIMARY, anchor="lm")

        right_text = "Fetching tasks…" if first_fetch else f"{self.data['pct']}%  ·  {self.data['active']} open"
        text_right_x = right - 22 * S
        draw.text((text_right_x, cy), right_text, font=self.f_xs, fill=TEXT_SECONDARY, anchor="rm")

        text_w = draw.textlength(right_text, font=self.f_xs)
        ring_r = 9.5 * S
        ring_cx = text_right_x - text_w - 14 * S - ring_r
        bbox = [ring_cx - ring_r, cy - ring_r, ring_cx + ring_r, cy + ring_r]
        draw.arc(bbox, start=0, end=360, fill=BORDER_HAIRLINE, width=3 * S)
        end_ang = -90 + int(3.6 * self.data["pct"])
        if self.data["pct"] > 0:
            draw.arc(bbox, start=-90, end=end_ang, fill=COLOR_DONE, width=3 * S)

    def draw_window_controls(self, draw, left, top, scale, boxes):
        callbacks = (self.close_app, self.collapse_notch, self.toggle_pin)
        for index, (color, callback) in enumerate(zip(WINDOW_CONTROL_COLORS, callbacks)):
            x, y = left + (6 + index * 18) * scale, top + 14 * scale
            radius = 5.5 * scale
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color)
            boxes.append((x / scale - 8, y / scale - 9, x / scale + 8, y / scale + 9, callback))
        if self.pinned:
            x, y = left + 42 * scale, top + 14 * scale
            draw.line([x - 2.5 * scale, y, x + 2.5 * scale, y], fill="#145d22", width=2)

    def draw_login_interface(self, draw: ImageDraw.ImageDraw, cx: float, nw_s: float, nh_s: float, S: int, boxes: list):
        left = cx - nw_s / 2 + 28 * S
        right = cx + nw_s / 2 - 28 * S
        top = 18 * S
        self.draw_window_controls(draw, left, top, S, boxes)

        draw.text((right, nh_s - 22 * S), "Appearance settings", font=self.f_xxs, fill=TEXT_SECONDARY, anchor="rm")
        boxes.append(((right - 120 * S) / S, (nh_s - 34 * S) / S, right / S, (nh_s - 10 * S) / S, self.open_settings))
        # Header Badge Pill
        p_x1, p_y1, p_x2, p_y2 = left + 74 * S, top, left + 242 * S, top + 30 * S
        draw.rounded_rectangle([p_x1, p_y1, p_x2, p_y2], radius=15 * S, fill=SURFACE_ELEVATED)
        dot_x = p_x1 + 18 * S
        dot_y = (p_y1 + p_y2) / 2
        draw.ellipse([dot_x - 4 * S, dot_y - 4 * S, dot_x + 4 * S, dot_y + 4 * S], fill=COLOR_ON_HOLD)
        draw.text((dot_x + 10 * S, dot_y), "Account & API Key", font=self.f_xs_b, fill=TEXT_PRIMARY, anchor="lm")

        message = self.login_status_msg
        while message and draw.textlength(message, font=self.f_xxs) > right - p_x2 - 14 * S:
            message = message[:-2].rstrip("…") + "…"
        draw.text((p_x2 + 14 * S, dot_y), message, font=self.f_xxs, fill=self.login_status_color, anchor="lm")

        # Helper to draw an iOS/macOS inset capsule field with smooth active focus ring
        def draw_ios_field_capsule(x1, y1, x2, y2, field_id, label_text):
            is_focused = self.focused_login_field == field_id
            # Label above capsule with balanced 10px breathing room
            lbl_col = TEXT_PRIMARY if is_focused else TEXT_MUTED
            draw.text((x1 + 6 * S, y1 - 11 * S), label_text, font=self.f_xxs_b, fill=lbl_col, anchor="lm")

            fill_col = (27, 27, 34) if is_focused else (21, 21, 26)
            border_col = (74, 144, 255) if is_focused else (38, 38, 48)
            border_w = 3 if is_focused else 2

            # Subtle outer focus glow when active
            if is_focused:
                draw.rounded_rectangle(
                    [x1 - 2 * S, y1 - 2 * S, x2 + 2 * S, y2 + 2 * S],
                    radius=14 * S,
                    outline=(24, 52, 96),
                    width=2,
                )

            draw.rounded_rectangle(
                [x1, y1, x2, y2],
                radius=12 * S,
                fill=fill_col,
                outline=border_col,
                width=border_w,
            )

        # Row 1 Capsules: Jira Site URL + Selectable Kanban Space Dropdown (y = 86..130)
        r1_y1, r1_y2 = 86 * S, 130 * S
        draw_ios_field_capsule(left, r1_y1, left + 492 * S, r1_y2, "url", "JIRA SITE URL")

        sp_x1, sp_x2 = left + 506 * S, right
        is_space_open = self.space_modal.is_open()
        if is_space_open:
            self.focused_login_field = "proj"
        draw_ios_field_capsule(sp_x1, r1_y1, sp_x2, r1_y2, "proj", "KANBAN SPACE")
        if is_space_open and self.focused_login_field == "proj":
            self.focused_login_field = None

        # Draw selected Space label + indicator dot + vector downward chevron inside the KANBAN SPACE capsule
        cur_proj_key = (self.proj_var.get().strip() or "AUTO").upper()
        sp_disp = self.get_space_selector_label(cur_proj_key)
        sp_cy = (r1_y1 + r1_y2) / 2
        dot_col = COLOR_DONE if cur_proj_key == "AUTO" else COLOR_IN_PROGRESS
        draw.ellipse([sp_x1 + 14 * S - 3.5 * S, sp_cy - 3.5 * S, sp_x1 + 14 * S + 3.5 * S, sp_cy + 3.5 * S], fill=dot_col)
        draw.text((sp_x1 + 25 * S, sp_cy), sp_disp, font=self.f_xs_b, fill=TEXT_PRIMARY, anchor="lm")

        chev_cx = sp_x2 - 16 * S
        chev_cy = sp_cy + 1 * S
        draw.line([chev_cx - 4.5 * S, chev_cy - 2.5 * S, chev_cx, chev_cy + 2.5 * S], fill=TEXT_SECONDARY, width=3)
        draw.line([chev_cx, chev_cy + 2.5 * S, chev_cx + 4.5 * S, chev_cy - 2.5 * S], fill=TEXT_SECONDARY, width=3)

        login_sp_anchor_x = int(sp_x2 / S) - self.space_modal.W
        login_sp_anchor_y = int(r1_y2 / S)
        boxes.append(
            (
                sp_x1 / S,
                r1_y1 / S,
                sp_x2 / S,
                r1_y2 / S,
                lambda ax=login_sp_anchor_x, ay=login_sp_anchor_y: self.open_space_switcher_menu(self.win_x + ax + self.side_content_offset()[0], self.win_y + ay + self.side_content_offset()[1]),
            )
        )

        # Row 2 Capsules: Atlassian Account Email + API Token (y = 160..204)
        r2_y1, r2_y2 = 160 * S, 204 * S
        draw_ios_field_capsule(left, r2_y1, left + 336 * S, r2_y2, "email", "ATLASSIAN ACCOUNT EMAIL")
        draw_ios_field_capsule(left + 350 * S, r2_y1, right, r2_y2, "token", "API TOKEN (CACHED UNTIL EXPIRED)")

        # iOS-style inline "Show / Hide" toggle pill inside the right edge of the API Token capsule
        sh_x1, sh_y1, sh_x2, sh_y2 = right - 54 * S, r2_y1 + 8 * S, right - 8 * S, r2_y2 - 8 * S
        draw.rounded_rectangle([sh_x1, sh_y1, sh_x2, sh_y2], radius=8 * S, fill=theme_color("#202028"))
        sh_label = "Hide" if self.show_token_plain else "Show"
        draw.text(((sh_x1 + sh_x2) / 2, (sh_y1 + sh_y2) / 2), sh_label, font=self.f_xxs_b, fill=TEXT_SECONDARY, anchor="mm")
        boxes.append((sh_x1 / S, sh_y1 / S, sh_x2 / S, sh_y2 / S, self.toggle_token_visibility))

        # Bottom Action Row (y = 226..268)
        btn_y1, btn_y2 = 226 * S, 268 * S

        tok_x1, tok_x2 = left, left + 185 * S
        draw.rounded_rectangle([tok_x1, btn_y1, tok_x2, btn_y2], radius=12 * S, fill=SURFACE_CARD, outline=theme_color("#24242d"), width=2)
        draw.text(((tok_x1 + tok_x2) / 2 - 6 * S, (btn_y1 + btn_y2) / 2), "Get New API Key", font=self.f_xs_b, fill=TEXT_SECONDARY, anchor="mm")
        # Crisp vector north-east external link arrow (replaces unsupported Unicode tofu box)
        ax, ay = tok_x2 - 22 * S, (btn_y1 + btn_y2) / 2
        draw.line([ax - 4 * S, ay + 4 * S, ax + 4 * S, ay - 4 * S], fill=TEXT_SECONDARY, width=3)
        draw.line([ax - 2 * S, ay - 4 * S, ax + 4 * S, ay - 4 * S], fill=TEXT_SECONDARY, width=3)
        draw.line([ax + 4 * S, ay - 4 * S, ax + 4 * S, ay + 2 * S], fill=TEXT_SECONDARY, width=3)
        boxes.append((tok_x1 / S, btn_y1 / S, tok_x2 / S, btn_y2 / S, lambda: webbrowser.open("https://id.atlassian.com/manage-profile/security/api-tokens")))

        if self.session.get("connected"):
            back_x1, back_x2 = tok_x2 + 12 * S, tok_x2 + 95 * S
            draw.rounded_rectangle([back_x1, btn_y1, back_x2, btn_y2], radius=12 * S, fill=SURFACE_CARD, outline=theme_color("#24242d"), width=2)
            draw.text(((back_x1 + back_x2) / 2, (btn_y1 + btn_y2) / 2), "Back", font=self.f_xs, fill=TEXT_MUTED, anchor="mm")
            boxes.append((back_x1 / S, btn_y1 / S, back_x2 / S, btn_y2 / S, self.cancel_api_key_settings))

            so_x1, so_x2 = back_x2 + 10 * S, back_x2 + 120 * S
            draw.rounded_rectangle([so_x1, btn_y1, so_x2, btn_y2], radius=12 * S, fill=SURFACE_CARD, outline=theme_color("#24242d"), width=2)
            draw.text(((so_x1 + so_x2) / 2, (btn_y1 + btn_y2) / 2), "Sign Out", font=self.f_xs_b, fill=COLOR_RETURNED, anchor="mm")
            boxes.append((so_x1 / S, btn_y1 / S, so_x2 / S, btn_y2 / S, self.sign_out))

        con_x1, con_x2 = right - 210 * S, right
        con_bg = SURFACE_ELEVATED if self.is_syncing else TEXT_PRIMARY
        con_fg = TEXT_SECONDARY if self.is_syncing else NOTCH_BG
        draw.rounded_rectangle([con_x1, btn_y1, con_x2, btn_y2], radius=12 * S, fill=con_bg)
        con_label = "Saving…" if self.is_syncing else "Save & Connect"
        draw.text(((con_x1 + con_x2) / 2, (btn_y1 + btn_y2) / 2), con_label, font=self.f_xs_b, fill=con_fg, anchor="mm")
        boxes.append((con_x1 / S, btn_y1 / S, con_x2 / S, btn_y2 / S, self.connect_live))

    def draw_expanded_content(self, draw: ImageDraw.ImageDraw, cx: float, nw_s: float, nh_s: float, S: int, boxes: list):
        left = cx - nw_s / 2 + 26 * S
        right = cx + nw_s / 2 - 26 * S
        top = 18 * S
        self.draw_window_controls(draw, left, top, S, boxes)

        # --- TOP BAR: Authentic macOS Alcove Nook / Active Pill Tabs ---
        t1_x1, t1_y1, t1_x2, t1_y2 = left + 74 * S, top, left + 164 * S, top + 28 * S
        t1_bg = SURFACE_ELEVATED if self.active_tab == "nook" else SURFACE_CARD
        t1_fg = TEXT_PRIMARY if self.active_tab == "nook" else TEXT_MUTED
        draw.rounded_rectangle([t1_x1, t1_y1, t1_x2, t1_y2], radius=14 * S, fill=t1_bg, outline=THEME_COLORS[THEME_NAME] if self.active_tab == "nook" else t1_bg, width=S)
        dot_x = t1_x1 + 20 * S
        dot_y = (t1_y1 + t1_y2) / 2
        draw.ellipse([dot_x - 3.5 * S, dot_y - 3.5 * S, dot_x + 3.5 * S, dot_y + 3.5 * S], fill=COLOR_DONE if self.active_tab == "nook" else TEXT_MUTED)
        draw.text((dot_x + 10 * S, dot_y), "Nook", font=self.f_xs_b, fill=t1_fg, anchor="lm")
        boxes.append((t1_x1 / S, t1_y1 / S, t1_x2 / S, t1_y2 / S, lambda: self.switch_tab("nook")))

        t2_x1, t2_y1, t2_x2, t2_y2 = t1_x2 + 8 * S, top, t1_x2 + 114 * S, top + 28 * S
        t2_bg = SURFACE_ELEVATED if self.active_tab == "active" else SURFACE_CARD
        t2_fg = TEXT_PRIMARY if self.active_tab == "active" else TEXT_MUTED
        draw.rounded_rectangle([t2_x1, t2_y1, t2_x2, t2_y2], radius=14 * S, fill=t2_bg, outline=THEME_COLORS[THEME_NAME] if self.active_tab == "active" else t2_bg, width=S)
        draw.text(
            ((t2_x1 + t2_x2) / 2, (t2_y1 + t2_y2) / 2),
            f"Active ({self.data['active']})",
            font=self.f_xs_b,
            fill=t2_fg,
            anchor="mm",
        )
        boxes.append((t2_x1 / S, t2_y1 / S, t2_x2 / S, t2_y2 / S, lambda: self.switch_tab("active")))

        # Green now owns expanded/pinned mode; keep account actions on the right.
        out_x1, out_y1, out_x2, out_y2 = right - 78 * S, top, right, top + 28 * S
        draw.rounded_rectangle([out_x1, out_y1, out_x2, out_y2], radius=14 * S, fill=SURFACE_CARD)
        draw.text(((out_x1 + out_x2) / 2, (out_y1 + out_y2) / 2), "Sign Out", font=self.f_xxs_b, fill=TEXT_MUTED, anchor="mm")
        boxes.append((out_x1 / S, out_y1 / S, out_x2 / S, out_y2 / S, self.sign_out))

        key_x1, key_y1, key_x2, key_y2 = out_x1 - 80 * S, top, out_x1 - 6 * S, top + 28 * S
        draw.rounded_rectangle([key_x1, key_y1, key_x2, key_y2], radius=14 * S, fill=SURFACE_CARD)
        draw.text(((key_x1 + key_x2) / 2, (key_y1 + key_y2) / 2), "API Key", font=self.f_xxs_b, fill=TEXT_MUTED, anchor="mm")
        boxes.append((key_x1 / S, key_y1 / S, key_x2 / S, key_y2 / S, self.open_api_key_settings))

        ref_x1, ref_y1, ref_x2, ref_y2 = key_x1 - 88 * S, top, key_x1 - 6 * S, top + 28 * S
        draw.rounded_rectangle([ref_x1, ref_y1, ref_x2, ref_y2], radius=14 * S, fill=SURFACE_CARD)
        ref_dot_x = ref_x1 + 14 * S
        ref_dot_y = (ref_y1 + ref_y2) / 2
        ref_dot_col = COLOR_ON_HOLD if self.data.get("refreshing") or self.data.get("error") else COLOR_DONE
        draw.ellipse([ref_dot_x - 3 * S, ref_dot_y - 3 * S, ref_dot_x + 3 * S, ref_dot_y + 3 * S], fill=ref_dot_col)
        ref_label = "Syncing…" if self.data.get("refreshing") else ("Retry" if self.data.get("error") else "Auto-Sync")
        draw.text((ref_dot_x + 8 * S, ref_dot_y), ref_label, font=self.f_xxs_b, fill=TEXT_MUTED, anchor="lm")
        boxes.append((ref_x1 / S, ref_y1 / S, ref_x2 / S, ref_y2 / S, lambda: self.trigger_sync(manual=True)))

        user_name = self.session.get("display_name", "")
        settings_x = ref_x1 - 22 * S
        settings_y = top + 14 * S
        draw.rounded_rectangle([settings_x - 14 * S, top, settings_x + 14 * S, top + 28 * S], radius=14 * S, fill=SURFACE_CARD)
        for tooth in range(8):
            angle = tooth * math.pi / 4
            draw.line([settings_x + math.cos(angle) * 5 * S, settings_y + math.sin(angle) * 5 * S,
                       settings_x + math.cos(angle) * 7 * S, settings_y + math.sin(angle) * 7 * S], fill=TEXT_SECONDARY, width=2 * S)
        draw.ellipse([settings_x - 5 * S, settings_y - 5 * S, settings_x + 5 * S, settings_y + 5 * S], outline=TEXT_SECONDARY, width=S)
        draw.ellipse([settings_x - 2 * S, settings_y - 2 * S, settings_x + 2 * S, settings_y + 2 * S], outline=TEXT_SECONDARY, width=S)
        boxes.append(((settings_x - 14 * S) / S, top / S, (settings_x + 14 * S) / S, (top + 28 * S) / S, self.open_settings))
        available = max(0, settings_x - 18 * S - t2_x2 - 16 * S)
        while len(user_name) > 1 and draw.textlength(user_name, font=self.f_xxs) > available:
            user_name = user_name[:-2].rstrip("…") + "…"
        if available > draw.textlength("…", font=self.f_xxs):
            draw.text(((t2_x2 + settings_x - 18 * S) / 2, top + 14 * S), user_name, font=self.f_xxs, fill=TEXT_MUTED, anchor="mm")

        if self.active_tab == "nook":
            self.draw_nook_overview(draw, left, right, top + 40 * S, nh_s, S, boxes)
        else:
            self.draw_active_tickets_tab(draw, left, right, top + 40 * S, nh_s, S, boxes)

    def draw_nook_overview(self, draw: ImageDraw.ImageDraw, left: float, right: float, content_top: float, nh_s: float, S: int, boxes: list):
        counts = self.data.get("counts", {})
        active_statuses = self.data.get("kanban_statuses", KANBAN_STATUSES)

        # LEFT COLUMN: Clean macOS Activity Ring + High-Contrast Metric Center
        ring_cx = left + 76 * S
        ring_cy = content_top + 108 * S
        ring_r = 64 * S
        ring_w = 12 * S
        bbox = [ring_cx - ring_r, ring_cy - ring_r, ring_cx + ring_r, ring_cy + ring_r]

        draw.arc(bbox, start=0, end=360, fill=theme_color("#1a1a20"), width=ring_w)

        total = max(self.data["total"], 1)
        cur_angle = -90.0
        for api_name, _, color in reversed(active_statuses):
            cnt = counts.get(api_name, 0)
            if cnt <= 0:
                continue
            span = (cnt / total) * 360.0
            draw.arc(bbox, start=cur_angle, end=cur_angle + span, fill=color, width=ring_w)
            cur_angle += span

        draw.text((ring_cx, ring_cy - 10 * S), f"{self.data['pct']}%", font=self.f_lg, fill=TEXT_PRIMARY, anchor="mm")
        draw.text((ring_cx, ring_cy + 20 * S), f"{self.data['finished']} of {self.data['total']} done", font=self.f_xxs_b, fill=TEXT_MUTED, anchor="mm")

        boxes.append(((ring_cx - ring_r) / S, (ring_cy - ring_r) / S, (ring_cx + ring_r) / S, (ring_cy + ring_r) / S, self.open_board))

        # 1px Hairline Vertical Divider
        div_x = left + 170 * S
        draw.line([div_x, content_top + 10 * S, div_x, content_top + 214 * S], fill=theme_color("#1c1c22"), width=2)

        # RIGHT COLUMN: Interactive Space Switcher Header + Role Badge + 3x3 Grid of Status Tiles
        rx = div_x + 20 * S
        proj_disp = self.data.get("project_display") or self.data.get("project", "SM360")
        if len(proj_disp) > 20:
            proj_disp = proj_disp[:19] + "…"
        board_label = proj_disp if proj_disp == "All Spaces" else f"{proj_disp} Board"

        # Clickable Space Switcher Pill (with custom vector chevron instead of unsupported Unicode ▾)
        lbl_w = draw.textlength(board_label, font=self.f_xs_b)
        sp_x1, sp_y1, sp_x2, sp_y2 = rx, content_top - 2 * S, rx + lbl_w + 34 * S, content_top + 22 * S
        draw.rounded_rectangle([sp_x1, sp_y1, sp_x2, sp_y2], radius=8 * S, fill=theme_color("#141419"), outline=BORDER_HAIRLINE, width=2)
        draw.text((sp_x1 + 10 * S, (sp_y1 + sp_y2) / 2), board_label, font=self.f_xs_b, fill=TEXT_PRIMARY, anchor="lm")
        # Vector downward chevron (∨)
        chev_cx = sp_x2 - 13 * S
        chev_cy = (sp_y1 + sp_y2) / 2 + 1 * S
        draw.line([chev_cx - 4 * S, chev_cy - 2 * S, chev_cx, chev_cy + 2 * S], fill=TEXT_SECONDARY, width=2)
        draw.line([chev_cx, chev_cy + 2 * S, chev_cx + 4 * S, chev_cy - 2 * S], fill=TEXT_SECONDARY, width=2)
        anchor_sx = int(sp_x1 / S)
        anchor_sy = int(sp_y2 / S)
        boxes.append((sp_x1 / S, sp_y1 / S, sp_x2 / S, sp_y2 / S, lambda ax=anchor_sx, ay=anchor_sy: self.open_space_switcher_menu(self.win_x + ax + self.side_content_offset()[0], self.win_y + ay + self.side_content_offset()[1])))

        # Clickable Role Pill (Dev / IQA / All) right next to the Space Switcher pill
        eff_role = self.data.get("effective_role", "DEV")
        role_text = f"Role: {eff_role}"
        rw = draw.textlength(role_text, font=self.f_xxs_b)
        rl_x1, rl_y1, rl_x2, rl_y2 = sp_x2 + 8 * S, content_top - 2 * S, sp_x2 + rw + 26 * S, content_top + 22 * S
        role_accent = COLOR_APPROVAL if eff_role == "IQA" else (COLOR_IN_PROGRESS if eff_role == "DEV" else COLOR_DONE)
        draw.rounded_rectangle([rl_x1, rl_y1, rl_x2, rl_y2], radius=8 * S, fill=theme_color("#141419"), outline=BORDER_HAIRLINE, width=2)
        draw.text(((rl_x1 + rl_x2) / 2, (rl_y1 + rl_y2) / 2), role_text, font=self.f_xxs_b, fill=role_accent, anchor="mm")
        boxes.append((rl_x1 / S, rl_y1 / S, rl_x2 / S, rl_y2 / S, self.cycle_role_mode))

        if self.data.get("refreshing"):
            sync_label = "Updating…"
        elif self.data.get("error"):
            sync_label = "Saved · offline" if self.data.get("from_cache") else "Sync failed"
        else:
            sync_label = f"Synced {self.data['updated_at']}"
        draw.text((right, content_top + 10 * S), sync_label, font=self.f_xxs, fill=COLOR_ON_HOLD if self.data.get("error") or self.data.get("from_cache") else TEXT_MUTED, anchor="rm")
        if self.data.get("error") and not self.data.get("refreshing"):
            width = draw.textlength(sync_label, font=self.f_xxs)
            boxes.append(((right - width) / S, (content_top - 2 * S) / S, right / S, (content_top + 23 * S) / S, self.show_last_sync_error))

        cols = 3
        gap_x = 8 * S
        gap_y = 8 * S
        grid_w = right - rx
        card_w = (grid_w - gap_x * (cols - 1)) / cols
        card_h = 54 * S
        grid_top = content_top + 32 * S

        visible_tiles = self.data.get("kanban_tiles", active_statuses[:9])
        for idx, (api_name, display_label, accent) in enumerate(visible_tiles):
            r = idx // cols
            c = idx % cols
            cx1 = rx + c * (card_w + gap_x)
            cy1 = grid_top + r * (card_h + gap_y)
            cx2 = cx1 + card_w
            cy2 = cy1 + card_h

            val = (len(self.data.get("issues_by_status", {}).get(api_name, []))
                   if api_name == OVERFLOW_STATUS_KEY else counts.get(api_name, 0))
            tile_bg = SURFACE_CARD if val > 0 else (15, 15, 18)
            draw.rounded_rectangle([cx1, cy1, cx2, cy2], radius=10 * S, fill=tile_bg, outline=theme_color("#202028") if val > 0 else theme_color("#141419"), width=2)

            dot_r = 4 * S
            dot_fill = accent if val > 0 else (62, 62, 70)
            draw.ellipse([cx1 + 12 * S - dot_r, cy1 + 16 * S - dot_r, cx1 + 12 * S + dot_r, cy1 + 16 * S + dot_r], fill=dot_fill)

            lbl_color = TEXT_SECONDARY if val > 0 else (82, 82, 91)
            val_color = TEXT_PRIMARY if val > 0 else (68, 68, 76)
            draw.text((cx1 + 22 * S, cy1 + 16 * S), display_label, font=self.f_xxs_b, fill=lbl_color, anchor="lm")
            draw.text((cx1 + 12 * S, cy1 + 38 * S), str(val), font=self.f_sm_b, fill=val_color, anchor="lm")

            card_center_x = (cx1 + cx2) / (2 * S)
            card_center_y = (cy1 + cy2) / (2 * S)
            boxes.append(
                (
                    cx1 / S,
                    cy1 / S,
                    cx2 / S,
                    cy2 / S,
                    lambda st=api_name, lbl=display_label, col=accent, ox=card_center_x, oy=card_center_y: self.task_list_widget.show_status(
                        st, lbl, col, origin_screen_pt=(self.win_x + ox + self.side_content_offset()[0], self.win_y + oy + self.side_content_offset()[1])
                    ),
                )
            )

    def draw_active_tickets_tab(self, draw: ImageDraw.ImageDraw, left: float, right: float, content_top: float, nh_s: float, S: int, boxes: list):
        tickets = self.data.get("active_tickets", [])
        active_statuses = self.data.get("kanban_statuses", KANBAN_STATUSES)
        if not tickets:
            proj_disp = self.data.get("project_display") or self.data.get("project", "SM360")
            draw.text(((left + right) / 2, content_top + 95 * S), f"All {proj_disp} tasks for your role are resolved", font=self.f_sm, fill=TEXT_MUTED, anchor="mm")
            return

        row_h = 38 * S
        gap = 8 * S
        color_map = {api: col for api, _, col in active_statuses}

        for i, t in enumerate(tickets[:5]):
            ry1 = content_top + i * (row_h + gap)
            ry2 = ry1 + row_h
            draw.rounded_rectangle([left, ry1, right, ry2], radius=9 * S, fill=SURFACE_CARD, outline=(30, 30, 38), width=2)

            key_str = t["key"]
            draw.text((left + 14 * S, (ry1 + ry2) / 2), key_str, font=self.f_xs_b, fill=TEXT_SECONDARY, anchor="lm")

            raw_sum = t["summary"]
            prefix = key_str + " | "
            summary = raw_sum[len(prefix):] if raw_sum.startswith(prefix) else raw_sum
            if len(summary) > 48:
                summary = summary[:47] + "…"
            draw.text((left + 112 * S, (ry1 + ry2) / 2), summary, font=self.f_xs, fill=TEXT_PRIMARY, anchor="lm")

            st = t["status"]
            _, fallback_col, _ = get_status_display_and_color(st)
            st_col = color_map.get(st, fallback_col)
            draw.text((right - 14 * S, (ry1 + ry2) / 2), st, font=self.f_xxs_b, fill=st_col, anchor="rm")

            hex_col = rgb_to_hex(st_col)
            boxes.append((left / S, ry1 / S, right / S, ry2 / S, lambda tk_obj=t, hc=hex_col: self.detail_widget.show_ticket(tk_obj, hc, 480, 230)))


def acquire_single_instance_socket():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", SINGLE_INSTANCE_PORT))
        sock.listen(5)
        return sock
    except OSError:
        sock.close()
        try:
            client = socket.create_connection(("127.0.0.1", SINGLE_INSTANCE_PORT), timeout=1.0)
            client.sendall(b"SUMMON")
            client.close()
        except Exception:
            pass
        return None


def main():
    lock_sock = acquire_single_instance_socket()
    if lock_sock is None:
        sys.exit(0)
    root = tk.Tk()
    app = NotchDesktopWidget(root)

    def ipc_listener():
        while True:
            try:
                conn, _ = lock_sock.accept()
                data = conn.recv(64)
                conn.close()
                if data:
                    root.after(0, app.summon_to_cursor_monitor)
            except Exception:
                break

    threading.Thread(target=ipc_listener, daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    main()
