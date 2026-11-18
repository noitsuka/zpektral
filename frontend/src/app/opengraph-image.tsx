import { readFile } from "node:fs/promises";
import path from "node:path";

import { ImageResponse } from "next/og";

import { REPOUSO } from "@/nucleo/espectro";
import { MARCA } from "@/nucleo/marca";
import { svgSimbolo } from "@/nucleo/simbolo";

export const alt = `${MARCA.nome}: ${MARCA.slogan}`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const PASTA = path.join(process.cwd(), "node_modules/@fontsource/archivo/files");

export default async function ImagemCompartilhamento() {
  const [regular, negrito] = await Promise.all([
    readFile(path.join(PASTA, "archivo-latin-400-normal.woff")),
    readFile(path.join(PASTA, "archivo-latin-600-normal.woff")),
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
        padding: "80px 88px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={simbolo} width={104} height={104} alt="" />
        <span style={{ fontSize: 92, fontWeight: 600, letterSpacing: -3 }}>{MARCA.nome}</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
        <span style={{ width: 120, height: 3, background: "#e9c46a" }} />
        <span style={{ fontSize: 44, color: "#a1a6a2", maxWidth: 900 }}>{MARCA.slogan}</span>
      </div>
    </div>,
    {
      ...size,
      fonts: [
        { name: "Archivo", data: regular, weight: 400 },
        { name: "Archivo", data: negrito, weight: 600 },
      ],
    },
  );
}
