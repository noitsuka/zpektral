import { describe, expect, it } from "vitest";

import { custoDoParcelamento, taxaAnual, taxaMensal } from "@/nucleo/juros";

describe("taxa mensal implícita no parcelamento", () => {
  it("acha a taxa da tabela Price", () => {
    expect(taxaMensal(100000, 9456, 12)).toBeCloseTo(0.0199, 3);
    expect(taxaMensal(377910, 40731, 12)).toBeCloseTo(0.042, 3);
  });

  it("é zero quando as parcelas somam o preço à vista", () => {
    expect(taxaMensal(120000, 10000, 12)).toBe(0);
    expect(taxaMensal(120000, 9990, 12)).toBe(0);
  });

  it("recusa entradas sem sentido", () => {
    expect(taxaMensal(0, 100, 12)).toBeNull();
    expect(taxaMensal(1000, 0, 12)).toBeNull();
    expect(taxaMensal(1000, 100, 0)).toBeNull();
    expect(taxaMensal(1000, 2000, 1)).toBeCloseTo(1, 6);
  });

  it("converte para taxa anual composta", () => {
    expect(taxaAnual(0.0199)).toBeCloseTo(0.2667, 3);
    expect(taxaAnual(0)).toBe(0);
  });

  it("descreve o custo do parcelamento em reais e em taxa", () => {
    const custo = custoDoParcelamento(377910, {
      parcelas: 12,
      valor: 40731,
      total: 488772,
      juros: true,
    });
    expect(custo).not.toBeNull();
    expect(custo!.juros).toBe(488772 - 377910);
    expect(custo!.mensal).toBeCloseTo(0.042, 3);
    expect(
      custoDoParcelamento(120000, { parcelas: 12, valor: 10000, total: 120000, juros: false }),
    ).toMatchObject({ juros: 0, mensal: 0 });
  });
});
