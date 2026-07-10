import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MF Lookr",
  description:
    "Browse fund house → fund → year → month from full detailed monthly factsheets: holdings, allocation, deployable cash, month-on-month changes and an AI interpretation.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
