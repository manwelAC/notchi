"""Portable Windows updates. Release metadata and archives come from our repository."""
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

APP_VERSION = "1.5.0"
RELEASE_BASE = "https://raw.githubusercontent.com/manwelAC/notchi/main/public/downloads/"
MAX_PACKAGE_BYTES = 150 * 1024 * 1024


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError("Invalid release version")
    return tuple(map(int, value.split(".")))


def check_release():
    request = urllib.request.Request(RELEASE_BASE + "release.json", headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read(16385))
    version_tuple(data.get("version"))
    if not re.fullmatch(r"Notchi-[0-9.]+-Windows-x64\.zip", str(data.get("file", ""))):
        raise ValueError("Invalid release filename")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", str(data.get("sha256", ""))):
        raise ValueError("Release checksum is missing")
    size = data.get("bytes")
    if type(size) is not int or not 0 < size <= MAX_PACKAGE_BYTES:
        raise ValueError("Invalid release size")
    return data if version_tuple(data["version"]) > version_tuple(APP_VERSION) else None


def download_release(release):
    stage = Path(tempfile.mkdtemp(prefix="Notchi-update-"))
    try:
        archive = stage / "release.zip"
        digest = hashlib.sha256()
        size = 0
        with urllib.request.urlopen(RELEASE_BASE + release["file"], timeout=30) as response, archive.open("wb") as output:
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > release["bytes"]:
                    raise ValueError("Download exceeds expected size")
                digest.update(chunk)
                output.write(chunk)
        if size != release["bytes"] or digest.hexdigest().lower() != release["sha256"].lower():
            raise ValueError("Download verification failed. Please try again.")
        with zipfile.ZipFile(archive) as package:
            entries = [entry for entry in package.infolist() if entry.filename == "Notchi.exe"]
            if len(entries) != 1 or not 0 < entries[0].file_size <= MAX_PACKAGE_BYTES:
                raise ValueError("Release must contain one Notchi.exe")
            with package.open(entries[0]) as source, (stage / "Notchi.exe").open("wb") as target:
                shutil.copyfileobj(source, target)
        with (stage / "Notchi.exe").open("rb") as executable:
            if executable.read(2) != b"MZ":
                raise ValueError("Release is not a Windows executable")
        return stage
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def launch_installer(stage, executable, parent_pid):
    """A detached helper waits for PyInstaller's file lock, replaces, then restarts."""
    stage, executable = Path(stage).resolve(), Path(executable).resolve()
    def literal(value):
        return "'" + str(value).replace("'", "''") + "'"
    script = stage / "install.ps1"
    script.write_text(r"""$ErrorActionPreference = 'Stop'
$target = TARGET
$source = SOURCE
$backup = $target + '.update-backup'
$log = Join-Path $env:LOCALAPPDATA 'Notchi\update-error.txt'
try {
    Wait-Process -Id PARENT -ErrorAction SilentlyContinue
    $installed = $false
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            [System.IO.File]::Replace($source, $target, $backup, $true)
            $installed = $true
            break
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $installed) { throw 'Could not replace Notchi.exe. Check folder write permissions and try again.' }
    try {
        Start-Process -FilePath $target -WorkingDirectory ([System.IO.Path]::GetDirectoryName($target))
    } catch {
        [System.IO.File]::Copy($backup, $target, $true)
        Start-Process -FilePath $target
        throw
    }
    Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $log -Force -ErrorAction SilentlyContinue
} catch {
    New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
    $_.ToString() | Set-Content -LiteralPath $log
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show('Notchi could not finish updating. Your preferences are safe. Details: ' + $log, 'Notchi update') | Out-Null
}
""".replace("TARGET", literal(executable)).replace("SOURCE", literal(stage / "Notchi.exe")).replace("PARENT", str(int(parent_pid))), encoding="utf-8-sig")
    subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-File", str(script)],
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                     close_fds=True)
