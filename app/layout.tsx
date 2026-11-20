import type { Metadata } from "next";
import { Bricolage_Grotesque, Inter } from "next/font/google";
import "./globals.css";

const bricolage = Bricolage_Grotesque({ variable: "--font-bricolage", subsets: ["latin"], weight: ["700", "800"] });
const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Live Show Radar",
  description: "Never miss a live show by an artist you love. Concert alerts, presales and ticket deadlines across India.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${bricolage.variable} ${inter.variable}`} suppressHydrationWarning>
      <head>
        {/* Marks "motion allowed" before first paint so animated items can be pre-hidden by CSS (no flash). Cleared by app/template.tsx. */}
        <script dangerouslySetInnerHTML={{ __html: "try{if(matchMedia('(prefers-reduced-motion: no-preference)').matches)document.documentElement.dataset.motion='ok'}catch(e){}" }} />
      </head>
      <body className="grain min-h-dvh antialiased">{children}</body>
    </html>
  );
}
