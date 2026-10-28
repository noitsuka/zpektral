import type { Espectro } from "@/nucleo/espectro";

export const FEIXE = { x: 6, y: 4, w: 20, h: 3.5 };
export const PRISMA: [number, number][] = [
  [26, 7.5],
  [11, 19.4],
  [6, 19.4],
  [21, 7.5],
];

const LINHAS_INICIO = 20.4;
const LINHAS_ALTURA_TOTAL = 7.7;
const LINHA_MIN = 8;
const ORDEM = { 4: [0, 2, 3, 1], 3: [0, 2, 1] } as const;
const DOURADA = 2;

type Linha = { x: number; y: number; w: number; h: number; dourada: boolean };

function comprimentoLinha(nivel: number): number {
  return LINHA_MIN + Math.max(0, Math.min(1, nivel)) * (FEIXE.w - LINHA_MIN);
}

export function formaDoSimbolo(
  espectro: Espectro,
  { linhas: quantidade = 4 }: { linhas?: 3 | 4 } = {},
): { linhas: Linha[] } {
  const h = quantidade === 4 ? 1.4 : 2.1;
  const passo = h + (LINHAS_ALTURA_TOTAL - quantidade * h) / (quantidade - 1);
  const linhas = ORDEM[quantidade].map((indice, i) => ({
    x: FEIXE.x,
    y: LINHAS_INICIO + i * passo,
    w: comprimentoLinha(espectro[indice]),
    h,
    dourada: indice === DOURADA,
  }));
  return { linhas };
}

export const pontosPrisma = PRISMA.map(([x, y]) => `${x},${y}`).join(" ");
export const arestasPrisma = `M${PRISMA[0].join(" ")} ${PRISMA[1].join(" ")}M${PRISMA[3].join(" ")} ${PRISMA[2].join(" ")}`;

export function svgSimbolo(
  espectro: Espectro,
  { dourada = true, linhas = 3 }: { dourada?: boolean; linhas?: 3 | 4 } = {},
): string {
  const retangulo = (x: number, y: number, w: number, h: number, fill: string) =>
    `<rect x="${x}" y="${y.toFixed(2)}" width="${w.toFixed(2)}" height="${h}" fill="${fill}"/>`;
  const partes = [
    retangulo(FEIXE.x, FEIXE.y, FEIXE.w, FEIXE.h, "#edf0ea"),
    `<polygon points="${pontosPrisma}" fill="#edf0ea" fill-opacity="0.35"/>`,
    `<path d="${arestasPrisma}" stroke="#edf0ea" stroke-width="0.7" fill="none"/>`,
    ...formaDoSimbolo(espectro, { linhas }).linhas.map((l) =>
      retangulo(l.x, l.y, l.w, l.h, l.dourada && dourada ? "#e9c46a" : "#c9cfc7"),
    ),
  ];
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="5" fill="#070707"/>${partes.join("")}</svg>`;
}
