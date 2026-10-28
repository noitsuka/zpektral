import { describe, expect, it } from "vitest";

import { REPOUSO, type Espectro } from "@/nucleo/espectro";
import { FEIXE, PRISMA, formaDoSimbolo, svgSimbolo } from "@/nucleo/simbolo";

describe("forma do símbolo prisma", () => {
  it("abre as linhas do preço a partir da borda do feixe", () => {
    const { linhas } = formaDoSimbolo(REPOUSO);
    expect(linhas).toHaveLength(4);
    for (const l of linhas) {
      expect(l.x).toBe(FEIXE.x);
      expect(l.w).toBeGreaterThan(0);
      expect(l.w).toBeLessThanOrEqual(FEIXE.w);
    }
  });

  it("deixa a loja mais barata como a única linha dourada e a mais curta", () => {
    const espectro: Espectro = [0.5, 1, 0, 0.8];
    const { linhas } = formaDoSimbolo(espectro);
    const douradas = linhas.filter((l) => l.dourada);
    expect(douradas).toHaveLength(1);
    expect(douradas[0].w).toBe(Math.min(...linhas.map((l) => l.w)));
    expect(Math.max(...linhas.map((l) => l.w))).toBe(FEIXE.w);
  });

  it("encaixa o prisma entre o feixe e as linhas", () => {
    const { linhas } = formaDoSimbolo(REPOUSO);
    const [topoDireito, , baseEsquerda] = PRISMA;
    expect(topoDireito).toEqual([FEIXE.x + FEIXE.w, FEIXE.y + FEIXE.h]);
    expect(baseEsquerda[0]).toBe(FEIXE.x);
    expect(baseEsquerda[1]).toBeLessThan(linhas[0].y);
  });

  it("usa três linhas grossas no tamanho de aba e mantém a dourada", () => {
    const quatro = formaDoSimbolo(REPOUSO);
    const tres = formaDoSimbolo(REPOUSO, { linhas: 3 });
    expect(tres.linhas).toHaveLength(3);
    expect(tres.linhas.some((l) => l.dourada)).toBe(true);
    expect(tres.linhas[0].h).toBeGreaterThan(quatro.linhas[0].h);
    const fim = (l: { y: number; h: number }) => l.y + l.h;
    expect(fim(tres.linhas[2])).toBeCloseTo(fim(quatro.linhas[3]), 5);
  });

  it("gera o ícone com uma linha dourada, ou nenhuma enquanto varre", () => {
    const dourado = (svg: string) => svg.match(/#e9c46a/g)?.length ?? 0;
    expect(dourado(svgSimbolo(REPOUSO))).toBe(1);
    expect(dourado(svgSimbolo(REPOUSO, { dourada: false }))).toBe(0);
    expect(svgSimbolo(REPOUSO)).toContain('viewBox="0 0 32 32"');
  });
});
