import { describe, expect, it } from "vitest";

import { comparadoAoTipico, mediana, precosTipicos } from "@/nucleo/referencia";
import type { Oferta } from "@/nucleo/tipos";

function oferta(loja: string, total: number, grupo: string | null = "g1"): Oferta {
  return {
    id: `${loja}:${total}`,
    loja: { id: loja, nome: loja },
    total,
    totais: null,
    grupo,
    disponivel: true,
    frete: { status: "calculado" },
  } as Oferta;
}

describe("preço típico de um produto", () => {
  it("calcula a mediana", () => {
    expect(mediana([])).toBeNull();
    expect(mediana([5])).toBe(5);
    expect(mediana([3, 1, 2])).toBe(2);
    expect(mediana([4, 1, 3, 2])).toBe(2.5);
  });

  it("usa um preço por loja e exige três lojas", () => {
    const tipicos = precosTipicos(
      [
        oferta("a", 100),
        oferta("a", 90),
        oferta("b", 120),
        oferta("c", 110),
        oferta("x", 50, "g2"),
        oferta("y", 60, "g2"),
        oferta("z", 70, null),
      ],
      "melhor",
    );
    expect(tipicos.get("g1")).toBe(110);
    expect(tipicos.has("g2")).toBe(false);
  });

  it("ignora indisponíveis e quem não entrega", () => {
    const fora = { ...oferta("d", 10), disponivel: false } as Oferta;
    const naoEntrega = { ...oferta("e", 10), frete: { status: "nao_entrega" } } as Oferta;
    const tipicos = precosTipicos(
      [oferta("a", 100), oferta("b", 120), oferta("c", 110), fora, naoEntrega],
      "melhor",
    );
    expect(tipicos.get("g1")).toBe(110);
  });

  it("diz quanto a oferta está abaixo ou acima, com um piso de relevância", () => {
    const tipicos = new Map([["g1", 1000]]);
    expect(comparadoAoTipico(oferta("a", 900), "melhor", tipicos)).toBeCloseTo(-0.1);
    expect(comparadoAoTipico(oferta("a", 990), "melhor", tipicos)).toBeNull();
    expect(comparadoAoTipico(oferta("a", 1200), "melhor", tipicos)).toBeCloseTo(0.2);
    expect(comparadoAoTipico(oferta("a", 900, null), "melhor", tipicos)).toBeNull();
  });
});
