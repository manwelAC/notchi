import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Notchi — Hardware-Grade Jira Notch for Windows",
  description:
    "A tactile macOS-inspired top-bezel notch utility for Windows. Live Jira Kanban counts, bubble-animated task lists, and full ticket inspection without opening a browser tab.",
  icons: {
    icon: "/notchi-icon.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable} dark`}>
      <body className="font-sans bg-[#070709] text-[#f4f4f6] selection:bg-white/15 selection:text-white">
        {children}
      </body>
    </html>
  );
}
