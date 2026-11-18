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
const TINTA = "#15171a";
const CAMPOS = ["Produto", "Frete para o seu CEP", "Pix e parcelas", "Total"];

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
        background: "#eceef1",
        padding: 56,
        fontFamily: "Archivo",
        color: TINTA,
      }}
    >
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#ffffff",
          border: `4px solid ${TINTA}`,
          borderRadius: 12,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", padding: "56px 64px 0" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={simbolo} width={104} height={104} alt="" />
            <span style={{ fontSize: 92, fontWeight: 600, letterSpacing: -3 }}>{MARCA.nome}</span>
          </div>
          <span style={{ marginTop: 28, fontSize: 40, color: "#4b5058" }}>{MARCA.slogan}</span>
        </div>
        <div style={{ display: "flex", borderTop: `4px solid ${TINTA}` }}>
          {CAMPOS.map((campo, i) => (
            <span
              key={campo}
              style={{
                flex: 1,
                padding: "26px 28px",
                fontSize: 24,
                fontWeight: 600,
                letterSpacing: 1,
                textTransform: "uppercase",
                borderLeft: i ? `2px solid ${TINTA}` : "none",
                color: i === CAMPOS.length - 1 ? "#2b3db8" : TINTA,
              }}
            >
              {campo}
            </span>
          ))}
        </div>
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
