# Notchi

A Jira desktop notch for Windows 10/11 x64.

## Latest release: 1.4.0 — 24 November 2026

- Cached rendering and silhouette masks reduce repeated drawing during animations.
- Saved dashboard snapshots display while Jira refreshes; role searches run in parallel and full task details load on demand.
- Refresh timeouts, automatic retry backoff, and an accessible error log.
- Twelve colorways with light/dark modes, gradient notch backgrounds, and adaptive text. Graphite Dark remains the original default.
- Optional **Side docking** toggle: enable it, then drag to the left, right, or top edge. Disable it to return to the top.
- Borderless Settings and task panels, traffic-light controls, custom status dropdowns, and button feedback.
- Save status changes directly to Jira using the transitions and required fields allowed by its workflow.

## Video

[Watch the v1.4.0 walkthrough](public/demo/notchi-v1.4.0.mp4)

## Download

[Notchi 1.4.0 for Windows x64](public/downloads/Notchi-1.4.0-Windows-x64.zip)

Quit Notchi before replacing the executable. Extract the archive and run `Notchi.exe`.
Local preferences remain in `%LOCALAPPDATA%\Notchi`. This release has no automatic updater.
Package size and SHA-256 are recorded in `public/downloads/release.json` and displayed on the website.

## Website

Run `npm run dev` for local development, or `npm run build` followed by `npm start` for production.
The homepage and newest-first collapsible `/versions` index share release metadata in `src/lib/release.ts`.
