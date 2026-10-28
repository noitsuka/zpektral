import { describe, expect, it } from "vitest";

import { adicionarRecente, lerRecentes, removerRecente } from "@/nucleo/recentes";

describe("buscas recentes", () => {
  it("põe a última busca primeiro e não repete a mesma consulta no mesmo CEP", () => {
    let lista = adicionarRecente([], { q: "air fryer", cep: "30130010" });
    lista = adicionarRecente(lista, { q: "tv 55", cep: null });
    lista = adicionarRecente(lista, { q: "Air Fryer ", cep: "30130010" });
    expect(lista).toEqual([
      { q: "Air Fryer", cep: "30130010" },
      { q: "tv 55", cep: null },
    ]);
  });

  it("guarda no máximo seis", () => {
    let lista = adicionarRecente([], { q: "a0", cep: null });
    for (let i = 1; i < 10; i++) lista = adicionarRecente(lista, { q: `a${i}`, cep: null });
    expect(lista).toHaveLength(6);
    expect(lista[0].q).toBe("a9");
  });

  it("remove uma busca", () => {
    const lista = [
      { q: "a", cep: null },
      { q: "b", cep: "01001000" },
    ];
    expect(removerRecente(lista, lista[1])).toEqual([{ q: "a", cep: null }]);
  });

  it("ignora o que não for uma lista válida", () => {
    expect(lerRecentes(null)).toEqual([]);
    expect(lerRecentes("{x")).toEqual([]);
    expect(lerRecentes('{"q":"a"}')).toEqual([]);
    expect(
      lerRecentes('[{"q":"ok","cep":"30130010"},{"q":5},{"q":"x","cep":"123"},{"q":"y"}]'),
    ).toEqual([
      { q: "ok", cep: "30130010" },
      { q: "y", cep: null },
    ]);
  });
});
