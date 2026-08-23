import type { Metadata } from "next";
import Script from "next/script";
import { AppHeader } from "@/components/AppHeader";
import { FloatingVideoPlayer } from "@/components/FloatingVideoPlayer";
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
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-center text-xs font-medium text-amber-800 sm:hidden">
          Hãy dùng máy tính để đem lại trải nghiệm tốt hơn
        </div>
        {children}
        <FloatingVideoPlayer />
      </body>
    </html>
  );
}
