import type { Metadata } from "next";
import { Be_Vietnam_Pro } from "next/font/google";
import type { ReactNode } from "react";

import { Navigation } from "@/components/navigation";

import "./globals.css";

const vietnameseFont = Be_Vietnam_Pro({
  display: "swap",
  subsets: ["latin", "vietnamese"],
  variable: "--font-vietnamese",
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "FlatMate Comfort",
  description: "Căn hộ thông minh mô phỏng bằng AI",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html className={vietnameseFont.variable} lang="vi">
      <body>
        <Navigation />
        {children}
      </body>
    </html>
  );
}
