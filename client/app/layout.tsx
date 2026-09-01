import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "PolicyKit",
  description: "Pre-publication job-posting compliance",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="site-header__inner">
            <Link className="brand" href="/" aria-label="PolicyKit home">
              <span className="brand__mark" aria-hidden="true">
                P
              </span>
              <span>PolicyKit</span>
            </Link>
            <nav className="site-nav" aria-label="Primary navigation">
              <Link href="/">New review</Link>
              <Link href="/admin/policies">Policy admin</Link>
            </nav>
          </div>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
