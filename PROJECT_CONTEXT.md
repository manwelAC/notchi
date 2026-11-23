# Notchi — Complete Project Handover & Architecture Context

> **Purpose of this document:** This file contains the complete technical context, directory locations, architecture, data flow, Jira Cloud API schema, UI rendering invariants, and build/release pipeline for **Notchi** so that ChatGPT (or any AI coding assistant / developer) can immediately understand and continue working on the project without losing context.

---

## 1. Project Folder Locations

Notchi consists of two components on this Windows machine:

1. **Desktop Widget Source & PyInstaller Build Folder (Primary Python Workspace):**
   - **Path:** `C:\Users\micro\projects\jira-task-counter`
   - **Mirror inside Website Repo:** `C:\Users\micro\projects\notchi\desktop-widget`
   - **Main Source File:** `notch_widget.py` (~2,950 lines, self-contained single-file Python desktop application)
   - **App Icon:** `jira_notch_v2.ico` (multi-size Windows `.ico`)
   - **PyInstaller Spec:** `Notchi.spec`
   - **Compiled Standalone Binary:** `dist\Notchi.exe`
   - **Packaged ZipStaging Folder:** `dist\Notchi-Package\` (`Notchi.exe` + `README.txt`)

2. **Marketing, Changelog & Download Website (Next.js 15 + Tailwind CSS v4):**
   - **Path:** `C:\Users\micro\projects\notchi`
   - **GitHub Remote:** `https://github.com/manwelAC/notchi.git` (branch: `main`)
   - **Main Landing Page & Changelog:** `src\app\page.tsx`
   - **Downloadable Release Archive:** `public\downloads\Notchi-Windows-x64.zip`
   - **Demo Videos:**
     - `public\demo\notchi-demo.mp4` (Main 60fps desktop capture)
     - `public\demo\notchi-demo.gif` (GitHub README animated preview)
     - `public\demo\how-to-login.mp4` (How to Login tutorial video)

3. **Per-User Runtime & Local Account Cache (Never Bundled in `.exe` or `.zip`):**
   - **Path:** `%LOCALAPPDATA%\Notchi\` (`C:\Users\<username>\AppData\Local\Notchi\`)
   - **`account_cache.json`**: Stores the user's `base_url`, `email`, base64-encoded `token_b64`, selected `project` (`"AUTO"`, `"ALL"`, or a space key like `"SM360"`, `"AIRI"`, `"HRIS"`), `role_mode` (`"AUTO"`, `"DEV"`, `"IQA"`, `"ALL"`), `manual_space_locked`, `display_name`, and `initials`.
   - **`widget_state.json`**: Stores `{"win_x": <int>}` so the notch remembers its horizontal position across multiple monitors on restart.

---

## 2. High-Level Product Overview

**Notchi** is a native Windows 10/11 top-bezel hardware notch utility (inspired by macOS Alcove / Dynamic Island) built for **Ascendens Asia (`https://ascendensasia-team.atlassian.net`)** and any Jira Cloud workspace.

- **Collapsed State (`340 × 44 px`):** Sits flush against the top-center bezel (`y = 0`) of the user's monitor, displaying a status dot, active Space code + total tasks, completion percentage, open task count, and a mini circular progress ring.
- **Expanded State (`732 × 304 px`):** Smoothly expands at 120Hz when the mouse cursor hovers into the notch bounds (or when pinned / typing in login fields / opening the Space Switcher modal).
- **Views inside the Notch:**
  1. **Login / Account & API Key Setup View (`draw_login_interface`):** Shown on first launch, after clicking `API Key`, after clicking `Sign Out`, or automatically if Jira returns `HTTP 401/403` (`JiraAuthExpiredError`).
  2. **Nook Tab (`draw_nook_overview`):** Left side shows a large circular multi-segment macOS-style activity ring (`% done`, `X of Y done`). Right side shows the clickable **Space Switcher Pill (`<Space> Board ∨`)**, clickable **Role Switcher Pill (`Role: DEV / IQA / ALL`)**, last synced timestamp, and a **3×3 grid of Kanban status cards**.
  3. **Active Tab (`draw_active_tickets_tab`):** Lists up to 5 currently active/unresolved tasks for rapid 1-click inspection.
