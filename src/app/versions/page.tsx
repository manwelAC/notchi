import type { Metadata } from "next";
import Link from "next/link";
import { RELEASE } from "@/lib/release";
import { ChevronDown, Download, GitCommitHorizontal } from "lucide-react";

export const metadata: Metadata = {
  title: "Versions — Notchi",
  description: "Explore Notchi releases, new features, and improvements for Windows, from newest to oldest.",
};

const releases = [
  {
    version: RELEASE.version,
    title: "Updates from inside Notchi",
    description: "Check for new versions and update without manually replacing the app. Released 27 November 2026.",
    changes: [
      ["Check for updates", "Open Settings to check for a newer release. When one is available, choose Update and restart."],
      ["Verified downloads & restart", "Notchi checks the download size and SHA-256 before replacing its executable and restarting. Downloads run in the background."],
      ["Keep your preferences", "Your saved account, appearance, and dashboard cache stay in the local Notchi folder."],
      ["One final manual upgrade", "If you are using 1.4.0 or earlier, quit Notchi and replace Notchi.exe with this release to receive the update button. Future releases can use the button. Keep Notchi in a writable folder; Windows PowerShell is required."],
    ],
  },
  {
    version: "1.4.0",
    title: "Performance, colorways & side docking",
    description: "Less repeated drawing, a cached dashboard, and a notch that fits your desktop. Released 24 November 2026.",
    changes: [
      ["Animation optimizations", "Reuse animation frames, content layers, and silhouette masks instead of repeatedly drawing text and cards during movement. Button feedback and panel animations avoid rebuilding layouts on every frame."],
      ["Cached dashboard & lighter syncing", "Restore a saved dashboard for the selected account and view while refreshing Jira in the background. Developer and IQA searches run in parallel; full ticket details load on demand. Successful refreshes replace the snapshot, and failed requests keep the last successful data."],
      ["Refresh recovery", "Bound refresh waits, clear stale error indicators when retrying, and back off automatic retries after failures. Use View Last Sync Error from the context menu for diagnostics."],
      ["12 colorways, light & dark", "Graphite plus iOS-inspired Blue, Indigo, Purple, Pink, Red, Orange, Yellow, Green, Mint, Teal, and Cyan. Color themes add gradient notch backgrounds and matching controls, with dark text in light mode and light text in dark mode. Graphite Dark retains the original near-black default."],
      ["Optional drag-to-edge side docking", "Turn on Side docking in Settings, then drag the notch to the left, right, or top edge. Side mode uses a vertical tab that expands inward into the horizontal dashboard. Turning the option off restores top placement. The preference is saved locally."],
      ["Redesigned Settings & task panels", "A borderless Settings panel shares the task inspector’s styling, draggable header, traffic-light controls, and scrolling without a visible scrollbar. Refined typography, custom dropdowns, and button feedback carry through the task windows."],
      ["Update task status inside Notchi", "Load the transitions allowed by the task’s Jira workflow, complete required fields when prompted, and save directly to Jira. The dashboard refreshes after the change."],
      ["Updating this release", "Quit the running app, extract the new archive, and replace the previous Notchi.exe. Existing account and appearance preferences remain in the local Notchi folder. An automatic updater is not included."],
    ],
  },
  {
    version: "1.3.0",
    title: "Multi-space Kanban & role detection",
    description: "Your spaces, roles, and workflows. Together in the notch.",
    changes: [
      ["Custom space switcher", "A DWM-rounded popover replaces the native dropdown, with a spring animation, live search across all 24 workspace spaces, active task counts, and vector chevrons."],
      ["Automatic Dev & IQA detection", "Queries developer assignments and IQA Officer tasks through the IQA Officer field and watchers. Switch between DEV, IQA, and ALL from the role pill."],
      ["Space selection at login", "Choose Auto-Detect My Space, All My Spaces, or a workspace board from the Kanban Space dropdown on the login screen and in Nook."],
      ["Adaptive Kanban grid", "The 3×3 status grid adapts to each space’s workflow, including non-SM360 boards, while keeping the familiar SM360 layout."],
    ],
  },
  {
    version: "1.2.0",
    title: "Account setup & automatic syncing",
    description: "Refined login controls and background updates.",
    changes: [
      ["Login capsules", "Borderless rounded inputs with a blue focus ring and an inline Show / Hide API token toggle."],
      ["Delta auto-sync", "Background updates every 30 seconds, plus a refresh when expanding the notch, with cached rendering when ticket data is unchanged."],
      ["Sign out", "A dedicated Sign Out button clears the cached account from the device."],
    ],
  },
  {
    version: "1.1.0",
    title: "Task inspector & companion panels",
    description: "A closer look at your tickets without leaving your desktop.",
    changes: [
      ["Bubble panels", "Spring animations bring the floating Status Task List and Task Detail Inspector into view."],
      ["Full ticket inspection", "Read parsed Atlassian Document Format descriptions and custom fields including Document ID, IQA Officer, and Team."],
      ["Pointer-aware scrolling", "Mousewheel input follows the pointer across floating panels."],
    ],
  },
  {
    version: "1.0.0",
    title: "The first Notchi",
    description: "A top-bezel Jira companion for Windows.",
    changes: [
      ["Hardware notch engine", "2× Lanczos supersampling, outward concave top corners, and a binary silhouette mask keep the notch crisp without wallpaper color bleed."],
      ["Multi-monitor movement", "Drag across dual and triple monitors, including negative screen coordinates, and double-click to center the notch."],
      ["Local account cache", "Account settings persist in %LOCALAPPDATA%\\Notchi for subsequent launches."],
    ],
  },
];

