import type { Metadata, Viewport } from "next";
import { Inter, Instrument_Serif, Newsreader } from "next/font/google";
import { SiteFooter } from "@/components/Editorial";
import { todasNoticias } from "@/lib/noticias";
import { SITE_DESCRICAO, SITE_NOME, SITE_URL } from "@/lib/site";
import { SCRIPT_TEMA } from "@/lib/tema";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-inter" });
const newsreader = Newsreader({ subsets: ["latin"], weight: ["400", "600", "700"], style: ["normal", "italic"], variable: "--font-newsreader" });
const instrumentSerif = Instrument_Serif({ subsets: ["latin"], weight: "400", style: ["normal", "italic"], variable: "--font-instrument-serif" });

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: `${SITE_NOME} · Jornalismo Econômico & Geopolítica Mundial`, template: `%s · ${SITE_NOME}` },
  description: SITE_DESCRICAO,
  openGraph: { type: "website", locale: "pt_BR", siteName: SITE_NOME },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fcf7f1" },
    { media: "(prefers-color-scheme: dark)", color: "#0c1017" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const fontes = [...new Set(todasNoticias().map((n) => n.source.split(" / ")[0]))];
  return (
    // data-theme é trocado pelo script abaixo antes da primeira pintura
    <html lang="pt-BR" data-theme="light" className={`${inter.variable} ${newsreader.variable} ${instrumentSerif.variable}`} suppressHydrationWarning>
      <body>
        <script dangerouslySetInnerHTML={{ __html: SCRIPT_TEMA }} />
        {children}
        <SiteFooter fontes={fontes} />
      </body>
    </html>
  );
}