- **Companion Floating Windows (`tk.Toplevel` with Windows 11 DWM rounded corners `DWMWCP_ROUND` and 120Hz bubble spring animations):**
  1. **`SpaceSwitcherModal` (`280 × 356 px`):** Custom dark popover modal with live search filter input, `Auto-Detect My Space`, `All My Spaces`, `YOUR ACTIVE SPACES` (with task count pills), and `ALL WORKSPACE SPACES` (all 24 company spaces). Works both on the Login screen and inside the Nook view.
  2. **`StatusTaskListWidget` (`420 × 540 px`):** Blooms open when clicking any Kanban status card in the 3×3 grid. Lists every ticket in that status with Issue Key, FRD Document ID badge, attachment count badge, and summary.
  3. **`TaskDetailWidget` (`520 × 620 px`):** Blooms open beside the task list when clicking any ticket card. Displays full summary, **Key Details** (`Document ID`, `Assignee (Dev)`, `IQA Officer`, `Team`, `Consult To`, `Environment`), full parsed **Atlassian Document Format (ADF) Description**, and **Attachments** (with inline async image thumbnail previews and 1-click download & open via `os.startfile`).

---

## 3. Core Architecture & End-to-End Flow (`notch_widget.py`)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         NotchDesktopWidget (tk.Tk)                           │
│  • Borderless topmost window (800×328), color-keyed with #010203             │
│  • 120Hz tick() loop interpolates progress (0.0 = collapsed, 1.0 = expanded) │
│  • 25 quantized spring frames cached in self.frame_cache                     │
└───────────────┬──────────────────────────────────────────────┬───────────────┘
                │                                              │
                ▼                                              ▼
┌─────────────────────────────────────────┐  ┌─────────────────────────────────┐
│     Jira Cloud REST API v3 Engine       │  │  Companion DWM Floating Panels  │
│  • fetch_jira_data(session)             │  │  • SpaceSwitcherModal           │
│  • Queries Dev (assignee) & IQA         │  │  • StatusTaskListWidget         │
│    (cf[10179] / watcher) & Reporter     │  │  • TaskDetailWidget             │
│  • Auto-discovers user's active Spaces  │  │  • Routed via unified global    │
│  • Dynamically builds 3×3 Kanban grid   │  │    on_global_mousewheel()       │
└─────────────────────────────────────────┘  └─────────────────────────────────┘
```

### 3.1. 2× Supersampled Rendering & Binary Silhouette Masking (`build_photo_image`)
- **Why:** Windows `wm_attributes("-transparentcolor", "#010203")` performs hard 1-bit color-key transparency. If anti-aliased text or shapes are drawn over a color-key background, subpixels blend with `#010203` and allow the desktop wallpaper to bleed through letters.
- **How Notchi solves it:**
  1. All interior notch graphics, cards, rings, and typography are drawn onto a solid `NOTCH_BG` (`#09090b`) RGB canvas at **2× resolution (`1600 × 656`)** and downsampled to `800 × 328` using `Image.Resampling.LANCZOS`.
  2. A separate grayscale silhouette mask (`draw_notch_mask`) draws the top-bezel notch shape—including the outward concave top corner ears (`ear_r`) and rounded bottom corners (`bot_r`)—and thresholds it to a strict binary mask (`0` outside, `255` inside).
  3. The Lanczos-downsampled interior canvas is composited onto a `TRANSPARENT_RGB` (`#010203`) background using the binary mask. Result: razor-sharp anti-aliased interior UI with zero wallpaper bleed-through.
- **25-Frame Cache (`self.frame_cache`):**
  - `self.progress` (`0.0` to `1.0`) is quantized into `NUM_STEPS = 25` discrete steps.
  - Each step is rendered once and cached as `(ImageTk.PhotoImage, hit_boxes)`.
  - Hover animations run at 120Hz (`self.root.after(8, self.tick)`) by swapping pre-rendered `PhotoImage` frames with zero per-frame Pillow drawing overhead.
  - `self.invalidate_cache()` is called **only** when data or UI state actually changes.

### 3.2. Zero-CPU Delta Auto-Sync (`trigger_sync` & `_on_sync_done`)
- Notchi syncs automatically:
  1. Every **30 seconds** in the background (`schedule_periodic_sync`).
  2. Whenever the user **hovers to expand** the notch if >10 seconds have elapsed since the last sync (`check_pointer_hover`).
  3. Immediately when the user clicks **`● Auto-Sync`**, switches Space, or cycles Role.
- **Delta Signature Check (`self.last_data_signature`):**
  - When a background sync thread finishes, `_on_sync_done()` hashes the active project, effective role, status counts, and issue keys/summaries/attachments into a JSON signature string.
  - If `sig == self.last_data_signature`, `self.frame_cache` is **not** cleared—preventing any UI flicker or CPU spike during 30-second background polls.

