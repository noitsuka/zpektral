import type { Metadata, Viewport } from "next";
import { Archivo } from "next/font/google";

import { MARCA } from "@/nucleo/marca";
import { URL_DO_SITE } from "@/nucleo/site";

import "./globals.css";

const texto = Archivo({
  variable: "--fonte-texto",
  subsets: ["latin"],
  axes: ["wdth"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(URL_DO_SITE),
  title: {
    default: `${MARCA.nome}: ${MARCA.slogan}`,
    template: `%s · ${MARCA.nome}`,
  },
  description: MARCA.descricao,
  applicationName: MARCA.nome,
  authors: [{ name: "Gabriel Barreto", url: "https://github.com/noitsuka" }],
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#16191c" },
  ],
};

export default function LayoutRaiz({ children }: LayoutProps<"/">) {
  return (
    <html lang="pt-BR" className={texto.variable}>
      <body className="min-h-dvh bg-fundo font-sans text-tinta">{children}</body>
    </html>
  );
}
