import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mart Lead Generator",
  description: "Discovery, enrichment, lead scoring and reporting dashboard.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
