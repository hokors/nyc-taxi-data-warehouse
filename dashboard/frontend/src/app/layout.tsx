import type { Metadata } from "next";
import AppShell from "@/src/app/components/layout/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "NYC Taxi Data Warehouse",
  description: "Explore NYC taxi warehouse data with OLAP analytics.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><AppShell>{children}</AppShell></body></html>;
}
