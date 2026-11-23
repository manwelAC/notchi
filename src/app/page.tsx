"use client";

import React, { useRef, useState } from "react";
import {
  Download,
  Check,
  Copy,
  Monitor,
  ShieldCheck,
  Terminal,
  Layers,
  Play,
  Pause,
  RotateCcw,
  Maximize2,
  ExternalLink,
  KeyRound,
  GitCommitHorizontal,
} from "lucide-react";

const SHA256_HASH =
  "0B93391ED480D8DD5D900F811931AB6D42F6A853CB4FC7A02654B489E8E05EEF";

function VideoShowcasePlayer({
  src,
  badgeText,
  subtitle,
  footerLeft,
}: {
  src: string;
  badgeText: string;
  subtitle: string;
  footerLeft: string;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [progress, setProgress] = useState<number>(0);

  const togglePlay = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) {
      v.play();
      setIsPlaying(true);
    } else {
      v.pause();
      setIsPlaying(false);
    }
  };

  const restartVideo = () => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = 0;
    v.play();
    setIsPlaying(true);
  };

  const openFullscreen = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.requestFullscreen) {
      v.requestFullscreen();
    }
  };

  const handleTimeUpdate = () => {
    const v = videoRef.current;
    if (!v || !v.duration) return;
    setProgress((v.currentTime / v.duration) * 100);
  };

  return (
    <div>
      {/* Top Video Frame Bar */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 rounded-xl bg-[#0e0e12] border border-white/[0.07]">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider text-[#e4e4e7]">
            <span className="w-2 h-2 rounded-full bg-[#32d74b]" />
            <span>{badgeText}</span>
          </span>
          <span className="text-white/15">|</span>
          <span className="text-[12px] text-[#a1a1aa]">{subtitle}</span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={togglePlay}
            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-[12px] font-medium bg-[#18181f] hover:bg-[#22222c] text-[#e4e4e7] border border-white/[0.07] transition-colors cursor-pointer"
          >
            {isPlaying ? (
              <>
                <Pause className="w-3.5 h-3.5" />
                <span>Pause</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                <span>Play</span>
              </>
            )}
          </button>
          <button
            onClick={restartVideo}
            title="Restart video"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-medium bg-[#18181f] hover:bg-[#22222c] text-[#a1a1aa] hover:text-white border border-white/[0.07] transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Replay</span>
          </button>
          <button
            onClick={openFullscreen}
            title="Fullscreen"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[12px] font-medium bg-[#18181f] hover:bg-[#22222c] text-[#a1a1aa] hover:text-white border border-white/[0.07] transition-colors cursor-pointer"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Hardware Bezel Video Container */}
      <div className="relative rounded-2xl border border-white/[0.11] bg-[#0a0b0f] overflow-hidden shadow-[0_28px_80px_rgba(0,0,0,0.85)]">
        <div className="relative w-full aspect-video bg-[#070709]">
          <video
            ref={videoRef}
            src={src}
            autoPlay
            loop
            muted
            playsInline
            onClick={togglePlay}
            onTimeUpdate={handleTimeUpdate}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            className="w-full h-full object-contain cursor-pointer"
          />
        </div>

        {/* Subtle Progress Hairline Bar + Telemetry Footer */}
        <div className="w-full h-[2px] bg-[#16161d]">
          <div
            className="h-full bg-[#f4f4f6] transition-all duration-100"
            style={{ width: `${progress}%` }}
          />
        </div>

        <div className="px-5 py-3 bg-[#0b0b0f] flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono text-[#696973]">
          <span>{footerLeft}</span>
          <span>CLICK VIDEO TO PAUSE / RESUME</span>
        </div>
      </div>
    </div>
  );
}

export default function NotchiPage() {
  const [copiedSha, setCopiedSha] = useState<boolean>(false);

  const copyChecksum = () => {
    navigator.clipboard.writeText(SHA256_HASH);
    setCopiedSha(true);
    setTimeout(() => setCopiedSha(false), 2000);
  };

  const loginSteps = [
    {
      step: "01",
      title: "Generate an Atlassian API Token",
      body: "Click 'Get New API Key ↗' inside Notchi (or open id.atlassian.com/manage-profile/security/api-tokens). Click Create API token, give it a label like 'notchi', and copy the token.",
      linkText: "Open Atlassian API Tokens ↗",
      linkHref: "https://id.atlassian.com/manage-profile/security/api-tokens",
    },
    {
      step: "02",
      title: "Select Your Kanban Space (or Auto-Detect)",
      body: "Hover the top-center bezel to expand Notchi. Enter your Jira Cloud URL and click the 'KANBAN SPACE' dropdown capsule to pick your Space from the full workspace list (or leave it on 'Auto-Detect' so Notchi finds your active boards automatically).",
    },
    {
      step: "03",
      title: "Enter Email & Paste Your API Key",
      body: "Type your Atlassian account email address and paste your copied API token. Notchi automatically detects whether your role is Developer (Assignee) or IQA Officer.",
    },
    {
      step: "04",
      title: "Switch Spaces & Roles Anytime",
      body: "Click 'Save & Connect'. Inside the Notch, click the Board pill (e.g. 'SM360 Board ▾') to switch between any of your Jira Spaces (or 'All My Spaces'), and click the 'Role: DEV / IQA' pill to toggle roles anytime.",
    },
  ];

  return (
    <div className="min-h-screen bg-[#070709] text-[#f4f4f6] flex flex-col">
      {/* Top Hardware Navigation Bar */}
      <header className="sticky top-0 z-50 border-b border-white/[0.07] bg-[#070709]/85 backdrop-blur-md">
        <div className="max-w-[1240px] mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3.5">
            <img
              src="/notchi-icon.png"
              alt="Notchi Icon"
              className="w-8 h-8 rounded-[8px] border border-white/10"
            />
            <div className="flex items-center gap-2.5">
              <span className="font-semibold tracking-tight text-[15px] text-white">
                Notchi
              </span>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-white/[0.05] text-[#a1a1aa] border border-white/[0.07]">
                v1.3.0 · Win x64
              </span>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-8 text-[13px] text-[#a1a1aa]">
            <a href="#demo" className="hover:text-white transition-colors">
              Video Demo
            </a>
            <a
              href="#how-to-login"
              className="hover:text-white transition-colors"
            >
              How to Login
            </a>
            <a
              href="#architecture"
              className="hover:text-white transition-colors"
            >
              Architecture
            </a>
            <a href="#versions" className="hover:text-white transition-colors">
              Versions
            </a>
            <a href="#download" className="hover:text-white transition-colors">
              Release Package
            </a>
          </nav>

          <div className="flex items-center gap-3">
            <a
              href="/downloads/Notchi-Windows-x64.zip"
              download
              className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-[#f4f4f6] text-[#09090b] font-medium text-[13px] hover:bg-white transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download .zip</span>
              <span className="text-[11px] font-mono text-[#52525b] ml-0.5">
                30.8 MB
              </span>
            </a>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero Section */}
        <section className="max-w-[1240px] mx-auto px-6 pt-14 pb-10">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-end">
            <div className="lg:col-span-8">
              <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-md bg-[#121217] border border-white/[0.08] text-[12px] text-[#a1a1aa] mb-5">
                <span className="w-1.5 h-1.5 rounded-full bg-[#32d74b]" />
                <span>Native Windows 10/11 Top-Bezel Utility for Jira Cloud</span>
              </div>
              <h1 className="text-4xl sm:text-5xl lg:text-[54px] font-semibold tracking-[-0.03em] leading-[1.06] text-white">
                Your Jira Kanban board,
                <br />
                built into the top bezel.
              </h1>
              <p className="mt-5 text-[16px] sm:text-[17px] text-[#a1a1aa] max-w-[62ch] leading-relaxed">
                Notchi turns the top-center of your Windows monitor into a tactile
                120Hz hardware notch. Hover to inspect live Kanban status counts,
                click any column tile to bloom open its task list, and inspect
                FRD document IDs, descriptions, and attachments without touching a
                browser tab.
              </p>
            </div>

            <div className="lg:col-span-4 flex flex-col sm:flex-row lg:flex-col gap-3 lg:items-end">
              <a
                href="/downloads/Notchi-Windows-x64.zip"
                download
                className="w-full sm:w-auto lg:w-full inline-flex items-center justify-between px-5 py-3.5 rounded-xl bg-[#f4f4f6] text-[#09090b] font-semibold text-[14px] hover:bg-white transition-all group"
              >
                <span className="flex items-center gap-2.5">
                  <Download className="w-4 h-4" />
                  <span>Download Notchi for Windows</span>
                </span>
                <span className="font-mono text-[12px] text-[#52525b] group-hover:translate-x-0.5 transition-transform">
                  x64 .ZIP →
                </span>
              </a>

              <div className="w-full sm:w-auto lg:w-full px-4 py-2.5 rounded-xl bg-[#0e0e12] border border-white/[0.07] flex items-center justify-between text-[12px] text-[#a1a1aa]">
                <span className="font-mono text-[11px] text-[#696973]">
                  Standalone EXE · Zero dependencies
                </span>
                <span className="font-mono text-[11px] text-[#e4e4e7]">
                  Windows 10 / 11
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* Main Video Demo Showcase Section */}
        <section id="demo" className="max-w-[1240px] mx-auto px-6 pb-20">
          <VideoShowcasePlayer
            src="/demo/notchi-demo.mp4"
            badgeText="60 FPS Desktop Capture"
            subtitle="Hover expansion, Kanban status drill-down, bubble-animated task list, and ticket inspection in action."
            footerLeft="SOURCE: LIVE WINDOWS 11 DESKTOP CAPTURE (1280×720 · 60FPS)"
          />
        </section>

        {/* How to Login Video + Step-by-Step Instructions Section */}
        <section
          id="how-to-login"
          className="max-w-[1240px] mx-auto px-6 py-16 border-t border-white/[0.07]"
        >
          <div className="max-w-2xl mb-8">
            <div className="inline-flex items-center gap-2 text-[11px] font-mono uppercase tracking-wider text-[#a1a1aa] px-2.5 py-1 rounded bg-white/[0.04] border border-white/[0.06] mb-3">
              <KeyRound className="w-3.5 h-3.5 text-[#32d74b]" />
              <span>Authentication & Setup Walkthrough</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-white">
              How to Login
            </h2>
            <p className="mt-2.5 text-[15px] text-[#a1a1aa] leading-relaxed">
              Connect your Atlassian Jira Cloud account once using an API token.
              Your session is cached locally on your machine so Notchi connects
              automatically every time you launch it.
            </p>
          </div>

          {/* How to Login Video Player */}
          <VideoShowcasePlayer
            src="/demo/how-to-login.mp4"
            badgeText="How to Login Walkthrough"
            subtitle="Generating an Atlassian API token, pasting credentials into Notchi, and connecting to your Jira project."
            footerLeft="WALKTHROUGH: ONE-TIME ATLASSIAN API TOKEN SETUP (1280×720 · 60FPS)"
          />

          {/* Step-by-Step Instructions Below the Video */}
          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {loginSteps.map((item) => (
              <div
                key={item.step}
                className="p-6 rounded-2xl bg-[#0e0e12] border border-white/[0.07] flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-mono text-[11px] font-bold px-2.5 py-0.5 rounded bg-white/[0.05] text-[#e4e4e7] border border-white/[0.07]">
                      STEP {item.step}
                    </span>
                  </div>
                  <h3 className="text-[15px] font-semibold text-white leading-snug">
                    {item.title}
                  </h3>
                  <p className="mt-2 text-[13px] text-[#a1a1aa] leading-relaxed">
                    {item.body}
                  </p>
                </div>

                {item.linkHref && (
                  <div className="mt-4 pt-3 border-t border-white/[0.06]">
                    <a
                      href={item.linkHref}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-[12px] font-medium text-[#f4f4f6] hover:underline"
                    >
                      <span>{item.linkText}</span>
                    </a>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* Architecture & Engineering Specs */}
        <section
          id="architecture"
          className="max-w-[1240px] mx-auto px-6 py-16 border-t border-white/[0.07]"
        >
          <div className="max-w-2xl mb-12">
            <div className="text-[11px] font-mono uppercase tracking-wider text-[#696973] mb-2">
              System Architecture
            </div>
            <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-white">
              Engineered like a native hardware bezel layer.
            </h2>
            <p className="mt-3 text-[15px] text-[#a1a1aa] leading-relaxed">
              Built specifically for Windows 10 and Windows 11 multi-monitor
              setups without Electron bloat or background telemetry services.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-5">
            {/* Spec 1: 7 cols */}
            <div className="md:col-span-7 p-7 rounded-2xl bg-[#0e0e12] border border-white/[0.07] flex flex-col justify-between">
              <div>
                <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#a1a1aa] px-2.5 py-1 rounded bg-white/[0.04] border border-white/[0.06] mb-4">
                  <Layers className="w-3.5 h-3.5" />
                  <span>2× Supersampled Silhouette Masking</span>
                </div>
                <h3 className="text-[18px] font-semibold text-white">
                  True outward concave notch ears with zero color-key bleed
                </h3>
                <p className="mt-2.5 text-[14px] text-[#a1a1aa] leading-relaxed">
                  Interior typography, status cards, and activity rings render
                  onto a solid{" "}
                  <code className="font-mono text-[#e4e4e7]">#09090b</code>{" "}
                  canvas at 2× resolution and downsample via Lanczos filtering
                  before compositing against a binary silhouette mask. Your
                  desktop wallpaper never bleeds through anti-aliased subpixels.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-white/[0.06] flex items-center justify-between text-[12px] font-mono text-[#696973]">
                <span>Collapsed: 340 × 44 px</span>
                <span>Expanded: 732 × 304 px</span>
                <span>25 Cached Spring Frames</span>
              </div>
            </div>

            {/* Spec 2: 5 cols */}
            <div className="md:col-span-5 p-7 rounded-2xl bg-[#0e0e12] border border-white/[0.07] flex flex-col justify-between">
              <div>
                <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#a1a1aa] px-2.5 py-1 rounded bg-white/[0.04] border border-white/[0.06] mb-4">
                  <Monitor className="w-3.5 h-3.5" />
                  <span>SM_XVIRTUALSCREEN Bounds</span>
                </div>
                <h3 className="text-[18px] font-semibold text-white">
                  End-to-end dual & triple monitor dragging
                </h3>
                <p className="mt-2.5 text-[14px] text-[#a1a1aa] leading-relaxed">
                  Hold left-click anywhere on the notch to slide it smoothly
                  across all connected monitors. Double-click the top grip to
                  snap directly to the center of your active display.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-white/[0.06] flex items-center justify-between text-[12px] font-mono text-[#696973]">
                <span>Per-Monitor DPI Aware v2</span>
                <span>Auto-saves X coordinate</span>
              </div>
            </div>

            {/* Spec 3: 5 cols */}
            <div className="md:col-span-5 p-7 rounded-2xl bg-[#0e0e12] border border-white/[0.07] flex flex-col justify-between">
              <div>
                <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#a1a1aa] px-2.5 py-1 rounded bg-white/[0.04] border border-white/[0.06] mb-4">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  <span>Local AppData Session Persistence</span>
                </div>
                <h3 className="text-[18px] font-semibold text-white">
                  Cached locally forever. Renew only on expiry.
                </h3>
                <p className="mt-2.5 text-[14px] text-[#a1a1aa] leading-relaxed">
                  Your Atlassian credentials are cached locally in{" "}
                  <code className="font-mono text-[#e4e4e7]">
                    %LOCALAPPDATA%\Notchi\
                  </code>{" "}
                  and authenticate directly with your Jira Cloud REST API v3
                  endpoint. Notchi never asks you to log in again unless your API
                  token expires.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-white/[0.06] flex items-center justify-between text-[12px] font-mono text-[#696973]">
                <span>Direct Jira REST API v3</span>
                <span>HTTP 401 Auto-Detection</span>
              </div>
            </div>

            {/* Spec 4: 7 cols */}
            <div className="md:col-span-7 p-7 rounded-2xl bg-[#0e0e12] border border-white/[0.07] flex flex-col justify-between">
              <div>
                <div className="inline-flex items-center gap-2 font-mono text-[11px] text-[#a1a1aa] px-2.5 py-1 rounded bg-white/[0.04] border border-white/[0.06] mb-4">
                  <Terminal className="w-3.5 h-3.5" />
                  <span>DWM Native Rounded Windows + ADF Parser</span>
                </div>
                <h3 className="text-[18px] font-semibold text-white">
                  Full Atlassian Document Format & attachment streaming
                </h3>
                <p className="mt-2.5 text-[14px] text-[#a1a1aa] leading-relaxed">
                  Clicking any Kanban status tile blooms open a hardware-rounded
                  Windows 11 DWM companion panel (
                  <code className="font-mono text-[#e4e4e7]">DWMWCP_ROUND</code>
                  ). Inspect custom fields (
                  <code className="font-mono text-[#e4e4e7]">Document ID</code>,{" "}
                  <code className="font-mono text-[#e4e4e7]">Team</code>,{" "}
                  <code className="font-mono text-[#e4e4e7]">Consult To</code>),
                  structured ADF descriptions, and open PDF or image attachments
                  in one click.
                </p>
              </div>
              <div className="mt-6 pt-4 border-t border-white/[0.06] flex items-center justify-between text-[12px] font-mono text-[#696973]">
                <span>DWMWA_WINDOW_CORNER_PREFERENCE</span>
                <span>Unified Pointer Wheel Router</span>
              </div>
            </div>
          </div>
        </section>

        {/* Versions & Changelog Section */}
        <section
          id="versions"
          className="max-w-[1240px] mx-auto px-6 py-16 border-t border-white/[0.07]"
        >
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-6 mb-10">
            <div className="max-w-2xl">
              <div className="inline-flex items-center gap-2 text-[11px] font-mono uppercase tracking-wider text-[#a1a1aa] px-2.5 py-1 rounded bg-white/[0.04] border border-white/[0.06] mb-3">
                <GitCommitHorizontal className="w-3.5 h-3.5 text-[#32d74b]" />
                <span>Release History & Package Updates</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-white">
                Versions
              </h2>
              <p className="mt-2.5 text-[15px] text-[#a1a1aa] leading-relaxed">
                Every standalone Windows build packaged for Notchi, detailing
                new capabilities, Kanban engine upgrades, and UI refinements.
              </p>
            </div>
            <div className="flex items-center gap-2.5 text-[12px] font-mono text-[#a1a1aa] px-3.5 py-2 rounded-xl bg-[#0e0e12] border border-white/[0.07]">
              <span className="w-2 h-2 rounded-full bg-[#32d74b]" />
              <span>Latest Stable Build:</span>
              <span className="text-white font-semibold">v1.3.0 (Win x64)</span>
            </div>
          </div>

          <div className="space-y-5">
            {/* v1.3.0 — Latest */}
            <div className="rounded-2xl bg-[#0e0e12] border border-white/[0.11] p-6 sm:p-8">
              <div className="flex flex-wrap items-center justify-between gap-4 pb-5 border-b border-white/[0.07]">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="font-mono text-[15px] font-bold text-white px-3 py-1 rounded-lg bg-[#18181f] border border-white/[0.1]">
                    v1.3.0
                  </span>
                  <span className="inline-flex items-center gap-1.5 text-[11px] font-mono uppercase tracking-wider px-2.5 py-1 rounded-md bg-[#112617] text-[#32d74b] border border-[#32d74b]/30">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#32d74b]" />
                    <span>Latest Release</span>
                  </span>
                  <span className="text-[14px] font-semibold text-white">
                    Dynamic Multi-Space Kanban, Dev / IQA Role Engine & Custom Space Modal
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="font-mono text-[12px] text-[#696973]">
                    Windows 10/11 x64 · Notchi-Windows-x64.zip
                  </span>
                  <a
                    href="/downloads/Notchi-Windows-x64.zip"
                    download
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#f4f4f6] hover:bg-white text-[#09090b] font-semibold text-[12px] transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Download v1.3.0</span>
                  </a>
                </div>
              </div>

              <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4 text-[13.5px] text-[#a1a1aa]">
                <div className="p-4 rounded-xl bg-[#09090b] border border-white/[0.05]">
                  <div className="font-mono text-[11px] uppercase tracking-wider text-[#32d74b] mb-1.5">
                    Custom Space Switcher Popover Modal
                  </div>
                  <p className="leading-relaxed">
                    Replaced the native Windows dropdown menu with a custom
                    DWM-rounded hardware popover featuring bubble-open spring
                    animation, instant live search filtering across all 24
                    workspace spaces, active task count pills, and crisp vector
                    chevron rendering.
                  </p>
                </div>
                <div className="p-4 rounded-xl bg-[#09090b] border border-white/[0.05]">
                  <div className="font-mono text-[11px] uppercase tracking-wider text-[#38bdf8] mb-1.5">
                    Automatic Dev & IQA Officer Role Detection
                  </div>
                  <p className="leading-relaxed">
                    Automatically queries both Developer assignments (
                    <code className="font-mono text-[#e4e4e7]">assignee = currentUser()</code>
                    ) and IQA Officer tasks (
                    <code className="font-mono text-[#e4e4e7]">IQA Officer cf[10179]</code>{" "}
                    &{" "}
                    <code className="font-mono text-[#e4e4e7]">watcher</code>),
                    with a 1-click{" "}
                    <code className="font-mono text-[#e4e4e7]">Role: DEV / IQA / ALL</code>{" "}
                    header toggle.
                  </p>
                </div>
                <div className="p-4 rounded-xl bg-[#09090b] border border-white/[0.05]">
                  <div className="font-mono text-[11px] uppercase tracking-wider text-[#e4e4e7] mb-1.5">
                    Selectable Space Dropdown on Login & Nook
                  </div>
                  <p className="leading-relaxed">
                    Employees no longer need to memorize or type project codes—
                    the <code className="font-mono text-[#e4e4e7]">KANBAN SPACE</code>{" "}
                    field on the Login screen is now a clickable dropdown
                    selector pre-loaded with{" "}
                    <code className="font-mono text-[#e4e4e7]">Auto-Detect My Space</code>,{" "}
                    <code className="font-mono text-[#e4e4e7]">All My Spaces</code>, and
                    all 24 workspace boards with instant search filtering.
                  </p>
                </div>
                <div className="p-4 rounded-xl bg-[#09090b] border border-white/[0.05]">
                  <div className="font-mono text-[11px] uppercase tracking-wider text-[#e4e4e7] mb-1.5">
                    Adaptive 3×3 Kanban Workflow Grid
                  </div>
                  <p className="leading-relaxed">
                    Dynamically adapts the 9 Kanban status tiles inside the
                    notch to match the exact statuses used by non-SM360 boards
                    while preserving the canonical 9-column SM360 layout when
                    viewing SM360.
                  </p>
                </div>
              </div>
            </div>

            {/* Older Versions Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
              {/* v1.2.0 */}
              <div className="rounded-2xl bg-[#0e0e12] border border-white/[0.07] p-6 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between gap-2 pb-3.5 mb-4 border-b border-white/[0.06]">
                    <span className="font-mono text-[13px] font-bold text-[#e4e4e7] px-2.5 py-0.5 rounded bg-white/[0.05] border border-white/[0.07]">
                      v1.2.0
                    </span>
                    <span className="font-mono text-[11px] text-[#696973]">
                      Auth & Auto-Sync Update
                    </span>
                  </div>
                  <h3 className="text-[15px] font-semibold text-white mb-2.5">
                    iOS-Style Login Capsules & Delta Auto-Sync
                  </h3>
                  <ul className="space-y-2 text-[13px] text-[#a1a1aa] leading-relaxed">
                    <li>
                      • Borderless iOS-style rounded input capsules with active
                      blue focus ring and inline{" "}
                      <code className="font-mono text-[#e4e4e7]">Show / Hide</code>{" "}
                      API token toggle.
                    </li>
                    <li>
                      • Background 30-second delta{" "}
                      <code className="font-mono text-[#e4e4e7]">● Auto-Sync</code>{" "}
                      and instant hover-expand refresh with zero UI stutter.
                    </li>
                    <li>
                      • Dedicated <code className="font-mono text-[#e4e4e7]">Sign Out</code>{" "}
                      button to clear cached credentials in one click.
                    </li>
                  </ul>
                </div>
              </div>

              {/* v1.1.0 */}
              <div className="rounded-2xl bg-[#0e0e12] border border-white/[0.07] p-6 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between gap-2 pb-3.5 mb-4 border-b border-white/[0.06]">
                    <span className="font-mono text-[13px] font-bold text-[#e4e4e7] px-2.5 py-0.5 rounded bg-white/[0.05] border border-white/[0.07]">
                      v1.1.0
                    </span>
                    <span className="font-mono text-[11px] text-[#696973]">
                      Inspector & Motion Update
                    </span>
                  </div>
                  <h3 className="text-[15px] font-semibold text-white mb-2.5">
                    120Hz Bubble Panels & Task Inspector
                  </h3>
                  <ul className="space-y-2 text-[13px] text-[#a1a1aa] leading-relaxed">
                    <li>
                      • Bubble-open and bubble-close spring animations on
                      floating Status Task List and Task Detail Inspector windows.
                    </li>
                    <li>
                      • Full Atlassian Document Format (ADF) description parser
                      with custom fields (<code className="font-mono text-[#e4e4e7]">Document ID</code>,{" "}
                      <code className="font-mono text-[#e4e4e7]">IQA Officer</code>,{" "}
                      <code className="font-mono text-[#e4e4e7]">Team</code>).
                    </li>
                    <li>
                      • Unified global pointer-coordinate mousewheel scrolling
                      across all floating panels.
                    </li>
                  </ul>
                </div>
              </div>

              {/* v1.0.0 */}
              <div className="rounded-2xl bg-[#0e0e12] border border-white/[0.07] p-6 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between gap-2 pb-3.5 mb-4 border-b border-white/[0.06]">
                    <span className="font-mono text-[13px] font-bold text-[#e4e4e7] px-2.5 py-0.5 rounded bg-white/[0.05] border border-white/[0.07]">
                      v1.0.0
                    </span>
                    <span className="font-mono text-[11px] text-[#696973]">
                      Initial Release
                    </span>
                  </div>
                  <h3 className="text-[15px] font-semibold text-white mb-2.5">
                    Top-Bezel Hardware Notch Engine
                  </h3>
                  <ul className="space-y-2 text-[13px] text-[#a1a1aa] leading-relaxed">
                    <li>
                      • 2× Lanczos supersampled notch silhouette with outward
                      concave top ears and zero wallpaper color-key bleed.
                    </li>
                    <li>
                      • End-to-end dual & triple monitor dragging across{" "}
                      <code className="font-mono text-[#e4e4e7]">SM_XVIRTUALSCREEN</code>{" "}
                      with double-click center snapping.
                    </li>
                    <li>
                      • Local <code className="font-mono text-[#e4e4e7]">%LOCALAPPDATA%\Notchi</code>{" "}
                      session persistence.
                    </li>
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Release Package & Direct Download Section */}
        <section
          id="download"
          className="max-w-[1240px] mx-auto px-6 py-16 border-t border-white/[0.07]"
        >
          <div className="rounded-2xl bg-[#0e0e12] border border-white/[0.09] p-8 sm:p-10">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
              <div className="lg:col-span-7">
                <div className="flex items-center gap-3.5 mb-4">
                  <img
                    src="/notchi-icon.png"
                    alt="Notchi App Icon"
                    className="w-12 h-12 rounded-xl border border-white/10"
                  />
                  <div>
                    <h2 className="text-xl sm:text-2xl font-semibold text-white">
                      Notchi for Windows (Standalone x64)
                    </h2>
                    <p className="text-[13px] text-[#a1a1aa]">
                      Version 1.3.0 · Pre-compiled standalone executable archive
                    </p>
                  </div>
                </div>

                <p className="text-[14px] text-[#a1a1aa] leading-relaxed max-w-[58ch]">
                  Packaged as a self-contained native Windows executable (
                  <code className="font-mono text-[#e4e4e7]">Notchi.exe</code>).
                  No Python installation, runtime libraries, or administrator
                  privileges required. Extract anywhere and launch.
                </p>

                {/* SHA-256 Checksum Bar */}
                <div className="mt-6 p-3.5 rounded-xl bg-[#09090b] border border-white/[0.06] flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[10px] font-mono uppercase text-[#696973]">
                      SHA-256 Checksum (Notchi-Windows-x64.zip)
                    </div>
                    <div className="font-mono text-[11px] text-[#a1a1aa] truncate mt-0.5">
                      {SHA256_HASH}
                    </div>
                  </div>
                  <button
                    onClick={copyChecksum}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#18181f] hover:bg-[#22222c] text-[11px] font-mono text-[#e4e4e7] shrink-0 transition-colors cursor-pointer"
                  >
                    {copiedSha ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-[#32d74b]" />
                        <span>Copied</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>
              </div>

              <div className="lg:col-span-5 flex flex-col gap-3.5 lg:pl-6 lg:border-l lg:border-white/[0.07]">
                <a
                  href="/downloads/Notchi-Windows-x64.zip"
                  download
                  className="w-full inline-flex items-center justify-center gap-2.5 px-6 py-4 rounded-xl bg-[#f4f4f6] hover:bg-white text-[#09090b] font-semibold text-[15px] transition-all"
                >
                  <Download className="w-4 h-4" />
                  <span>Download Notchi-Windows-x64.zip</span>
                </a>

                <div className="rounded-xl bg-[#09090b] border border-white/[0.06] p-4 space-y-2 text-[12px] font-mono">
                  <div className="flex justify-between text-[#a1a1aa]">
                    <span className="text-[#696973]">Archive Size</span>
                    <span>30.8 MB (.zip)</span>
                  </div>
                  <div className="flex justify-between text-[#a1a1aa]">
                    <span className="text-[#696973]">Binary Target</span>
                    <span>Notchi.exe (Win10/11 x64)</span>
                  </div>
                  <div className="flex justify-between text-[#a1a1aa]">
                    <span className="text-[#696973]">Credential Cache</span>
                    <span>%LOCALAPPDATA%\Notchi\</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Minimalist Footer */}
      <footer className="border-t border-white/[0.07] py-8">
        <div className="max-w-[1240px] mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-[12px] text-[#696973]">
          <div className="flex items-center gap-2.5">
            <img
              src="/notchi-icon.png"
              alt="Notchi"
              className="w-5 h-5 rounded-[5px] opacity-80"
            />
            <span>Notchi — Top-Bezel Jira Utility for Windows</span>
          </div>
          <div className="font-mono text-[11px]">
            Built for Jira Cloud REST API v3 · Ready for Vercel Deployment
          </div>
        </div>
      </footer>
    </div>
  );
}
