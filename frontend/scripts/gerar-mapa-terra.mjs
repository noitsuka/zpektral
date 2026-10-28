import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

import { feature } from "topojson-client";

const PASSO = 0.5;
const LARGURA = 360 / PASSO;
const ALTURA = 180 / PASSO;

const raiz = path.resolve(import.meta.dirname, "..");
const topologia = JSON.parse(
  await readFile(path.join(raiz, "node_modules/world-atlas/land-50m.json"), "utf8"),
);
const terra = feature(topologia, topologia.objects.land);

const aneis = [];
for (const f of terra.features ?? [terra]) {
  const g = f.geometry;
  const poligonos = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
  for (const p of poligonos) for (const anel of p) aneis.push(anel);
}

const bits = new Uint8Array(Math.ceil((LARGURA * ALTURA) / 8));
for (let l = 0; l < ALTURA; l++) {
  const lat = 90 - (l + 0.5) * PASSO;
  const cortes = [];
  for (const anel of aneis) {
    for (let i = 0, j = anel.length - 1; i < anel.length; j = i++) {
      const [x1, y1] = anel[j];
      const [x2, y2] = anel[i];
      if (y1 > lat !== y2 > lat && Math.abs(x2 - x1) < 180) {
        cortes.push(x1 + ((lat - y1) * (x2 - x1)) / (y2 - y1));
      }
    }
  }
  cortes.sort((a, b) => a - b);
  for (let k = 0; k + 1 < cortes.length; k += 2) {
    const inicio = Math.max(0, Math.ceil((cortes[k] + 180) / PASSO - 0.5));
    const fim = Math.min(LARGURA - 1, Math.floor((cortes[k + 1] + 180) / PASSO - 0.5));
    for (let c = inicio; c <= fim; c++) {
      const i = l * LARGURA + c;
      bits[i >> 3] |= 1 << (i & 7);
    }
  }
}
for (let c = 0; c < LARGURA; c++) {
  for (let l = Math.round((90 + 78) / PASSO); l < ALTURA; l++) {
    const i = l * LARGURA + c;
    bits[i >> 3] |= 1 << (i & 7);
  }
}

const saida = `export const MAPA_TERRA = {
  largura: ${LARGURA},
  altura: ${ALTURA},
  dados: "${Buffer.from(bits).toString("base64")}",
} as const;
`;
await writeFile(path.join(raiz, "src/nucleo/mapa-terra.ts"), saida);
console.log(`mapa ${LARGURA}x${ALTURA}, ${aneis.length} anéis, ${saida.length} bytes`);