### 3.3. Dynamic Multi-Space & Role (`DEV` / `IQA` / `Reporter`) Jira Engine (`fetch_jira_data`)
Employees at Ascendens Asia belong to different roles (**Developers**, **IQA Officers**, **PMs/Reporters**) and work across **24 different Jira Spaces** (`SM360`, `AIRI` [`AAIRI`], `HRIS`, `IPS` [`Inventory and Procurement`], `SDA` [`SDA x SM360`], `LIM` [`LIMS`], `LMS`, `RMS`, `CUSP`, `AMS`, `PAR` [`PartnerPay`], `PUB` [`Publication`], `SP` [`Student Portal`], `OPH` [`Ordinansa`], `OPS`, `ACD`, `AD`, `AAD`, `PD`, `TEAM`, `REA`, `JL2025`, `DZ2025`, `GTMS`).

How `fetch_jira_data(session)` handles every user dynamically:
1. **Workspace Project Discovery (`get_workspace_projects`):**
   - Calls `GET /rest/api/3/project` and caches `{project_key: project_name}` in `WORKSPACE_PROJECTS_CACHE`.
   - `DEFAULT_WORKSPACE_SPACES` provides all 24 spaces offline before the user even logs in.
2. **Dual/Triple Role Queries (`_run_jql_query` via `POST /rest/api/3/search/jql`):**
   - **Developer Query (`dev_issues`):** `assignee = currentUser() ORDER BY updated DESC`
   - **IQA Officer Query (`iqa_issues`):** `(cf[10179] = currentUser() OR watcher = currentUser()) AND (assignee != currentUser() OR assignee is EMPTY) ORDER BY updated DESC` (where `customfield_10179` is the workspace's `IQA Officer` field). Falls back to `watcher = currentUser()` if `cf[10179]` is restricted.
   - **Reporter Fallback:** If a user has `0` Dev tasks and `0` IQA tasks (e.g., a Project Manager or Reporter), automatically queries `reporter = currentUser() ORDER BY updated DESC`.
3. **Smart Space Auto-Selection:**
   - Computes `all_space_counts` across the union of `dev_issues + iqa_issues`.
   - If the user selected **`Auto-Detect` (`AUTO`)** (or left a default space where they have `0` tasks and `manual_space_locked` is False), Notchi automatically selects the Space where the user has the most tasks (`all_space_counts.most_common(1)[0][0]`).
4. **Smart Role Auto-Detection (`DEV` vs `IQA` vs `ALL`):**
   - In `AUTO` role mode, Notchi compares the user's `IQA` task count vs `DEV` task count inside the active space (`i_cnt > d_cnt`).
   - This ensures hybrid IQA Officers (such as `Christine Torzar`, who has 50+ IQA tasks and 1 Dev task) are accurately placed in **`Role: IQA`** rather than `DEV`.
   - Additionally, if a user manually switches to a Space where they have `0` tasks under their current role but `>0` tasks under their other role (e.g., `DEV` in `SM360` and `IQA` in `HRIS`), Notchi automatically shows their tasks from that other role and flips the `Role` badge accordingly.
5. **Dynamic 3×3 Kanban Workflow Grid (`build_dynamic_kanban_statuses`):**
   - Fetches the selected Space's official statuses via `GET /rest/api/3/project/{project_key}/statuses` (`get_project_workflow_statuses`).
   - Maps statuses through `STATUS_STYLE_CATALOG` (which covers `SM360`'s 9 canonical columns as well as `For QA`, `IQA In Progress`, `In Progress (Devs)`, `Returned with Findings`, `Drafting`, `Delivery`, `Ready for Launch`, `Production`, `Accomplished`, etc.) and sorts them in logical Kanban progression order into up to 9 status tiles.

### 3.4. Custom Jira Fields Extracted per Ticket
Inside `fetch_jira_data`, every issue extracts:
- `customfield_10278` → **Document ID** (FRD Document ID, e.g., `SM360-FRD-042`)
- `customfield_10179` → **IQA Officer** (`displayName`)
- `customfield_10001` → **Team** (`name` / `title`)
- `customfield_10311` → **Consult To** (array of user/option objects)
- `assignee` → **Assignee (Dev)** (`displayName`)
- `description` & `environment` → Parsed from **Atlassian Document Format (ADF)** JSON trees into readable structured plain text via `parse_adf_to_text(node)`.
- `attachment` → List of attachment metadata dicts (`id`, `filename`, `size`, `size_str`, `mimeType`, `content_url`, `author`, `created`). Authenticated bytes are streamed on demand via `download_jira_bytes(url, email, token)`.

---

## 4. Critical UI & Windows 11 Engineering Rules (Must Preserve)

If modifying `notch_widget.py`, always preserve these rules:

1. **Never Use Unsupported Unicode Symbols in Pillow `ImageDraw.text`:**
   - Windows `segoeuib.ttf` (`Segoe UI Bold`) in Pillow does **not** contain glyphs like `↻`, `⇄`, `↗`, or `▾`—they render as ugly `□` tofu rectangles!
   - Always draw icons/arrows/chevrons using crisp vector lines (`draw.line(...)`), as done for the `Get New API Key` north-east arrow and the `Space Switcher` downward chevron (`∨`).
2. **Global Pointer-Coordinate MouseWheel Routing (`on_global_mousewheel`):**
   - All floating `tk.Toplevel` windows (`SpaceSwitcherModal`, `StatusTaskListWidget`, `TaskDetailWidget`) expose `.win`, `.scroll_canvas`, `.pos_x`, `.pos_y`, `.W`, `.H`.
   - Never bind `<MouseWheel>` inside `<Enter>/<Leave>` handlers (moving over child `tk.Frame`/`tk.Label` widgets fires spurious `<Leave>` events on Windows). Instead, `self.root.bind_all("<MouseWheel>", self.on_global_mousewheel)` checks the cursor's screen coordinates `(px, py)` against each open floating panel.
3. **Single-Instance Localhost IPC (`SINGLE_INSTANCE_PORT = 47831`):**
   - `acquire_single_instance_socket()` binds `127.0.0.1:47831`. If a second instance of `Notchi.exe` is launched, it sends `b"SUMMON"` to the running instance (which smoothly summons the notch to the cursor's current monitor via `summon_to_cursor_monitor()`) and exits cleanly.
4. **Multi-Monitor Virtual Screen Dragging (`SM_XVIRTUALSCREEN`):**
   - `get_virtual_screen_bounds()` reads Win32 metrics `76, 77, 78, 79` (`SM_XVIRTUALSCREEN`, `SM_YVIRTUALSCREEN`, `SM_CXVIRTUALSCREEN`, `SM_CYVIRTUALSCREEN`) so the user can drag the notch across negative or positive X coordinates on dual/triple monitor setups.

---

## 5. How to Build, Package & Release a New Version

Whenever `notch_widget.py` is updated, follow this exact 4-step pipeline to build `Notchi.exe`, package `Notchi-Windows-x64.zip`, update the Next.js website, and push to GitHub:

### Step 1: Verify Syntax & Compile `Notchi.exe` with PyInstaller
> **Important:** PyInstaller `--onefile` spawns two processes (bootloader + child). Always kill existing `Notchi.exe` processes with `/T` (tree kill) before compiling.

```powershell
python -m py_compile "C:\Users\micro\projects\jira-task-counter\notch_widget.py"
taskkill /F /IM Notchi.exe /T 2>$null
taskkill /F /IM pythonw.exe /T 2>$null
Start-Sleep -Seconds 1

Set-Location "C:\Users\micro\projects\jira-task-counter"
python -m PyInstaller --noconfirm --clean --onefile --noconsole --name "Notchi" --icon "C:\Users\micro\projects\jira-task-counter\jira_notch_v2.ico" "C:\Users\micro\projects\jira-task-counter\notch_widget.py"
```

### Step 2: Bundle `Notchi-Windows-x64.zip` & Compute SHA-256 Checksum
```powershell
$pkgDir = "C:\Users\micro\projects\jira-task-counter\dist\Notchi-Package"
New-Item -ItemType Directory -Force -Path $pkgDir | Out-Null
Copy-Item -Force "C:\Users\micro\projects\jira-task-counter\dist\Notchi.exe" "$pkgDir\Notchi.exe"

$zipDest = "C:\Users\micro\projects\notchi\public\downloads\Notchi-Windows-x64.zip"
if (Test-Path $zipDest) { Remove-Item -Force $zipDest }
Compress-Archive -Path "$pkgDir\*" -DestinationPath $zipDest -Force

(Get-FileHash -Path $zipDest -Algorithm SHA256).Hash
```

### Step 3: Update Website `SHA256_HASH` & `#versions` Changelog (`C:\Users\micro\projects\notchi\src\app\page.tsx`)
1. Update `const SHA256_HASH = "<NEW_HASH>";` at the top of `C:\Users\micro\projects\notchi\src\app\page.tsx`.
2. Add or update the version entry in the **Versions (`#versions`)** section and bump the header/download version badge in `src\app\page.tsx`.
3. Also copy the updated `notch_widget.py` into `C:\Users\micro\projects\notchi\desktop-widget\notch_widget.py` to keep the repo mirror in sync.

### Step 4: Commit & Push to GitHub (Triggers Vercel Deployment)
```powershell
Set-Location "C:\Users\micro\projects\notchi"
git add public/downloads/Notchi-Windows-x64.zip src/app/page.tsx
git commit -m "feat: release Notchi vX.Y.Z with <summary of changes>"
git push origin main
```
