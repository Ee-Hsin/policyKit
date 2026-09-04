import type { Metadata } from "next";
import Link from "next/link";
import { MotionProvider } from "@/components/MotionProvider";
import "./globals.css";
import "./taste.css";

export const metadata: Metadata = {
  title: "PolicyKit",
  description: "AI-assisted job-posting editor and pre-publication compliance",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <a className="skip-link" href="#main-content">Skip to main content</a>
        <header className="site-header">
          <div className="site-header__inner">
            <Link className="brand" href="/" aria-label="PolicyKit home">
              <span className="brand__mark" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <path d="M12 3.2 19 6v5.4c0 4.4-2.8 7.8-7 9.6-4.2-1.8-7-5.2-7-9.6V6l7-2.8Z" />
                  <path d="m9 12 2 2 4-4" />
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
