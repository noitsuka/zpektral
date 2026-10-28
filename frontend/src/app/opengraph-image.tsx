import { readFile } from "node:fs/promises";
import path from "node:path";

import { ImageResponse } from "next/og";

import { REPOUSO } from "@/nucleo/espectro";
import { picosDoTexto } from "@/nucleo/espectro-texto";
import { MARCA } from "@/nucleo/marca";
import { svgSimbolo } from "@/nucleo/simbolo";

export const alt = `${MARCA.nome}: ${MARCA.slogan}`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const PASTA = path.join(process.cwd(), "node_modules/@fontsource");
const LINHAS = 150;

function intensidades(): number[] {
  const nivel = Array.from({ length: LINHAS }, (_, i) => {
    const h = Math.sin(i * 12.9898) * 43758.5453;
    return 0.04 + (h - Math.floor(h)) * 0.05;
  });
  for (const p of picosDoTexto(MARCA.nome + " preço frete pix")) {
    const centro = p.posicao * (LINHAS - 1);
    for (let i = 0; i < LINHAS; i++) {
      const d = (i - centro) / 1.6;
      nivel[i] = Math.min(1, nivel[i] + p.forca * Math.exp(-d * d));
    }
  }
  return nivel;
}

export default async function ImagemCompartilhamento() {
  const [texto, leitura] = await Promise.all([
    readFile(path.join(PASTA, "archivo/files/archivo-latin-600-normal.woff")),
    readFile(path.join(PASTA, "ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff")),
  ]);
  const simbolo = `data:image/svg+xml,${encodeURIComponent(svgSimbolo(REPOUSO, { linhas: 4 }))}`;

  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        background: "#070707",
        color: "#f2f3f1",
        fontFamily: "Archivo",
        padding: "72px 80px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={simbolo} width={112} height={112} alt="" />
        <span style={{ fontSize: 96, letterSpacing: -3 }}>{MARCA.nome}</span>
      </div>
      <div style={{ display: "flex", height: 170, alignItems: "stretch" }}>
        {intensidades().map((n, i) => (
          <span
            key={i}
            style={{
              width: n > 0.5 ? 3 : 1,
              marginRight: n > 0.5 ? 4 : 6,
              background: n > 0.5 ? `rgba(233,196,106,${n})` : `rgba(242,243,241,${n * 0.6})`,
            }}
          />
        ))}
      </div>
      <span style={{ fontFamily: "Plex", fontSize: 24, color: "#a1a6a2" }}>{MARCA.slogan}</span>
    </div>,
    {
      ...size,
      fonts: [
        { name: "Archivo", data: texto, weight: 600 },
        { name: "Plex", data: leitura, weight: 400 },
      ],
    },
  );
}
