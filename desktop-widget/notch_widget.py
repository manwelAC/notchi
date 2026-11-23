import os
import io
import sys
import time
import json
import base64
import ctypes
import socket
import tempfile
import threading
import queue
import webbrowser
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime
from collections import Counter
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk, ImageFont

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


def jira_request(base_url, email, token, path, method="GET", body=None):
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
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise JiraAuthExpiredError(f"HTTP {e.code}: API token expired or invalid")
        raise


def download_jira_bytes(url: str, email: str, token: str) -> bytes:
    auth_str = f"{email}:{token}"
    b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {b64_auth}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


# In-memory cache of project metadata & per-project workflow statuses so we don't re-fetch every 30s
WORKSPACE_PROJECTS_CACHE = {}      # base_url -> {key: name}
PROJECT_STATUSES_CACHE = {}        # (base_url, project_key) -> [status_name, ...]


def get_workspace_projects(base_url: str, email: str, token: str) -> dict:
    if base_url in WORKSPACE_PROJECTS_CACHE and WORKSPACE_PROJECTS_CACHE[base_url]:
        return WORKSPACE_PROJECTS_CACHE[base_url]
    try:
        projs = jira_request(base_url, email, token, "/rest/api/3/project")
        mapping = {}
        if isinstance(projs, list):
            for p in projs:
                k = p.get("key", "").strip().upper()
                n = p.get("name", "").strip()
                if k:
                    mapping[k] = n or k
        WORKSPACE_PROJECTS_CACHE[base_url] = mapping
        return mapping
    except Exception:
        return {"SM360": "SM360"}


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


def get_project_workflow_statuses(base_url: str, email: str, token: str, project_key: str) -> list:
    if not project_key or project_key in ("ALL", "AUTO"):
        return [s[0] for s in KANBAN_STATUSES]
    cache_key = (base_url, project_key)
    if cache_key in PROJECT_STATUSES_CACHE:
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
            PROJECT_STATUSES_CACHE[cache_key] = statuses
            return statuses
    except Exception:
        pass
    return [s[0] for s in KANBAN_STATUSES]


