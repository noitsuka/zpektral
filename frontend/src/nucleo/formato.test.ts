import { describe, expect, it } from "vitest";

import {
  FILTROS_PADRAO,
  filtrosDosParametros,
  filtrosParaParametros,
  linkDaOferta,
  totalPara,
} from "@/nucleo/filtros";
import {
  reais,
  partesReais,
  dataEntrega,
  ehCep,
  mascararCep,
  porcentagem,
  hojeEmBrasilia,
  diaAbreviado,
  segundos,
} from "@/nucleo/formato";

describe("dinheiro", () => {
  it.each([
    [0, "R$ 0,00"],
    [5, "R$ 0,05"],
    [129990, "R$ 1.299,90"],
    [100000000, "R$ 1.000.000,00"],
  ])("formata %i centavos", (centavos, texto) => {
    expect(reais(centavos)).toBe(texto);
  });

  it("separa reais e centavos", () => {
    expect(partesReais(129905)).toEqual({ reais: "1.299", fracao: "05" });
  });
});

describe("cep", () => {
  it("aplica a máscara ao digitar e valida", () => {
    expect(mascararCep("30130")).toBe("30130");
    expect(mascararCep("30130010")).toBe("30130-010");
    expect(mascararCep("30.130-010 abc")).toBe("30130-010");
    expect(ehCep("30130-010")).toBe(true);
    expect(ehCep("00000-000")).toBe(false);
    expect(ehCep("3013")).toBe(false);
  });
});

describe("datas e horários", () => {
  it("formata a data de entrega prometida sem mudar o dia", () => {
    expect(dataEntrega("2026-10-22")).toMatch(/22/);
  });
  it("formata durações", () => {
    expect(segundos(270)).toBe("270 ms");
    expect(segundos(3120)).toBe("3,1 s");
  });
});

describe("filtros na URL", () => {
  it("vai e volta sem perder nada e omite os padrões", () => {
    expect(filtrosParaParametros(FILTROS_PADRAO).toString()).toBe("");
    const personalizado = {
      ...FILTROS_PADRAO,
      ordem: "menor_total" as const,
      pagamento: "pix" as const,
      lojas: ["carrefour", "kabum"],
      preco_max: 300000,
      voltagem: ["220V"],
      condicao: ["novo" as const, "recondicionado" as const],
    };
    expect(filtrosDosParametros(filtrosParaParametros(personalizado))).toEqual(personalizado);
  });

  it("ignora valores que a API recusaria", () => {
    const f = filtrosDosParametros(
      new URLSearchParams("ordem=hack&pagamento=boleto&preco_min=-5&voltagem=380V&condicao=x"),
    );
    expect(f).toEqual(FILTROS_PADRAO);
  });

  it("usa o total do pagamento e, sem ele, o preço no cartão", () => {
    const oferta = { total: 90, totais: { pix: 80, avista: 100, parcelado: null } };
    expect(totalPara(oferta as never, "pix")).toBe(80);
    expect(totalPara(oferta as never, "parcelado")).toBe(100);
    expect(totalPara(oferta as never, "melhor")).toBe(90);
  });
});

describe("link da oferta", () => {
  const base = {
    link: "https://loja.example/p?skuId=1",
    link_carrinho: "https://loja.example/checkout/cart/add?sku=1&seller=X",
  };

  it("abre o carrinho com o vendedor cotado quando a oferta é de parceiro", () => {
    expect(linkDaOferta({ ...base, origem: "marketplace" } as never)).toBe(base.link_carrinho);
  });

  it("abre a página do produto para a própria loja e para o comparador", () => {
    expect(linkDaOferta({ ...base, origem: "loja" } as never)).toBe(base.link);
    expect(linkDaOferta({ ...base, origem: "comparador", link_carrinho: null } as never)).toBe(
      base.link,
    );
  });
});

describe("porcentagem", () => {
  it("usa vírgula e no máximo uma casa", () => {
    expect(porcentagem(0.042)).toBe("4,2%");
    expect(porcentagem(0.12)).toBe("12%");
    expect(porcentagem(0.6371)).toBe("63,7%");
  });
});

describe("datas do histórico", () => {
  it("usa o dia de Brasília, não o de UTC", () => {
    expect(hojeEmBrasilia(new Date("2026-10-29T01:30:00Z"))).toBe("2026-10-28");
    expect(hojeEmBrasilia(new Date("2026-10-28T15:00:00Z"))).toBe("2026-10-28");
  });

  it("abrevia o dia para o gráfico", () => {
    expect(diaAbreviado("2026-10-05")).toBe("05 de out");
    expect(diaAbreviado("lixo")).toBe("lixo");
  });
});
