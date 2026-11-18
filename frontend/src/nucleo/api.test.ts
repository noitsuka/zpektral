import { describe, expect, it } from "vitest";

import { parametrosDaBusca, urlTransmissao } from "@/nucleo/api";
import { FILTROS_PADRAO } from "@/nucleo/filtros";

describe("transmissão da busca", () => {
  it("pede todas as condições para que os filtros funcionem no navegador", () => {
    const url = new URL(urlTransmissao("air fryer", "01310100"));
    expect(url.pathname).toBe("/busca/transmissao");
    expect(url.searchParams.get("q")).toBe("air fryer");
    expect(url.searchParams.get("cep")).toBe("01310100");
    expect(url.searchParams.get("condicao")).toBe("novo,recondicionado,usado");
    expect(url.searchParams.get("apenas_disponiveis")).toBe("false");
    expect(url.searchParams.has("preco_max")).toBe(false);
    expect(url.searchParams.has("lojas")).toBe(false);
  });

  it("funciona sem CEP", () => {
    expect(new URL(urlTransmissao("tv", null)).searchParams.has("cep")).toBe(false);
  });
});

describe("página da busca no servidor", () => {
  it("não manda ao servidor o que só o navegador sabe calcular", () => {
    const params = parametrosDaBusca("tv", null, {
      ...FILTROS_PADRAO,
      ordem: "economia_verificada",
      queda_verificada: true,
    });
    expect(params.has("ordem")).toBe(false);
    expect(params.has("queda")).toBe(false);
  });
});