export default function VersionsPage() {
  return (
    <div className="flex min-h-screen flex-col bg-[#070709] text-[#f4f4f6]">
      <header className="sticky top-0 z-50 border-b border-white/[0.07] bg-[#070709]/85 backdrop-blur-md">
        <div className="mx-auto flex min-h-16 max-w-[1240px] flex-wrap items-center justify-between gap-4 px-6 py-3">
          <Link href="/" aria-label="Notchi home" className="flex items-center gap-3.5 rounded-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white">
            <img src="/notchi-icon.png" alt="" width={32} height={32} className="rounded-lg border border-white/10" />
            <span className="text-[15px] font-semibold tracking-tight">Notchi</span>
            <span className="hidden rounded border border-white/[0.07] bg-white/[0.05] px-2 py-0.5 font-mono text-[11px] text-[#a1a1aa] sm:inline">v{RELEASE.version} · Win x64</span>
          </Link>
          <nav aria-label="Main navigation" className="flex items-center gap-5 text-sm sm:gap-8">
            <Link href="/" className="text-[#a1a1aa] transition-colors hover:text-white">Home</Link>
            <Link href="/versions" aria-current="page" className="text-white">Versions</Link>
            <a href={RELEASE.download} download className="inline-flex items-center gap-2 rounded-lg bg-[#f4f4f6] px-3.5 py-1.5 font-medium text-[#09090b] transition-colors hover:bg-white">
              <Download className="h-3.5 w-3.5" aria-hidden="true" />
              Download
            </a>
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1000px] flex-1 px-6 pb-24 pt-12 sm:pt-20">
        <div className="mb-5 inline-flex items-center gap-2 rounded border border-white/[0.06] bg-white/[0.04] px-2.5 py-1 font-mono text-xs uppercase tracking-wider text-[#a1a1aa]">
          <GitCommitHorizontal className="h-3.5 w-3.5 text-[#32d74b]" aria-hidden="true" />
          Release history
        </div>
        <h1 className="text-4xl font-semibold tracking-[-0.03em] text-white sm:text-5xl">Versions</h1>
        <p className="mt-4 max-w-xl text-base leading-relaxed text-[#a1a1aa]">Every step forward for Notchi. Explore what’s new, what’s improved, and how the notch has evolved.</p>

        <section aria-label="Release index" className="mt-12 sm:mt-16">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.12] pb-4 font-mono text-xs uppercase tracking-wider text-[#a1a1aa]">
            <span>Release index <span className="ml-2 text-[#696973]">/ {releases.length} releases</span></span>
            <span>Newest first</span>
          </div>

          {releases.map((release, index) => (
            <details key={release.version} id={`v${release.version}`} open={index === 0} className="group scroll-mt-24 border-b border-white/[0.09]">
              <summary className="flex cursor-pointer list-none items-start gap-4 rounded-sm py-6 transition-colors hover:bg-white/[0.025] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white sm:gap-8 sm:py-7 [&::-webkit-details-marker]:hidden">
                <span className="w-20 shrink-0 pt-0.5 font-mono text-base font-medium text-white sm:w-24">v{release.version}</span>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-x-3 gap-y-2">
                    <span className="text-base font-medium text-[#e4e4e7] sm:text-lg">{release.title}</span>
                    {index === 0 && <span className="rounded border border-[#32d74b]/25 bg-[#112617] px-2 py-0.5 font-mono text-[11px] uppercase tracking-wide text-[#32d74b]">Latest</span>}
                  </span>
                  <span className="mt-2 block text-sm leading-relaxed text-[#a1a1aa]">{release.description}</span>
                </span>
                <ChevronDown aria-hidden="true" className="mt-1 h-4 w-4 shrink-0 text-[#a1a1aa] transition-transform group-open:rotate-180 motion-reduce:transition-none" />
              </summary>

              <div className="pb-8 sm:pl-32">
                {index === 0 && (
                  <figure className="mb-6 overflow-hidden rounded-xl border border-white/10 bg-black">
                    <video controls playsInline preload="metadata" className="aspect-video w-full" aria-label="Notchi version 1.4.0 release walkthrough">
                      <source src={RELEASE.video} type="video/mp4" />
                      <a href={RELEASE.video}>Watch the release walkthrough</a>
                    </video>
                    <figcaption className="px-5 py-3 text-sm text-[#a1a1aa]">The latest desktop walkthrough · 24 November 2026</figcaption>
                  </figure>
                )}
                <div className="rounded-xl border border-white/[0.07] bg-[#0e0e12] px-5 sm:px-6">
                  {release.changes.map(([title, body]) => (
                    <div key={title} className="border-b border-white/[0.06] py-5 last:border-0">
                      <h2 className="text-sm font-medium text-[#f4f4f6]">{title}</h2>
                      <p className="mt-2 text-base leading-relaxed text-[#a1a1aa]">{body}</p>
                    </div>
                  ))}
                </div>
                {index === 0 && (
                  <div className="mt-5 flex flex-wrap items-center justify-between gap-4">
                    <span className="font-mono text-xs text-[#a1a1aa]">Windows 10/11 · x64 · {RELEASE.size}</span>
                    <a href={RELEASE.download} download className="inline-flex items-center gap-2 rounded-lg bg-[#f4f4f6] px-4 py-2 text-sm font-medium text-[#09090b] transition-colors hover:bg-white">
                      <Download className="h-3.5 w-3.5" aria-hidden="true" />
                      Download v{release.version}
                    </a>
                  </div>
                )}
              </div>
            </details>
          ))}
        </section>
        <p className="mt-6 text-sm text-[#a1a1aa]">Select a release to expand or collapse its notes.</p>
      </main>

      <footer className="border-t border-white/[0.07] py-8">
        <div className="mx-auto flex max-w-[1240px] flex-wrap items-center justify-between gap-4 px-6 text-xs text-[#a1a1aa]">
          <span>Notchi — Top-Bezel Jira Utility for Windows</span>
          <Link href="/" className="transition-colors hover:text-white">Back to home</Link>
        </div>
      </footer>
    </div>
  );
}
