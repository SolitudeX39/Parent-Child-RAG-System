import type { Metadata } from "next";
import { IBM_Plex_Sans_Thai } from "next/font/google";
import AppTabs from "./AppTabs";
import "./globals.css";

const plexThai = IBM_Plex_Sans_Thai({
  weight: ["400", "500", "600", "700"],
  subsets: ["thai", "latin"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "Medical RAG AI",
  description: "Medical RAG AI — ถามเอกสารทางการแพทย์และสร้างกราฟความรู้",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="th" className={`${plexThai.variable} h-full antialiased`}>
      <body className={`${plexThai.className} min-h-full`}>
        <div className="flex h-dvh overflow-hidden">
          <AppTabs />
          <div className="min-w-0 flex-1">{children}</div>
        </div>
      </body>
    </html>
  );
}
