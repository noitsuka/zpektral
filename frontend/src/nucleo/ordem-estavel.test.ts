import { describe, expect, it } from "vitest";

import { destaqueSeguro, foraDeOrdem, ordemEstavel } from "@/nucleo/ordem-estavel";
import type { Oferta } from "@/nucleo/tipos";
import { agrupar } from "@/nucleo/vitrine";

function oferta(id: string, grupo: string | null = null): Oferta {
  return { id, grupo } as Oferta;
}

const itens = (...ids: string[]) => ids.map((id) => oferta(id));
const ids = (lista: { id: string }[]) => lista.map((i) => i.id);

describe("ordem estável durante a busca", () => {
  it("sem nada visto, segue o ranking", () => {
    const ranking = itens("c", "a", "b");
    expect(ordemEstavel(ranking, [])).toBe(ranking);
  });

  it("o que já foi visto fica onde estava, mesmo que o ranking mude", () => {
    expect(ids(ordemEstavel(itens("d", "c", "b", "a"), ["a", "b"]))).toEqual(["a", "b", "d", "c"]);
  });

  it("um grupo melhor que chega entra logo depois do que já foi visto, na ordem do ranking", () => {
    expect(ids(ordemEstavel(itens("x", "y", "a", "c", "b"), ["a", "b"]))).toEqual([
      "a",
      "b",
      "x",
      "y",
      "c",
    ]);
  });

  it("o que ainda não foi visto segue o ranking", () => {
    expect(ids(ordemEstavel(itens("a", "d", "c", "b"), ["a"]))).toEqual(["a", "d", "c", "b"]);
  });

  it("o que saiu do ranking some, mesmo se já tinha sido visto", () => {
    expect(ids(ordemEstavel(itens("c", "a"), ["a", "b", "c"]))).toEqual(["a", "c"]);
  });

  it("recomeçar sem nada visto devolve o ranking puro", () => {
    const ranking = itens("z", "y", "x");
    expect(ids(ordemEstavel(ranking, ["x", "y"]))).toEqual(["x", "y", "z"]);
    expect(ordemEstavel(ranking, [])).toEqual(ranking);
  });

  it("rolar a tela sem o ranking mudar não mexe em nada", () => {
    const ranking = itens("n", "m", "a", "b", "c");
    const antes = ordemEstavel(ranking, ["a"]);
    // a pessoa rolou e viu os dois seguintes, na ordem em que estavam na tela
    const depois = ordemEstavel(ranking, ["a", ...ids(antes).slice(1, 3)]);
    expect(ids(depois)).toEqual(ids(antes));
  });

  it("a troca da chave do grupo no fim da busca não move o que já foi visto", () => {
    const vistos = ["b:1", "a:1", "a:2"];
    const durante = [oferta("a:1", "g-a"), oferta("a:2", "g-a"), oferta("b:1", "g-b")];
    const noFim = [oferta("a:1", "final-a"), oferta("a:2", "final-a"), oferta("b:1", "final-b")];
    const chaves = (lista: Oferta[]) => agrupar(ordemEstavel(lista, vistos)).map((g) => g.chave);
    expect(chaves(durante)).toEqual(["g-b", "g-a"]);
    expect(chaves(noFim)).toEqual(["final-b", "final-a"]);
  });

  it("um grupo já visto fica no lugar mesmo quando as ofertas dele chegam com outro id", () => {
    // a segunda passada do comparador troca o id; a chave do grupo segura o lugar
    const vistos = ["b:1", "g-b", "a:1", "g-a"];
    const ranking = [oferta("c:1", "g-c"), oferta("a:2", "g-a"), oferta("b:1", "g-b")];
    const grupos = agrupar(ordemEstavel(ranking, vistos));
    expect(grupos.map((g) => g.chave)).toEqual(["g-b", "g-a", "g-c"]);
  });

  it("oferta nova de um grupo já visto entra no fim do grupo, sem mudar os outros de lugar", () => {
    const ranking = [oferta("c:1", "g-a"), oferta("a:1", "g-a"), oferta("b:1", "g-b")];
    const grupos = agrupar(ordemEstavel(ranking, ["a:1", "g-a", "b:1", "g-b"]));
    expect(grupos.map((g) => [g.chave, ids(g.ofertas)])).toEqual([
      ["g-a", ["a:1", "c:1"]],
      ["g-b", ["b:1"]],
    ]);
  });
});

describe("lista fora da ordem do ranking", () => {
  it("só acusa diferença quando a lista agrupada muda", () => {
    const a1 = oferta("a:1", "g-a");
    const a2 = oferta("a:2", "g-a");
    const b1 = oferta("b:1", "g-b");
    expect(foraDeOrdem([a1, b1, a2], [a1, a2, b1])).toBe(false);
    expect(foraDeOrdem([b1, a1, a2], [a1, a2, b1])).toBe(true);
    expect(foraDeOrdem([a2, a1, b1], [a1, a2, b1])).toBe(true);
  });
});

describe("troca do menor total", () => {
  it("mostra o melhor quando ninguém está mexendo no destaque", () => {
    expect(destaqueSeguro("loja-a", "loja-b", false)).toBe("loja-b");
  });

  it("segura a oferta enquanto a pessoa interage e assenta no melhor quando ela sai", () => {
    expect(destaqueSeguro("loja-a", "loja-b", true)).toBe("loja-a");
    expect(destaqueSeguro("loja-a", null, true)).toBe("loja-a");
    expect(destaqueSeguro("loja-a", "loja-b", false)).toBe("loja-b");
  });

  it("sem nada na tela, mostra o primeiro melhor mesmo com o ponteiro em cima", () => {
    expect(destaqueSeguro(null, "loja-b", true)).toBe("loja-b");
  });
});
