import { describe, expect, it } from "vitest";

import { picosDoTexto } from "@/nucleo/espectro-texto";

describe("espectro de uma consulta", () => {
  it("não tem picos sem texto", () => {
    expect(picosDoTexto("")).toEqual([]);
    expect(picosDoTexto("   ")).toEqual([]);
  });

  it("é sempre o mesmo para a mesma consulta, sem ligar para caixa e espaços", () => {
    expect(picosDoTexto("Air  Fryer ")).toEqual(picosDoTexto("air fryer"));
  });

  it("muda quando a consulta muda", () => {
    expect(picosDoTexto("air fryer")).not.toEqual(picosDoTexto("air fryer 5l"));
  });

  it("mantém posição e força dentro da faixa e limita a quantidade", () => {
    const picos = picosDoTexto("geladeira frost free inox 450 litros duas portas branca");
    expect(picos.length).toBeLessThanOrEqual(24);
    for (const p of picos) {
      expect(p.posicao).toBeGreaterThanOrEqual(0);
      expect(p.posicao).toBeLessThan(1);
      expect(p.forca).toBeGreaterThan(0);
      expect(p.forca).toBeLessThanOrEqual(1);
    }
  });

  it("dá a cada palavra um pico forte", () => {
    const fortes = picosDoTexto("smart tv 55").filter((p) => p.forca >= 0.6);
    expect(fortes).toHaveLength(3);
  });
});
