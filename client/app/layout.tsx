import type { Metadata } from "next";
import { SiteHeader } from "@/components/SiteHeader";
import "./globals.css";
import "./taste.css";

export const metadata: Metadata = {
  title: "PolicyKit",
  description: "Pre-publication job-posting compliance",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <SiteHeader />
        <main className="app-main" id="main-content">
          {children}
        </main>
      </body>
    </html>
  );
}
