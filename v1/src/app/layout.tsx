import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ConsoleShell } from "@/components/layout/console-shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Sagad OS",
  description:
    "Open-source, self-hostable AI operations platform for supervised agent workflows.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-background text-foreground">
        <TooltipProvider delayDuration={200}>
          <ConsoleShell>{children}</ConsoleShell>
        </TooltipProvider>
      </body>
    </html>
  );
}
