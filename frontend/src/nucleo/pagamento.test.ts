import { describe, expect, it } from "vitest";

import { textoDoPagamento } from "@/nucleo/pagamento";
import type { Oferta } from "@/nucleo/tipos";

// Produto 14.500, frete 2.278: os totais já incluem o frete.
function oferta(extra: Partial<Oferta>): Oferta {
  return {
    preco: 14500,
    total: 16778,
    parcelamento: null,
    totais: { pix: null, avista: 16778, parcelado: null },
    ...extra,
  } as Oferta;
}

describe("linha do pagamento sob o total", () => {
  it("diz que o total é no Pix e quanto fica no cartão", () => {
    const o = oferta({
      total: 15328,
      totais: { pix: 15328, avista: 16778, parcelado: 16778 },
      parcelamento: { parcelas: 2, valor: 7250, total: 14500, juros: false },
    });
    expect(textoDoPagamento(o, "melhor")).toBe("no Pix; no cartão, R$ 167,78 em até 2x sem juros");
  });

  it("não repete o valor quando o parcelado sem juros é o próprio total", () => {
    const o = oferta({
      totais: { pix: null, avista: 16778, parcelado: 16778 },
      parcelamento: { parcelas: 4, valor: 3625, total: 14500, juros: false },
    });
    expect(textoDoPagamento(o, "melhor")).toBe("no cartão, em até 4x sem juros");
  });

  it("mostra o total parcelado com frete e a taxa quando há juros", () => {
    const o = oferta({
      totais: { pix: null, avista: 16778, parcelado: 17578 },
      parcelamento: { parcelas: 5, valor: 3060, total: 15300, juros: true },
    });
    expect(textoDoPagamento(o, "melhor")).toMatch(
      /^no cartão à vista, ou R\$ 175,78 em 5x com juros de [\d,]+% ao mês$/,
    );
    expect(textoDoPagamento(o, "parcelado")).toMatch(/^em 5x no cartão, com juros de/);
  });

  it("fica só com a forma quando a loja não informa parcelas", () => {
    expect(textoDoPagamento(oferta({}), "melhor")).toBe("no cartão");
    expect(textoDoPagamento(oferta({ totais: null }), "melhor")).toBeNull();
  });
});