def _run_jql_query(base_url: str, email: str, token: str, jql: str, requested_fields: list) -> list:
    issues = []
    next_page_token = None
    while True:
        payload = {
            "jql": jql,
            "maxResults": 100,
            "fields": requested_fields,
        }
        if next_page_token:
            payload["nextPageToken"] = next_page_token
        res = jira_request(base_url, email, token, "/rest/api/3/search/jql", method="POST", body=payload)
        batch = res.get("issues", [])
        issues.extend(batch)
        next_page_token = res.get("nextPageToken")
        if not next_page_token or res.get("isLast", True):
            break
    return issues


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

    proj_map = get_workspace_projects(base_url, email, token)
    resolved_proj = resolve_project_input(raw_project, proj_map)

    requested_fields = [
        "summary",
        "status",
        "issuetype",
        "priority",
        "project",
        "assignee",
        "updated",
        "created",
        "description",
        "environment",
        "attachment",
        "customfield_10278",  # Document ID
        "customfield_10001",  # Team
        "customfield_10311",  # Consult To
        "customfield_10179",  # IQA Officer
    ]

    # A failed search is not a successful empty result: keep the last good board.
    dev_issues = _run_jql_query(
        base_url, email, token, "assignee = currentUser() ORDER BY updated DESC", requested_fields
    )

    # 2. Fetch IQA issues (IQA Officer cf[10179] = currentUser() OR watcher = currentUser()) across all spaces
    try:
        iqa_issues = _run_jql_query(
            base_url,
            email,
            token,
            "(cf[10179] = currentUser() OR watcher = currentUser()) AND (assignee != currentUser() OR assignee is EMPTY) ORDER BY updated DESC",
            requested_fields,
        )
    except JiraAuthExpiredError:
        raise
    except urllib.error.HTTPError as exc:
        # Jira rejects an unavailable custom field with 400. Network/server errors
        # must not silently remove IQA tasks from the displayed totals.
        if exc.code != 400:
            raise
        iqa_issues = _run_jql_query(
            base_url,
            email,
            token,
            "watcher = currentUser() AND (assignee != currentUser() OR assignee is EMPTY) ORDER BY updated DESC",
            requested_fields,
        )

    # 3. Fallback for PMs / Reporters who only create/report tickets (0 Dev and 0 IQA assignments)
    if not dev_issues and not iqa_issues:
        dev_issues = _run_jql_query(
            base_url, email, token, "reporter = currentUser() ORDER BY updated DESC", requested_fields
        )

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
        wf_statuses = get_project_workflow_statuses(base_url, email, token, active_project)
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
            author_name = att.get("author", {}).get("displayName", "")
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
        self.win.configure(bg="#09090b")

        self.pos_x = int(anchor_screen_x)
        self.pos_y = int(anchor_screen_y + 6)
        apply_windows11_rounded_shadow(self.win)

        outer = tk.Frame(self.win, bg="#09090b", highlightbackground="#262630", highlightthickness=1, bd=0)
        outer.pack(fill="both", expand=True)

        # Top Header + Close
        top_bar = tk.Frame(outer, bg="#09090b", height=38)
        top_bar.pack(fill="x", padx=12, pady=(8, 2))
        top_bar.pack_propagate(False)

        tk.Label(
            top_bar,
            text="SWITCH KANBAN SPACE",
            bg="#09090b",
            fg="#696973",
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left", pady=8)

        close_lbl = tk.Label(
            top_bar,
            text="✕",
            bg="#09090b",
            fg="#696973",
            font=("Segoe UI", 9),
            padx=4,
            cursor="hand2",
        )
        close_lbl.pack(side="right", pady=6)
        close_lbl.bind("<Enter>", lambda e: close_lbl.configure(fg="#f4f4f6"))
        close_lbl.bind("<Leave>", lambda e: close_lbl.configure(fg="#696973"))
        close_lbl.bind("<Button-1>", lambda e: self.close())

        # Search Filter Capsule
        search_box = tk.Frame(outer, bg="#141419", highlightbackground="#24242e", highlightthickness=1, padx=10, pady=5)
        search_box.pack(fill="x", padx=12, pady=(0, 8))

        search_var = tk.StringVar(value="")
        search_ent = tk.Entry(
            search_box,
            textvariable=search_var,
            bg="#141419",
            fg="#f4f4f6",
            insertbackground="#0a84ff",
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", 9),
        )
        search_ent.pack(fill="x")

        # Scrollable Spaces List
        list_wrap = tk.Frame(outer, bg="#09090b")
        list_wrap.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        canvas = tk.Canvas(list_wrap, bg="#09090b", highlightthickness=0, bd=0)
        self.scroll_canvas = canvas
        list_frame = tk.Frame(canvas, bg="#09090b")

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
                    bg="#09090b",
                    fg="#52525b",
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
                    bg="#09090b",
                    fg="#52525b",
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
        bg_norm = "#181820" if is_selected else "#111115"
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
        dot_col = "#32d74b" if is_selected else ("#0a84ff" if is_highlighted else "#3f3f46")
        dot_c.create_oval(2, 2, 8, 8, fill=dot_col, outline="")

        # Title + optional key badge
        lbl_text = f"{title} ({subtitle})" if subtitle else title
        if len(lbl_text) > 26:
            lbl_text = lbl_text[:25] + "…"
        title_lbl = tk.Label(
            row,
            text=lbl_text,
            bg=bg_norm,
            fg="#f4f4f6" if (is_selected or is_highlighted) else "#a1a1aa",
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
                fg="#f4f4f6" if is_selected else "#a1a1aa",
                font=("Consolas", 8, "bold"),
                padx=7,
                pady=1,
            )
            cnt_lbl.pack(side="right")

        def on_pick(e=None, k=key):
            self.close()
            self.app.select_or_switch_space(k)

        def on_enter(e):
            row.configure(bg="#1d1d26", highlightbackground="#3e3e4f")
            dot_c.configure(bg="#1d1d26")
            title_lbl.configure(bg="#1d1d26", fg="#ffffff")

        def on_leave(e):
            row.configure(bg=bg_norm, highlightbackground=border_norm)
            dot_c.configure(bg=bg_norm)
            title_lbl.configure(bg=bg_norm, fg="#f4f4f6" if (is_selected or is_highlighted) else "#a1a1aa")

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
        self.drag_x = 0
        self.drag_y = 0
        self.pos_x = 76
        self.pos_y = 240

    def show_status(self, status_api_name: str, display_label: str, accent_rgb: tuple, origin_screen_pt=None):
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
            self.win.configure(bg="#09090b")

            primary_w = max(self.app.root.winfo_screenwidth(), 1)
            notch_cx = self.app.win_x + self.app.WIN_W // 2
            mon_idx = int((notch_cx - self.app.vx) // primary_w)
            mon_left = self.app.vx + mon_idx * primary_w
            self.pos_x = mon_left + 72
            self.pos_y = 230
            apply_windows11_rounded_shadow(self.win)
        else:
            for child in self.win.winfo_children():
                child.destroy()
            self.win.lift()

        outer = tk.Frame(self.win, bg="#09090b", highlightbackground="#22222a", highlightthickness=1, bd=0)
        outer.pack(fill="both", expand=True)

        # Clean Header Bar
        header = tk.Frame(outer, bg="#09090b", height=52)
        header.pack(fill="x", side="top", padx=16, pady=(6, 0))
        header.pack_propagate(False)

        dot_canvas = tk.Canvas(header, width=12, height=12, bg="#09090b", highlightthickness=0)
        dot_canvas.pack(side="left", padx=(2, 8), pady=20)
        dot_canvas.create_oval(2, 2, 10, 10, fill=accent_hex, outline="")

        title_lbl = tk.Label(
            header,
            text=display_label,
            bg="#09090b",
            fg="#f4f4f6",
            font=("Segoe UI Semibold", 11, "bold"),
        )
        title_lbl.pack(side="left", pady=12)

        count_badge = tk.Label(
            header,
            text=str(len(tickets)),
            bg="#18181f",
            fg="#a1a1aa",
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=1,
        )
        count_badge.pack(side="left", padx=8, pady=15)

        close_btn = tk.Label(
            header,
            text="✕",
            bg="#09090b",
            fg="#696973",
            font=("Segoe UI", 10),
            padx=6,
            cursor="hand2",
        )
        close_btn.pack(side="right", pady=14)
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg="#f4f4f6"))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg="#696973"))
        close_btn.bind("<Button-1>", lambda e: self.close())

        # 1px Hairline Divider
        tk.Frame(outer, bg="#1c1c22", height=1).pack(fill="x", padx=16, pady=(2, 6))

        for w in (header, title_lbl, count_badge):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

        # Scrollable Task List Area
        list_container = tk.Frame(outer, bg="#09090b")
        list_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        canvas = tk.Canvas(list_container, bg="#09090b", highlightthickness=0, bd=0, yscrollincrement=18)
        self.scroll_canvas = canvas
        scroll_frame = tk.Frame(canvas, bg="#09090b")

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win_id = canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=self.W - 36)
        canvas.bind("<Configure>", lambda e, cid=canvas_win_id: canvas.itemconfigure(cid, width=max(100, e.width - 4)))

        canvas.pack(side="left", fill="both", expand=True)

        if not tickets:
            tk.Label(
                scroll_frame,
                text=f"No tasks in {display_label}",
                bg="#09090b",
                fg="#696973",
                font=("Segoe UI", 9),
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

    def _create_task_card(self, parent, ticket: dict, accent_hex: str):
        card = tk.Frame(
            parent,
            bg="#121216",
            highlightbackground="#1e1e26",
            highlightthickness=1,
            padx=16,
            pady=13,
            cursor="hand2",
        )
        card.pack(fill="x", pady=(0, 8), padx=2)

        top_row = tk.Frame(card, bg="#121216")
        top_row.pack(fill="x")

        key_lbl = tk.Label(
            top_row,
            text=ticket["key"],
            bg="#121216",
            fg="#a1a1aa",
            font=("Consolas", 9, "bold"),
        )
        key_lbl.pack(side="left")

        att_cnt = len(ticket.get("attachments", []))
        if att_cnt > 0:
            att_badge = tk.Label(
                top_row,
                text=f"{att_cnt} file{'s' if att_cnt > 1 else ''}",
                bg="#1b1b22",
                fg="#a1a1aa",
                font=("Segoe UI", 8),
                padx=6,
                pady=1,
            )
            att_badge.pack(side="right")

        if ticket.get("doc_id") and ticket["doc_id"] != "—":
            doc_lbl = tk.Label(
                top_row,
                text=ticket["doc_id"],
                bg="#1b1b22",
                fg="#a1a1aa",
                font=("Consolas", 8),
                wraplength=self.W - 240,
                padx=6,
                pady=1,
            )
            doc_lbl.pack(side="left", padx=(8, 0))
        else:
            doc_lbl = None

        clean_sum = clean_ticket_summary(ticket)

        sum_lbl = tk.Label(
            card,
            text=clean_sum,
            bg="#121216",
            fg="#f4f4f6",
            font=("Segoe UI Semibold", 10),
            wraplength=self.W - 76,
            justify="left",
            anchor="w",
        )
        sum_lbl.pack(fill="x", pady=(6, 3))

        desc_preview = ticket.get("description", "").replace("\n", " ").strip()
        if len(desc_preview) > 90:
            desc_preview = desc_preview[:89] + "…"
        desc_lbl = tk.Label(
            card,
            text=desc_preview,
            bg="#121216",
            fg="#9696a2",
            font=("Segoe UI", 9),
            wraplength=self.W - 76,
            justify="left",
            anchor="w",
        )
        if desc_preview and desc_preview != "No description provided.":
            desc_lbl.pack(fill="x", pady=(2, 0))

        def on_select(e=None, tk_obj=ticket, col=accent_hex):
            ox = e.x_root if e else (self.pos_x + self.W // 2)
            oy = e.y_root if e else (self.pos_y + 120)
            self.app.detail_widget.show_ticket(tk_obj, col, self.pos_x + self.W + 14, self.pos_y, origin_screen_pt=(ox, oy))

        def on_enter(e):
            card.configure(bg="#19191f", highlightbackground="#32323e")
            top_row.configure(bg="#19191f")
            key_lbl.configure(bg="#19191f", fg="#f4f4f6")
            sum_lbl.configure(bg="#19191f")
            desc_lbl.configure(bg="#19191f")

        def on_leave(e):
            card.configure(bg="#121216", highlightbackground="#1e1e26")
            top_row.configure(bg="#121216")
            key_lbl.configure(bg="#121216", fg="#a1a1aa")
            sum_lbl.configure(bg="#121216")
            desc_lbl.configure(bg="#121216")

        widgets = [card, top_row, key_lbl, sum_lbl, desc_lbl]
        if att_cnt > 0:
            widgets.append(att_badge)
        if doc_lbl:
            widgets.append(doc_lbl)
        for w in widgets:
            w.bind("<Button-1>", on_select)
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

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

    def show_ticket(self, ticket: dict, accent_hex: str, default_x: int, default_y: int, origin_screen_pt=None):
        self.preview_images.clear()
        is_new_win = self.win is None or not self.win.winfo_exists()
        if is_new_win:
            self.win = tk.Toplevel(self.app.root)
            self.win.title(ticket["key"])
            self.win.overrideredirect(True)
            self.win.attributes("-topmost", True)
            self.win.attributes("-alpha", 0.0)
            self.win.configure(bg="#09090b")
            self.pos_x = default_x
            self.pos_y = default_y
            apply_windows11_rounded_shadow(self.win)
        else:
            for child in self.win.winfo_children():
                child.destroy()
            self.win.lift()

        outer = tk.Frame(self.win, bg="#09090b", highlightbackground="#22222a", highlightthickness=1, bd=0)
        outer.pack(fill="both", expand=True)

        # Header Bar: Breadcrumb Key + Status Pill + Open in Jira + Close
        header = tk.Frame(outer, bg="#09090b", height=52)
        header.pack(fill="x", side="top", padx=18, pady=(6, 0))
        header.pack_propagate(False)

        key_badge = tk.Label(
            header,
            text=ticket["key"],
            bg="#09090b",
            fg="#a1a1aa",
            font=("Consolas", 10, "bold"),
        )
        key_badge.pack(side="left", pady=14)

        dot_c = tk.Canvas(header, width=10, height=10, bg="#09090b", highlightthickness=0)
        dot_c.pack(side="left", padx=(12, 5), pady=20)
        dot_c.create_oval(2, 2, 8, 8, fill=accent_hex, outline="")

        status_pill = tk.Label(
            header,
            text=ticket["status"],
            bg="#09090b",
            fg="#e4e4e7",
            font=("Segoe UI Semibold", 9),
        )
        status_pill.pack(side="left", pady=14)

        close_btn = tk.Label(
            header,
            text="✕",
            bg="#09090b",
            fg="#696973",
            font=("Segoe UI", 10),
            padx=6,
            cursor="hand2",
        )
        close_btn.pack(side="right", pady=14)
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg="#f4f4f6"))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg="#696973"))
        close_btn.bind("<Button-1>", lambda e: self.close())

        base_url = self.app.session.get("base_url") or "https://ascendensasia-team.atlassian.net"
        issue_url = f"{base_url}/browse/{ticket['key']}"
        open_btn = tk.Label(
            header,
            text="Open in Jira ↗",
            bg="#18181f",
            fg="#d4d4d8",
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=4,
            cursor="hand2",
        )
        open_btn.pack(side="right", padx=8, pady=13)
        open_btn.bind("<Enter>", lambda e: open_btn.configure(bg="#24242e", fg="#ffffff"))
        open_btn.bind("<Leave>", lambda e: open_btn.configure(bg="#18181f", fg="#d4d4d8"))
        open_btn.bind("<Button-1>", lambda e, u=issue_url: webbrowser.open(u))

        tk.Frame(outer, bg="#1c1c22", height=1).pack(fill="x", padx=18, pady=(2, 6))

        for w in (header, key_badge, status_pill):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)

        # Scrollable Content Body
        body_container = tk.Frame(outer, bg="#09090b")
        body_container.pack(fill="both", expand=True, padx=18, pady=(4, 14))

        canvas = tk.Canvas(body_container, bg="#09090b", highlightthickness=0, bd=0, yscrollincrement=18)
        self.scroll_canvas = canvas
        content = tk.Frame(canvas, bg="#09090b")

        content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        c_win_id = canvas.create_window((0, 0), window=content, anchor="nw", width=self.W - 48)
        canvas.bind("<Configure>", lambda e, cid=c_win_id: canvas.itemconfigure(cid, width=max(100, e.width - 4)))

        canvas.pack(side="left", fill="both", expand=True)

        # 1. Task Title
        title_lbl = tk.Label(
            content,
            text=clean_ticket_summary(ticket),
            bg="#09090b",
            fg="#f4f4f6",
            font=("Segoe UI Semibold", 12),
            wraplength=self.W - 60,
            justify="left",
            anchor="w",
        )
        title_lbl.pack(fill="x", pady=(4, 16))

        # 2. Key Details Section
        tk.Label(
            content,
            text="KEY DETAILS",
            bg="#09090b",
            fg="#9696a2",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        kd_card = tk.Frame(content, bg="#121216", highlightbackground="#1e1e26", highlightthickness=1, padx=14, pady=10)
        kd_card.pack(fill="x", pady=(0, 16))

        details_rows = [
            ("Document ID", ticket.get("doc_id", "—"), ("Consolas", 9)),
            ("Assignee (Dev)", ticket.get("assignee", "—"), ("Segoe UI Semibold", 9)),
            ("IQA Officer", ticket.get("iqa_officer", "—"), ("Segoe UI Semibold", 9)),
            ("Team", ticket.get("team", "—"), ("Segoe UI Semibold", 9)),
            ("Consult To", ticket.get("consult_to", "—"), ("Segoe UI Semibold", 9)),
            ("Environment", ticket.get("environment", "None"), ("Segoe UI", 9)),
        ]
        kd_card.grid_columnconfigure(0, minsize=112)
        kd_card.grid_columnconfigure(1, weight=1)
        for row_index, (label_txt, val_txt, val_font) in enumerate(details_rows):
            tk.Label(
                kd_card, text=label_txt, bg="#121216", fg="#9696a2",
                font=("Segoe UI", 9), anchor="w",
            ).grid(row=row_index, column=0, sticky="nw", pady=6, padx=(0, 12))
            tk.Label(
                kd_card, text=val_txt, bg="#121216",
                fg="#e4e4e7" if val_txt not in ("—", "None") else "#71717a",
                font=(val_font[0], 10), anchor="w",
                wraplength=self.W - 192, justify="left",
            ).grid(row=row_index, column=1, sticky="ew", pady=6)

        # 3. Description Section
        tk.Label(
            content,
            text="DESCRIPTION",
            bg="#09090b",
            fg="#9696a2",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        desc_card = tk.Frame(content, bg="#121216", highlightbackground="#1e1e26", highlightthickness=1, padx=14, pady=12)
        desc_card.pack(fill="x", pady=(0, 16))

        tk.Label(
            desc_card,
            text=ticket.get("description", "No description provided."),
            bg="#121216",
            fg="#d4d4d8",
            font=("Segoe UI", 10),
            wraplength=self.W - 86,
            justify="left",
            anchor="w",
        ).pack(fill="x")

        # 4. Attachments Section
        atts = ticket.get("attachments", [])
        tk.Label(
            content,
            text=f"ATTACHMENTS  ({len(atts)})",
            bg="#09090b",
            fg="#9696a2",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        if not atts:
            tk.Label(
                content,
                text="No files attached",
                bg="#121216",
                fg="#52525b",
                font=("Segoe UI", 9),
                padx=14,
                pady=10,
                anchor="w",
            ).pack(fill="x", pady=(0, 10))
        else:
            for att in atts:
                self._create_attachment_row(content, att)

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

    def _create_attachment_row(self, parent, att: dict):
        att_card = tk.Frame(
            parent,
            bg="#121216",
            highlightbackground="#1e1e26",
            highlightthickness=1,
            padx=14,
            pady=10,
        )
        att_card.pack(fill="x", pady=4)

        top = tk.Frame(att_card, bg="#121216")
        top.pack(fill="x")

        fname_lbl = tk.Label(
            top,
            text=att["filename"],
            bg="#121216",
            fg="#f4f4f6",
            font=("Segoe UI Semibold", 10),
            anchor="w",
            wraplength=315,
            justify="left",
        )
        fname_lbl.pack(side="left", fill="x", expand=True)

        open_att_btn = tk.Label(
            top,
            text="Open ↗",
            bg="#1f1f27",
            fg="#e4e4e7",
            font=("Segoe UI", 8, "bold"),
            padx=10,
            pady=4,
            cursor="hand2",
        )
        open_att_btn.pack(side="right", padx=(8, 0))
        open_att_btn.bind("<Enter>", lambda e: open_att_btn.configure(bg="#2c2c38", fg="#ffffff"))
        open_att_btn.bind("<Leave>", lambda e: open_att_btn.configure(bg="#1f1f27", fg="#e4e4e7"))

        meta_txt = f"{att['size_str']}   ·   {att['created']}   ·   {att['author']}"
        tk.Label(
            att_card,
            text=meta_txt,
            bg="#121216",
            fg="#9696a2",
            font=("Segoe UI", 9),
            wraplength=self.W - 80,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(4, 0))

        mime = (att.get("mimeType") or "").lower()
        if mime.startswith("image/") and att.get("content_url"):
            preview_holder = tk.Label(att_card, bg="#121216", text="Loading preview…", fg="#52525b", font=("Segoe UI", 8))
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

        self.vx, self.vy, self.vw, self.vh = get_virtual_screen_bounds()
        primary_w = self.root.winfo_screenwidth()

        saved_x = self.load_saved_position()
        if saved_x is not None:
            self.win_x = self.clamp_x(saved_x)
        else:
            self.win_x = (primary_w - self.WIN_W) // 2
        self.win_y = 0

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

        self.task_list_widget = StatusTaskListWidget(self)
        self.detail_widget = TaskDetailWidget(self)
        self.space_modal = SpaceSwitcherModal(self)

        # Load permanently cached account credentials (persisted forever until token expires or user updates key)
        self.session = self.load_cached_account()

        self.progress = 0.0
        self.target_progress = 0.0
        self.pinned = False
        self.active_tab = "nook"
        self.show_token_update_ui = not self.session.get("connected", False)
        self.is_syncing = False
        self.request_generation = 0
        self.sync_results = queue.Queue()
        self.manual_sync_active = False
        self.last_sync_epoch = 0.0
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

        self.login_widgets_visible = False
        self.focused_login_field = None
        self.show_token_plain = False
        self.build_login_entries()

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)

        # Global pointer-aware mousewheel router so both Task List & Task Detail scroll anywhere inside their bounds
        self.root.bind_all("<MouseWheel>", self.on_global_mousewheel)

        self.menu = tk.Menu(self.root, tearoff=0, bg="#141418", fg="#f4f4f6", activebackground="#262630")
        self.menu.add_command(label="Refresh Jira Now", command=self.trigger_sync)
        self.menu.add_command(label="Open SM360 Board in Browser", command=self.open_board)
        self.menu.add_command(label="Toggle Pin Expanded", command=self.toggle_pin)
        self.menu.add_command(label="Update API Key / Account…", command=self.open_api_key_settings)
        self.menu.add_command(label="Sign Out (Clear Cached Account)", command=self.sign_out)
        self.menu.add_separator()
        self.menu.add_command(label="Snap to Center of Monitor 1", command=lambda: self.snap_to_monitor(0))
        self.menu.add_command(label="Snap to Center of Monitor 2", command=lambda: self.snap_to_monitor(1))
        self.menu.add_separator()
        self.menu.add_command(label="Quit Notch Widget", command=self.root.destroy)

        self.last_time = time.perf_counter()
        self.flash_until = time.perf_counter() + 2.2
        self.invalidate_cache()
        self.display_progress(0.0)
        self.prepare_animation_shapes()
        if self.session.get("connected"):
            self.trigger_sync()
        self.schedule_periodic_sync()
        self.tick()

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
            fg="#f4f4f6",
            insertbackground="#0a84ff",
            insertwidth=2,
            selectbackground="#264f78",
            selectforeground="#ffffff",
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
            ent.configure(bg="#1b1b22" if fn == field_name else "#15151a")
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
            self.ent_url.place(x=left + 16, y=97, width=460, height=22)
            self.ent_proj.place_forget()
            self.ent_email.place(x=left + 16, y=171, width=306, height=22)
            self.ent_token.place(x=left + 364, y=171, width=250, height=22)
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
            self.sync_results.put((generation, candidate, fresh, error, True))

        threading.Thread(target=worker, daemon=True).start()

    def summon_to_cursor_monitor(self):
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
            self.state_file.write_text(json.dumps({"win_x": self.win_x}), encoding="utf-8")
        except Exception:
            pass

    def snap_to_monitor(self, monitor_index: int):
        primary_w = self.root.winfo_screenwidth()
        target_cx = monitor_index * primary_w + primary_w // 2
        self.win_x = self.clamp_x(target_cx - self.WIN_W // 2)
        self.root.geometry(f"{self.WIN_W}x{self.WIN_H}+{self.win_x}+{self.win_y}")
        self.save_position()

    def on_double_click(self, event):
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
        steps = int(-1 * (event.delta / 120))
        if steps == 0:
            steps = -1 if event.delta > 0 else 1

        # Check SpaceSwitcherModal, TaskDetailWidget, and StatusTaskListWidget
        for panel in (self.space_modal, self.detail_widget, self.task_list_widget):
            w = panel.win
            c = panel.scroll_canvas
            if w is not None and c is not None and w.winfo_exists() and c.winfo_exists():
                wx, wy = panel.pos_x, panel.pos_y
                if wx <= px <= wx + panel.W and wy <= py <= wy + panel.H:
                    c.yview_scroll(steps, "units")
                    return

    def on_mouse_down(self, event):
        if self.account_transition is not None:
            return
        self.dragging = True
        self.drag_moved = False
        self.drag_start_mouse_x = self.root.winfo_pointerx()
        self.drag_start_win_x = self.win_x

    def on_mouse_drag(self, event):
        if not self.dragging:
            return
        cur_mouse_x = self.root.winfo_pointerx()
        dx = cur_mouse_x - self.drag_start_mouse_x
        if abs(dx) > 4:
            self.drag_moved = True
        if self.drag_moved:
            new_x = self.clamp_x(self.drag_start_win_x + dx)
            if new_x != self.win_x:
                self.win_x = new_x
                self.root.geometry(f"+{self.win_x}+{self.win_y}")

    def on_mouse_up(self, event):
        if self.account_transition is not None:
            self.dragging = False
            return
        was_drag = self.drag_moved
        self.dragging = False
        self.drag_moved = False
        if was_drag:
            self.save_position()
            return

        mx, my = event.x, event.y
        for x1, y1, x2, y2, cb in self.hit_boxes:
            if x1 <= mx <= x2 and y1 <= my <= y2:
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

    def trigger_sync(self, manual: bool = False):
        if not self.session.get("connected") or self.is_syncing:
            return
        self.is_syncing = True
        self.manual_sync_active = manual
        self.request_generation += 1
        generation = self.request_generation
        snapshot = dict(self.session)
        if manual:
            self.invalidate_cache()
            self.display_progress(self.progress)

        def worker():
            fresh, error = None, None
            try:
                fresh = fetch_jira_data(snapshot)
            except Exception as e:
                error = e
            self.sync_results.put((generation, snapshot, fresh, error, False))

        threading.Thread(target=worker, daemon=True).start()

    def drain_sync_results(self):
        """Apply worker results on the Tk thread, only for the current request."""
        while True:
            try:
                generation, snapshot, fresh, error, connecting = self.sync_results.get_nowait()
            except queue.Empty:
                break
            if generation != self.request_generation:
                continue
            self.is_syncing = False
            self.manual_sync_active = False
            if isinstance(error, JiraAuthExpiredError):
                self.session["connected"] = False
                self.show_token_update_ui = True
                self.login_status_msg = "API Token expired or invalid · Click 'Get New API Key' below"
                self.login_status_color = COLOR_RETURNED
            elif error is not None:
                if connecting:
                    self.login_status_msg = f"Connection error: {error}"
                    self.login_status_color = COLOR_RETURNED
                else:
                    self.data["error"] = str(error)
            else:
                if connecting:
                    self.session = snapshot
                    self.proj_var.set(snapshot.get("project", "AUTO"))
                    self.save_cached_account()
                    self.show_token_update_ui = True
                    self.login_status_msg = "Connected · Opening your dashboard…"
                    self.login_status_color = COLOR_DONE
                    self.task_list_widget.close()
                    self.detail_widget.close()
                    self.start_account_transition(show_login=False, hold_ms=350)
                self.session["effective_role"] = fresh.get("effective_role", "DEV")
                self.data = fresh
                self.last_sync_epoch = time.time()
            self._on_sync_done()

    def _on_sync_done(self):
        # Compute data signature so we ONLY clear the 25-frame render cache when Jira data actually changed!
        active_statuses = self.data.get("kanban_tiles", self.data.get("kanban_statuses", KANBAN_STATUSES))
        sig = json.dumps(
            {k: v for k, v in self.data.items() if k not in ("updated_at", "error")},
            sort_keys=True,
        )
        ui_sig = (
            self.show_token_update_ui, self.login_status_msg, self.login_status_color,
            self.manual_sync_active, self.data.get("error"), self.data.get("updated_at"),
        )
        ui_changed = ui_sig != getattr(self, "last_ui_signature", None)
        self.last_ui_signature = ui_sig
        data_changed = sig != self.last_data_signature
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

    def toggle_pin(self):
        self.pinned = not self.pinned
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
        inside = (x1 - pad <= px <= x2 + pad) and (0 <= py <= y2 + pad)

        focus_w = self.root.focus_get()
        typing_login = self.show_token_update_ui and (focus_w in (self.ent_url, self.ent_proj, self.ent_email, self.ent_token))
        space_modal_open = self.space_modal.is_open()
        flashing = time.perf_counter() < getattr(self, "flash_until", 0)
        new_target = 1.0 if (inside or self.pinned or flashing or typing_login or space_modal_open) else 0.0

        # Trigger an automatic background sync when the user hovers to expand if >10s since last sync
        if new_target == 1.0 and self.target_progress == 0.0:
            if self.session.get("connected") and not self.show_token_update_ui and (time.time() - self.last_sync_epoch > 10.0):
                self.trigger_sync(manual=False)

        self.target_progress = new_target

    def tick(self):
        frame_started = time.perf_counter()
        self.drain_animation_shapes()
        self.drain_sync_results()
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

        should_show_entries = self.show_token_update_ui and self.account_transition is None and (self.progress > 0.88)
        self.set_login_widgets_visibility(should_show_entries)

        moving = abs(self.target_progress - self.progress) > 0.001
        interval_ms = 1000 / 120 if moving else 24
        delay_ms = max(1, round(interval_ms - (time.perf_counter() - frame_started) * 1000))
        self.root.after(delay_ms, self.tick)

    def display_progress(self, t: float):
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
        final_img.paste(content, (0, 0), self.shape_masks[idx])
        frame = ImageTk.PhotoImage(final_img), boxes
        if 0.15 <= t <= 0.82:
            self.transition_cache[idx] = frame
        return frame

    def render_content_layer(self, t: float, draw_content: bool = True):
        S = 2
        W, H = self.WIN_W * S, self.WIN_H * S

        content_hi = Image.new("RGB", (W, H), NOTCH_BG)
        draw = ImageDraw.Draw(content_hi)

        _, _, _, _, nw, nh = self.get_box_for_progress(t)
        cx = W / 2
        nw_s = nw * S
        nh_s = nh * S

        # Subtle hardware drag pill at top center
        grip_w = 34 * S
        draw.rounded_rectangle(
            [cx - grip_w / 2, 5 * S, cx + grip_w / 2, 7.5 * S],
            radius=2 * S,
            fill=(42, 42, 52),
        )

        boxes = []
        if draw_content and t < 0.15:
            self.draw_collapsed_content(draw, cx, nw_s, nh_s, S)
        elif draw_content and t > 0.82:
            if self.show_token_update_ui:
                self.draw_login_interface(draw, cx, nw_s, nh_s, S, boxes)
            else:
                self.draw_expanded_content(draw, cx, nw_s, nh_s, S, boxes)

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
        dot_col = COLOR_ON_HOLD if self.manual_sync_active or self.data.get("error") else COLOR_DONE
        draw.ellipse([dot_x - dot_r, cy - dot_r, dot_x + dot_r, cy + dot_r], fill=dot_col)

        proj_label = f"{self.data['project']}   {self.data['total']}"
        draw.text((dot_x + 12 * S, cy), proj_label, font=self.f_xs_b, fill=TEXT_PRIMARY, anchor="lm")

        right_text = f"{self.data['pct']}%  ·  {self.data['active']} open"
        text_right_x = right - 22 * S
        draw.text((text_right_x, cy), right_text, font=self.f_xs, fill=TEXT_SECONDARY, anchor="rm")

        text_w = draw.textlength(right_text, font=self.f_xs)
        ring_r = 9.5 * S
        ring_cx = text_right_x - text_w - 14 * S - ring_r
        bbox = [ring_cx - ring_r, cy - ring_r, ring_cx + ring_r, cy + ring_r]
        draw.arc(bbox, start=0, end=360, fill=(38, 38, 46), width=3 * S)
        end_ang = -90 + int(3.6 * self.data["pct"])
        if self.data["pct"] > 0:
            draw.arc(bbox, start=-90, end=end_ang, fill=COLOR_DONE, width=3 * S)

    def draw_login_interface(self, draw: ImageDraw.ImageDraw, cx: float, nw_s: float, nh_s: float, S: int, boxes: list):
        left = cx - nw_s / 2 + 28 * S
        right = cx + nw_s / 2 - 28 * S
        top = 18 * S

        # Header Badge Pill
        p_x1, p_y1, p_x2, p_y2 = left, top, left + 168 * S, top + 30 * S
        draw.rounded_rectangle([p_x1, p_y1, p_x2, p_y2], radius=15 * S, fill=SURFACE_ELEVATED)
        dot_x = p_x1 + 18 * S
        dot_y = (p_y1 + p_y2) / 2
        draw.ellipse([dot_x - 4 * S, dot_y - 4 * S, dot_x + 4 * S, dot_y + 4 * S], fill=COLOR_ON_HOLD)
        draw.text((dot_x + 10 * S, dot_y), "Account & API Key", font=self.f_xs_b, fill=TEXT_PRIMARY, anchor="lm")

        draw.text((p_x2 + 14 * S, dot_y), self.login_status_msg, font=self.f_xxs, fill=self.login_status_color, anchor="lm")

        # Pin button
        pin_x1, pin_y1, pin_x2, pin_y2 = right - 30 * S, top, right, top + 30 * S
        pin_bg = COLOR_IN_PROGRESS if self.pinned else SURFACE_CARD
        draw.ellipse([pin_x1, pin_y1, pin_x2, pin_y2], fill=pin_bg)
        draw.ellipse([pin_x1 + 10 * S, pin_y1 + 10 * S, pin_x2 - 10 * S, pin_y2 - 10 * S], fill=TEXT_PRIMARY)
        boxes.append((pin_x1 / S, pin_y1 / S, pin_x2 / S, pin_y2 / S, self.toggle_pin))

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
                lambda ax=login_sp_anchor_x, ay=login_sp_anchor_y: self.open_space_switcher_menu(self.win_x + ax, self.win_y + ay),
            )
        )

        # Row 2 Capsules: Atlassian Account Email + API Token (y = 160..204)
        r2_y1, r2_y2 = 160 * S, 204 * S
        draw_ios_field_capsule(left, r2_y1, left + 336 * S, r2_y2, "email", "ATLASSIAN ACCOUNT EMAIL")
        draw_ios_field_capsule(left + 350 * S, r2_y1, right, r2_y2, "token", "API TOKEN (CACHED UNTIL EXPIRED)")

        # iOS-style inline "Show / Hide" toggle pill inside the right edge of the API Token capsule
        sh_x1, sh_y1, sh_x2, sh_y2 = right - 54 * S, r2_y1 + 8 * S, right - 8 * S, r2_y2 - 8 * S
        draw.rounded_rectangle([sh_x1, sh_y1, sh_x2, sh_y2], radius=8 * S, fill=(32, 32, 40))
        sh_label = "Hide" if self.show_token_plain else "Show"
        draw.text(((sh_x1 + sh_x2) / 2, (sh_y1 + sh_y2) / 2), sh_label, font=self.f_xxs_b, fill=TEXT_SECONDARY, anchor="mm")
        boxes.append((sh_x1 / S, sh_y1 / S, sh_x2 / S, sh_y2 / S, self.toggle_token_visibility))

        # Bottom Action Row (y = 226..268)
        btn_y1, btn_y2 = 226 * S, 268 * S

        tok_x1, tok_x2 = left, left + 185 * S
        draw.rounded_rectangle([tok_x1, btn_y1, tok_x2, btn_y2], radius=12 * S, fill=SURFACE_CARD, outline=(36, 36, 45), width=2)
        draw.text(((tok_x1 + tok_x2) / 2 - 6 * S, (btn_y1 + btn_y2) / 2), "Get New API Key", font=self.f_xs_b, fill=TEXT_SECONDARY, anchor="mm")
        # Crisp vector north-east external link arrow (replaces unsupported Unicode tofu box)
        ax, ay = tok_x2 - 22 * S, (btn_y1 + btn_y2) / 2
        draw.line([ax - 4 * S, ay + 4 * S, ax + 4 * S, ay - 4 * S], fill=TEXT_SECONDARY, width=3)
        draw.line([ax - 2 * S, ay - 4 * S, ax + 4 * S, ay - 4 * S], fill=TEXT_SECONDARY, width=3)
        draw.line([ax + 4 * S, ay - 4 * S, ax + 4 * S, ay + 2 * S], fill=TEXT_SECONDARY, width=3)
        boxes.append((tok_x1 / S, btn_y1 / S, tok_x2 / S, btn_y2 / S, lambda: webbrowser.open("https://id.atlassian.com/manage-profile/security/api-tokens")))

        if self.session.get("connected"):
            back_x1, back_x2 = tok_x2 + 12 * S, tok_x2 + 95 * S
            draw.rounded_rectangle([back_x1, btn_y1, back_x2, btn_y2], radius=12 * S, fill=SURFACE_CARD, outline=(36, 36, 45), width=2)
            draw.text(((back_x1 + back_x2) / 2, (btn_y1 + btn_y2) / 2), "Back", font=self.f_xs, fill=TEXT_MUTED, anchor="mm")
            boxes.append((back_x1 / S, btn_y1 / S, back_x2 / S, btn_y2 / S, self.cancel_api_key_settings))

            so_x1, so_x2 = back_x2 + 10 * S, back_x2 + 120 * S
            draw.rounded_rectangle([so_x1, btn_y1, so_x2, btn_y2], radius=12 * S, fill=SURFACE_CARD, outline=(36, 36, 45), width=2)
            draw.text(((so_x1 + so_x2) / 2, (btn_y1 + btn_y2) / 2), "Sign Out", font=self.f_xs_b, fill=COLOR_RETURNED, anchor="mm")
            boxes.append((so_x1 / S, btn_y1 / S, so_x2 / S, btn_y2 / S, self.sign_out))

        con_x1, con_x2 = right - 210 * S, right
        con_bg = SURFACE_ELEVATED if self.is_syncing else (244, 244, 246)
        con_fg = TEXT_SECONDARY if self.is_syncing else (9, 9, 11)
        draw.rounded_rectangle([con_x1, btn_y1, con_x2, btn_y2], radius=12 * S, fill=con_bg)
        con_label = "Saving…" if self.is_syncing else "Save & Connect"
        draw.text(((con_x1 + con_x2) / 2, (btn_y1 + btn_y2) / 2), con_label, font=self.f_xs_b, fill=con_fg, anchor="mm")
        boxes.append((con_x1 / S, btn_y1 / S, con_x2 / S, btn_y2 / S, self.connect_live))

    def draw_expanded_content(self, draw: ImageDraw.ImageDraw, cx: float, nw_s: float, nh_s: float, S: int, boxes: list):
        left = cx - nw_s / 2 + 26 * S
        right = cx + nw_s / 2 - 26 * S
        top = 18 * S

        # --- TOP BAR: Authentic macOS Alcove Nook / Active Pill Tabs ---
        t1_x1, t1_y1, t1_x2, t1_y2 = left, top, left + 90 * S, top + 28 * S
        t1_bg = SURFACE_ELEVATED if self.active_tab == "nook" else SURFACE_CARD
        t1_fg = TEXT_PRIMARY if self.active_tab == "nook" else TEXT_MUTED
        draw.rounded_rectangle([t1_x1, t1_y1, t1_x2, t1_y2], radius=14 * S, fill=t1_bg)
        dot_x = t1_x1 + 20 * S
        dot_y = (t1_y1 + t1_y2) / 2
        draw.ellipse([dot_x - 3.5 * S, dot_y - 3.5 * S, dot_x + 3.5 * S, dot_y + 3.5 * S], fill=COLOR_DONE if self.active_tab == "nook" else TEXT_MUTED)
        draw.text((dot_x + 10 * S, dot_y), "Nook", font=self.f_xs_b, fill=t1_fg, anchor="lm")
        boxes.append((t1_x1 / S, t1_y1 / S, t1_x2 / S, t1_y2 / S, lambda: self.switch_tab("nook")))

        t2_x1, t2_y1, t2_x2, t2_y2 = t1_x2 + 8 * S, top, t1_x2 + 114 * S, top + 28 * S
        t2_bg = SURFACE_ELEVATED if self.active_tab == "active" else SURFACE_CARD
        t2_fg = TEXT_PRIMARY if self.active_tab == "active" else TEXT_MUTED
        draw.rounded_rectangle([t2_x1, t2_y1, t2_x2, t2_y2], radius=14 * S, fill=t2_bg)
        draw.text(
            ((t2_x1 + t2_x2) / 2, (t2_y1 + t2_y2) / 2),
            f"Active ({self.data['active']})",
            font=self.f_xs_b,
            fill=t2_fg,
            anchor="mm",
        )
        boxes.append((t2_x1 / S, t2_y1 / S, t2_x2 / S, t2_y2 / S, lambda: self.switch_tab("active")))

        # Top-right Controls: Pin dot + Sign Out pill + API Key pill + Sync pill
        pin_x1, pin_y1, pin_x2, pin_y2 = right - 28 * S, top, right, top + 28 * S
        pin_bg = COLOR_IN_PROGRESS if self.pinned else SURFACE_CARD
        draw.ellipse([pin_x1, pin_y1, pin_x2, pin_y2], fill=pin_bg)
        draw.ellipse([pin_x1 + 9.5 * S, pin_y1 + 9.5 * S, pin_x2 - 9.5 * S, pin_y2 - 9.5 * S], fill=TEXT_PRIMARY if self.pinned else TEXT_SECONDARY)
        boxes.append((pin_x1 / S, pin_y1 / S, pin_x2 / S, pin_y2 / S, self.toggle_pin))

        out_x1, out_y1, out_x2, out_y2 = pin_x1 - 86 * S, top, pin_x1 - 8 * S, top + 28 * S
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
        ref_dot_col = COLOR_ON_HOLD if self.manual_sync_active or self.data.get("error") else COLOR_DONE
        draw.ellipse([ref_dot_x - 3 * S, ref_dot_y - 3 * S, ref_dot_x + 3 * S, ref_dot_y + 3 * S], fill=ref_dot_col)
        ref_label = "Syncing…" if self.manual_sync_active else ("Retry" if self.data.get("error") else "Auto-Sync")
        draw.text((ref_dot_x + 8 * S, ref_dot_y), ref_label, font=self.f_xxs_b, fill=TEXT_MUTED, anchor="lm")
        boxes.append((ref_x1 / S, ref_y1 / S, ref_x2 / S, ref_y2 / S, lambda: self.trigger_sync(manual=True)))

        user_name = self.session.get("display_name", "")
        if len(user_name) > 18:
            user_name = user_name[:17] + "…"
        draw.text((cx - 28 * S, top + 14 * S), user_name, font=self.f_xxs, fill=TEXT_MUTED, anchor="mm")

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

        draw.arc(bbox, start=0, end=360, fill=(26, 26, 32), width=ring_w)

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
        draw.line([div_x, content_top + 10 * S, div_x, content_top + 214 * S], fill=(28, 28, 34), width=2)

        # RIGHT COLUMN: Interactive Space Switcher Header + Role Badge + 3x3 Grid of Status Tiles
        rx = div_x + 20 * S
        proj_disp = self.data.get("project_display") or self.data.get("project", "SM360")
        if len(proj_disp) > 20:
            proj_disp = proj_disp[:19] + "…"
        board_label = proj_disp if proj_disp == "All Spaces" else f"{proj_disp} Board"

        # Clickable Space Switcher Pill (with custom vector chevron instead of unsupported Unicode ▾)
        lbl_w = draw.textlength(board_label, font=self.f_xs_b)
        sp_x1, sp_y1, sp_x2, sp_y2 = rx, content_top - 2 * S, rx + lbl_w + 34 * S, content_top + 22 * S
        draw.rounded_rectangle([sp_x1, sp_y1, sp_x2, sp_y2], radius=8 * S, fill=(20, 20, 25), outline=(36, 36, 46), width=2)
        draw.text((sp_x1 + 10 * S, (sp_y1 + sp_y2) / 2), board_label, font=self.f_xs_b, fill=TEXT_PRIMARY, anchor="lm")
        # Vector downward chevron (∨)
        chev_cx = sp_x2 - 13 * S
        chev_cy = (sp_y1 + sp_y2) / 2 + 1 * S
        draw.line([chev_cx - 4 * S, chev_cy - 2 * S, chev_cx, chev_cy + 2 * S], fill=TEXT_SECONDARY, width=2)
        draw.line([chev_cx, chev_cy + 2 * S, chev_cx + 4 * S, chev_cy - 2 * S], fill=TEXT_SECONDARY, width=2)
        anchor_sx = int(sp_x1 / S)
        anchor_sy = int(sp_y2 / S)
        boxes.append((sp_x1 / S, sp_y1 / S, sp_x2 / S, sp_y2 / S, lambda ax=anchor_sx, ay=anchor_sy: self.open_space_switcher_menu(self.win_x + ax, self.win_y + ay)))

        # Clickable Role Pill (Dev / IQA / All) right next to the Space Switcher pill
        eff_role = self.data.get("effective_role", "DEV")
        role_text = f"Role: {eff_role}"
        rw = draw.textlength(role_text, font=self.f_xxs_b)
        rl_x1, rl_y1, rl_x2, rl_y2 = sp_x2 + 8 * S, content_top - 2 * S, sp_x2 + rw + 26 * S, content_top + 22 * S
        role_accent = COLOR_APPROVAL if eff_role == "IQA" else (COLOR_IN_PROGRESS if eff_role == "DEV" else COLOR_DONE)
        draw.rounded_rectangle([rl_x1, rl_y1, rl_x2, rl_y2], radius=8 * S, fill=(20, 20, 25), outline=(36, 36, 46), width=2)
        draw.text(((rl_x1 + rl_x2) / 2, (rl_y1 + rl_y2) / 2), role_text, font=self.f_xxs_b, fill=role_accent, anchor="mm")
        boxes.append((rl_x1 / S, rl_y1 / S, rl_x2 / S, rl_y2 / S, self.cycle_role_mode))

        sync_label = "Sync failed" if self.data.get("error") else f"Synced {self.data['updated_at']}"
        draw.text((right, content_top + 10 * S), sync_label, font=self.f_xxs, fill=COLOR_ON_HOLD if self.data.get("error") else TEXT_MUTED, anchor="rm")

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
            draw.rounded_rectangle([cx1, cy1, cx2, cy2], radius=10 * S, fill=tile_bg, outline=(32, 32, 40) if val > 0 else (20, 20, 25), width=2)

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
                        st, lbl, col, origin_screen_pt=(self.win_x + ox, self.win_y + oy)
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
