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
  dataEntrega,
  ehCep,
  mascararCep,
  porcentagem,
  hojeEmBrasilia,
  diaAbreviado,
  haQuanto,
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
});

describe("quando o preço foi consultado", () => {
  const agora = new Date("2026-11-17T15:00:00Z");
  it("diz há quanto tempo, em minutos ou horas", () => {
    expect(haQuanto("2026-11-17T14:59:40Z", agora)).toBe("há menos de 1 min");
    expect(haQuanto("2026-11-17T14:57:00Z", agora)).toBe("há 3 min");
    expect(haQuanto("2026-11-17T12:10:00Z", agora)).toBe("há 2 h");
  });
  it("passa a dizer o dia depois de 24 horas e ignora datas ruins", () => {
    expect(haQuanto("2026-11-15T12:00:00Z", agora)).toBe("em 15 de nov");
    expect(haQuanto("lixo", agora)).toBeNull();
    expect(haQuanto("2026-11-17T15:05:00Z", agora)).toBe("há menos de 1 min");
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
      queda_verificada: true,
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

  it("abre a página do anúncio, sem passar pelo carrinho, para todas as origens", () => {
    expect(linkDaOferta({ ...base, origem: "marketplace" } as never)).toBe(base.link);
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
