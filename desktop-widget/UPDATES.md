# Portable updates (1.5.0)

Settings now includes **Check for updates**. When a newer release exists, the
button becomes **Update and restart**. Downloads run in the background, verify
the archive size and SHA-256, and extract only `Notchi.exe`. A hidden PowerShell
helper waits for the current process and PyInstaller file lock to close, replaces
the executable atomically, and restarts it. Account and appearance files stay in
`%LOCALAPPDATA%\Notchi`.

The app must be in a writable folder. Installation errors are shown in a Windows
dialog and recorded in `%LOCALAPPDATA%\Notchi\update-error.txt`. The old executable
is retained until restart is launched and restored if launching fails. This does
not detect crashes after the new process starts. Update staging files are in the
Windows temporary folder. PowerShell must be available and permitted to run.

## Publishing the first updater release

Existing 1.4.0 installations need one manual replacement to receive this feature.
The first updater release identifies itself as 1.5.0. The website and release
manifest must identify the same version as the packaged executable.

1. Build from `C:\Users\micro\projects\jira-task-counter\Notchi.spec`. Keep
   `notchi_updater.py` beside `notch_widget.py`; PyInstaller includes the import.
2. Package `Notchi.exe` at the ZIP root. Use an immutable versioned filename,
   such as `Notchi-1.5.0-Windows-x64.zip`.
3. Put the archive in `public/downloads`, then update `release.json` with its
   `version`, `date`, `file`, exact `bytes`, and `sha256`. Publish the archive and
   metadata together. Keep `src/lib/release.ts`, the changelog and README aligned.
4. The client checks the public repository's `main/public/downloads/release.json`
   through HTTPS on raw.githubusercontent.com and downloads from that same folder.
   It never uses Jira credentials for update requests. SHA-256 detects corruption;
   it is not a publisher signature. Repository access controls remain the trust
   boundary for both metadata and binaries.
5. For each later release, bump `APP_VERSION` in `notchi_updater.py` before
   compiling. Validate the published manifest and archive, then test an actual
   upgrade from the preceding packaged version before announcing it.

Run focused checks in the primary desktop folder:

```powershell
python -m unittest test_notchi_updater test_update_ui -v
```

These use synthetic packages and isolated preferences. The Windows helper test
executes real file replacement, while suppressing executable launch. The UI test
covers offline errors, retries, current/newer versions, closing and reopening
Settings during a check, and the development-source installation guard.
