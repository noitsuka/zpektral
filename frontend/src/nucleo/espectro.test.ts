import { describe, expect, it } from "vitest";

import { REPOUSO, espectroDe } from "@/nucleo/espectro";
import type { Oferta } from "@/nucleo/tipos";

function oferta(loja: string, total: number, extra: Partial<Oferta> = {}): Oferta {
  return {
    loja: { id: loja, nome: loja },
    total,
    totais: null,
    total_exato: true,
    relevancia: 100,
    ...extra,
  } as Oferta;
}

describe("espectro do símbolo", () => {
  it("mantém a forma de repouso sem pelo menos duas lojas", () => {
    expect(espectroDe([], "melhor")).toEqual(REPOUSO);
    expect(espectroDe([oferta("a", 100), oferta("a", 50)], "melhor")).toEqual(REPOUSO);
  });

  it("põe a loja mais barata na barra dourada, como a mais curta", () => {
    const s = espectroDe(
      [oferta("a", 300), oferta("b", 100), oferta("c", 200), oferta("d", 400)],
      "melhor",
    );
    expect(s[2]).toBe(Math.min(...s));
    expect(s[1]).toBe(1);
    expect(s.every((v) => v >= 0 && v <= 1)).toBe(true);
  });

  it("usa o menor total exato de cada loja e ignora resultados fracos", () => {
    const s = espectroDe(
      [
        oferta("a", 1000),
        oferta("a", 100),
        oferta("b", 200),
        oferta("c", 1, { total_exato: false }),
        oferta("d", 1, { relevancia: 60 }),
      ],
      "melhor",
    );
    expect(s[2]).toBe(0);
    expect(s[1]).toBe(1);
  });
});
