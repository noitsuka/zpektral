import { describe, expect, it } from "vitest";

import { urlTransmissao } from "@/nucleo/api";

describe("transmissão da busca", () => {
  it("pede todas as condições para que os filtros funcionem no navegador", () => {
    const url = new URL(urlTransmissao("air fryer", "01310100"));
    expect(url.pathname).toBe("/busca/transmissao");
    expect(url.searchParams.get("q")).toBe("air fryer");
    expect(url.searchParams.get("cep")).toBe("01310100");
    expect(url.searchParams.get("condicao")).toBe("novo,recondicionado,usado");
    expect(url.searchParams.has("preco_max")).toBe(false);
    expect(url.searchParams.has("lojas")).toBe(false);
  });

  it("funciona sem CEP", () => {
    expect(new URL(urlTransmissao("tv", null)).searchParams.has("cep")).toBe(false);
  });
});
