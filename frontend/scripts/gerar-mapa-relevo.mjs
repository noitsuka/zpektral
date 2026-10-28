import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const [, , arquivo] = process.argv;
if (!arquivo) {
  console.error("uso: node scripts/gerar-mapa-relevo.mjs <ETOPO_2022 1 grau em ASCII OPeNDAP>");
  process.exit(1);
}

const LARGURA = 360;
const ALTURA = 180;
const METROS_POR_NIVEL = 25;

const texto = await readFile(arquivo, "utf8");
const linhas = texto.split("\n").filter((l) => /^\[\d+\],/.test(l));
if (linhas.length !== ALTURA) throw new Error(`esperava ${ALTURA} linhas, veio ${linhas.length}`);

const niveis = new Uint8Array(LARGURA * ALTURA);
for (const linha of linhas) {
  const [indice, ...valores] = linha.split(",");
  const sul = Number(indice.slice(1, -1));
  if (valores.length !== LARGURA) throw new Error(`linha ${sul} com ${valores.length} colunas`);
  const l = ALTURA - 1 - sul;
  valores.forEach((v, c) => {
    const metros = Number(v);
    niveis[l * LARGURA + c] = Math.max(0, Math.min(255, Math.round(metros / METROS_POR_NIVEL)));
  });
}

const raiz = path.resolve(import.meta.dirname, "..");
const saida = `export const MAPA_RELEVO = {
  largura: ${LARGURA},
  altura: ${ALTURA},
  metrosPorNivel: ${METROS_POR_NIVEL},
  dados: "${Buffer.from(niveis).toString("base64")}",
} as const;
`;
await writeFile(path.join(raiz, "src/nucleo/mapa-relevo.ts"), saida);
const maximo = Math.max(...niveis) * METROS_POR_NIVEL;
console.log(`relevo ${LARGURA}x${ALTURA}, máximo ${maximo} m, ${saida.length} bytes`);
