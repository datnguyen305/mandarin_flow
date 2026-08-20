import type { Metadata } from "next";
import { AppHeader } from "@/components/AppHeader";
import { FloatingVideoPlayer } from "@/components/FloatingVideoPlayer";
import { ImportProcessingMonitor } from "@/components/ImportProcessingMonitor";
import "./globals.css";

export const metadata: Metadata = {
  title: "MandarinFlow",
  description: "Học tiếng Trung theo ngữ cảnh video"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className="font-sans antialiased">
        <AppHeader />
        {children}
        <ImportProcessingMonitor />
        <FloatingVideoPlayer />
      </body>
    </html>
  );
}
