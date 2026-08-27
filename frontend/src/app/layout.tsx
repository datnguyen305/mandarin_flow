import type { Metadata } from "next";
import Script from "next/script";
import { Suspense } from "react";
import { Smartphone } from "lucide-react";
import { AppHeader } from "@/components/AppHeader";
import { FloatingVideoPlayer } from "@/components/FloatingVideoPlayer";
import { LearningCelebrationProvider } from "@/components/LearningCelebrationProvider";
import { RouteScrollManager } from "@/components/RouteScrollManager";
import "./globals.css";

export const metadata: Metadata = {
  title: "MandarinFlow",
  description: "Học tiếng Trung theo ngữ cảnh video"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className="font-sans antialiased">
        <Script
          async
          src="https://www.googletagmanager.com/gtag/js?id=G-VYKJRGE538"
          strategy="afterInteractive"
        />
        <Script id="google-analytics" strategy="afterInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){window.dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-VYKJRGE538');
          `}
        </Script>
        <AppHeader />
        <Suspense fallback={null}>
          <RouteScrollManager />
        </Suspense>
        <div className="mobile-landscape-warning" role="status">
          <Smartphone aria-hidden="true" size={34} />
          <p>Vui lòng xoay dọc điện thoại để sử dụng MandarinFlow.</p>
        </div>
        {children}
        <FloatingVideoPlayer />
        <LearningCelebrationProvider />
      </body>
    </html>
  );
}
