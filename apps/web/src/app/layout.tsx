import type { Metadata } from "next";
import Link from "next/link";
import { SessionBar } from "@/components/SessionBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "PlanBench",
  description: "Agentic AI PlanBench — AMR/AGV path & motion planning benchmark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="layout">
          <aside className="sidebar">
            <h1>PlanBench</h1>
            <div className="tagline">AMR/AGV planning benchmark — simulation only</div>
            <nav>
              <Link href="/">Dashboard</Link>
              <Link href="/maps">Maps</Link>
              <Link href="/simulate">Live Simulation</Link>
              <Link href="/benchmarks">Benchmarks</Link>
            </nav>
            <SessionBar />
          </aside>
          <main className="content">{children}</main>
        </div>
      </body>
    </html>
  );
}
