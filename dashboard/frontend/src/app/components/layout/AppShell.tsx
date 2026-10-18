"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const items = [
  { label: "Overview", href: "/", icon: "◫" },
  { label: "OLAP Explorer", href: "/trip-analytics", icon: "⌁" },
  { label: "Query Performance", href: "/query-performance", icon: "◷" },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><span /><span /><span /></div>
          <strong>NYC Taxi Dataset</strong>
        </div>
        <nav>
          <p>WORKSPACE</p>
          {items.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-link ${pathname === item.href ? "active" : ""}`}
              aria-current={pathname === item.href ? "page" : undefined}
            >
              <span className="nav-icon">{item.icon}</span><span>{item.label}</span>
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="warehouse">
            <div className="db-dot">▤</div>
            <div><strong>NYC Taxi Warehouse</strong><span>Prototype data</span></div>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="breadcrumb"><span>NYC Taxi Dataset</span><span>/</span><strong>{items.find((i) => i.href === pathname)?.label ?? "Overview"}</strong></div>
        </header>
        {children}
      </main>
    </div>
  );
}
