import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { Providers } from "./providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PRIME Search harness",
  description: "Starter agent vs PRIME Search, side by side (docs/07)",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <Providers>
          <header className="border-b border-line">
            <div className="mx-auto flex max-w-[1600px] items-center justify-between px-6 py-3">
              <Link href="/" className="font-semibold tracking-tight">
                PRIME Search harness
              </Link>
              <nav className="flex gap-5 text-sm text-muted">
                <Link href="/" className="hover:text-foreground">
                  Compare
                </Link>
                <Link href="/runs" className="hover:text-foreground">
                  Runs
                </Link>
                <Link href="/bench" className="hover:text-foreground">
                  Bench
                </Link>
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-[1600px] px-6 py-6">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
