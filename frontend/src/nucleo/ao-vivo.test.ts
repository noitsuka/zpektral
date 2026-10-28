import { describe, expect, it } from "vitest";

import { filtrarAoVivo, rebaixarMuitoAbaixo, usarPaginaDoServidor } from "@/nucleo/ao-vivo";
import { FILTROS_PADRAO } from "@/nucleo/filtros";
import type { Oferta } from "@/nucleo/tipos";

function oferta(id: string, total: number, extra: Partial<Oferta> = {}): Oferta {
  return {
    id,
    titulo: id,
    loja: { id: id.split(":")[0], nome: id },
    preco: total,
    melhor_preco: total,
    total,
    totais: null,
    total_exato: true,
    relevancia: 100,
    disponivel: true,
    condicao: "novo",
    voltagem: null,
    origem: "loja",
    frete: { status: "calculado", valor: 0 },
    alertas: [],
    ...extra,
  } as Oferta;
}

const fritadeiras = Array.from({ length: 12 }, (_, i) => oferta(`l${i}:f`, 25000 + i * 1500));

describe("rebaixamento de preço muito abaixo do nível", () => {
  it("rebaixa comida e acessório, mantém o produto barato de verdade", () => {
    const pizza = oferta("a:pizza", 1376);
    const cesto = oferta("b:cesto", 5500);
    const barata = oferta("c:barata", 14990);
    const saida = rebaixarMuitoAbaixo([...fritadeiras, pizza, cesto, barata]);
    const por = new Map(saida.map((o) => [o.id, o]));
    expect(por.get("a:pizza")!.relevancia).toBe(50);
    expect(por.get("a:pizza")!.alertas).toContain("preco_fora_da_curva");
    expect(por.get("b:cesto")!.relevancia).toBe(50);
    expect(por.get("c:barata")!.relevancia).toBe(100);
    expect(pizza.relevancia).toBe(100);
  });

  it("não mexe em conjuntos pequenos", () => {
    const poucas = [...fritadeiras.slice(0, 5), oferta("a:pizza", 1376)];
    expect(rebaixarMuitoAbaixo(poucas).every((o) => o.relevancia === 100)).toBe(true);
  });
});

describe("filtros aplicados enquanto as lojas respondem", () => {
  const base = [
    oferta("a:1", 10000),
    oferta("b:1", 20000, { relevancia: 40 }),
    oferta("c:1", 30000, { disponivel: false }),
    oferta("d:1", 40000, { frete: { status: "nao_entrega" } as Oferta["frete"] }),
    oferta("e:1", 50000, { condicao: "usado" }),
    oferta("f:1", 60000, { voltagem: "220V" }),
    oferta("g:1", 70000, {
      total_exato: false,
      frete: { status: "nao_informado" } as Oferta["frete"],
    }),
  ];
  const ids = (os: Oferta[]) => os.map((o) => o.id);

  it("segue o padrão: relevância mínima, compráveis e só novos", () => {
    expect(ids(filtrarAoVivo(base, FILTROS_PADRAO))).toEqual(["a:1", "f:1", "g:1"]);
  });

  it("respeita preço, loja, voltagem e frete", () => {
    expect(
      ids(filtrarAoVivo(base, { ...FILTROS_PADRAO, preco_max: 60000, preco_min: 20000 })),
    ).toEqual(["f:1"]);
    expect(ids(filtrarAoVivo(base, { ...FILTROS_PADRAO, lojas: ["g"] }))).toEqual(["g:1"]);
    expect(ids(filtrarAoVivo(base, { ...FILTROS_PADRAO, voltagem: ["110V"] }))).toEqual([
      "a:1",
      "g:1",
    ]);
    expect(
      ids(filtrarAoVivo(base, { ...FILTROS_PADRAO, voltagem: ["110V"], voltagem_estrita: true })),
    ).toEqual([]);
    expect(ids(filtrarAoVivo(base, { ...FILTROS_PADRAO, frete: "calculado" }))).toEqual([
      "a:1",
      "f:1",
    ]);
    expect(ids(filtrarAoVivo(base, { ...FILTROS_PADRAO, frete: "gratis" }))).toEqual([
      "a:1",
      "f:1",
    ]);
    expect(ids(filtrarAoVivo(base, { ...FILTROS_PADRAO, condicao: ["novo", "usado"] }))).toContain(
      "e:1",
    );
  });
});

describe("troca da lista ao vivo pela página do servidor", () => {
  const pagina = (pronto: boolean, total: number) => ({ pronto, total });

  it("usa a página quando a busca no servidor está completa", () => {
    expect(usarPaginaDoServidor(pagina(true, 12), 30)).toBe(true);
    expect(usarPaginaDoServidor(pagina(true, 0), 0)).toBe(true);
  });

  it("mantém a lista ao vivo quando a página chega incompleta", () => {
    expect(usarPaginaDoServidor(pagina(false, 0), 30)).toBe(false);
    expect(usarPaginaDoServidor(pagina(false, 4), 30)).toBe(false);
  });

  it("mantém a lista ao vivo quando a página vem vazia e a transmissão trouxe ofertas", () => {
    expect(usarPaginaDoServidor(pagina(true, 0), 30)).toBe(false);
  });

  it("sem página, fica na lista ao vivo", () => {
    expect(usarPaginaDoServidor(null, 30)).toBe(false);
  });
});
