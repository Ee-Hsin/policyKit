"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  {
    href: "/",
    label: "Review Post",
    isActive: (pathname: string) =>
      pathname === "/" || pathname.startsWith("/sessions/"),
  },
  {
    href: "/admin/policies",
    label: "Policy Library",
    isActive: (pathname: string) => pathname.startsWith("/admin/policies"),
  },
];

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Link className="brand" href="/" aria-label="PolicyKit home">
          PolicyKit
        </Link>
        <nav className="site-nav" aria-label="Primary navigation">
          {navigation.map((item) => {
            const active = item.isActive(pathname);

            return (
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                key={item.href}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
