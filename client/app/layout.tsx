import type { Metadata } from "next";
import { DM_Mono, Instrument_Sans } from "next/font/google";
import Link from "next/link";
import { MotionProvider } from "@/components/MotionProvider";
import "./globals.css";
import "./taste.css";

const instrumentSans = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-instrument-sans",
});

const dmMono = DM_Mono({
  subsets: ["latin"],
  variable: "--font-dm-mono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "PolicyKit",
  description: "AI-assisted job-posting editor and pre-publication compliance",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      className={`${instrumentSans.variable} ${dmMono.variable}`}
      lang="en"
      data-scroll-behavior="smooth"
    >
      <body>
        <a className="skip-link" href="#main-content">Skip to main content</a>
        <header className="site-header">
          <div className="site-header__inner">
            <Link className="brand" href="/" aria-label="PolicyKit home">
              <span className="brand__mark" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <rect x="3.5" y="3.5" width="17" height="17" />
                  <path d="m8 12 2.5 2.5L16 9" />
                </svg>
              </span>
              <span>PolicyKit</span>
            </Link>
            <nav className="site-nav" aria-label="Primary navigation">
              <Link href="/admin/policies">Policy library</Link>
            </nav>
            <Link className="header-action" href="/">
              New posting
              <svg aria-hidden="true" viewBox="0 0 20 20"><path d="M4 10h12m-5-5 5 5-5 5" /></svg>
            </Link>
          </div>
        </header>
        <main className="app-main" id="main-content"><MotionProvider>{children}</MotionProvider></main>
      </body>
    </html>
  );
}
