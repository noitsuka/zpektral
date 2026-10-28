import { describe, expect, it } from "vitest";

import {
  FILTROS_PADRAO,
  contarFiltrosAtivos,
  facetasDe,
  filtrosDosParametros,
  filtrosParaParametros,
  ocultasPorCondicao,
  voltagemFazSentido,
} from "@/nucleo/filtros";
import {
  todasOfertas,
  maisBarata,
  INICIAL,
  rankingAoVivo,
  progresso,
  reduzir,
} from "@/nucleo/transmissao";
import type { Oferta, RelatorioFonte } from "@/nucleo/tipos";

function oferta(id: string, total: number, extra: Partial<Oferta> = {}): Oferta {
  return {
    id,
    titulo: id,
    link: "https://loja.example",
    link_carrinho: null,
    importacao: null,
    loja: { id: id.split(":")[0], nome: "Loja" },
    preco: total,
    origem: "loja",
    vendedor: null,
    imagem: null,
    marca: null,
    ean: null,
    voltagem: null,
    condicao: "novo",
    preco_original: null,
    preco_pix: null,
    parcelamento: null,
    frete: {
      status: "calculado",
      valor: 0,
      prazo: null,
      prazo_dias: 3,
      opcoes: [],
      modalidade: null,
      transportadora: null,
      entrega_ate: null,
      cotado_em: null,
    },
    disponivel: true,
    relevancia: 100,
    posicao: 0,
    melhor_preco: total,
    total,
    total_exato: true,
    totais: { pix: null, avista: total, parcelado: null },
    alertas: [],
    grupo: null,
    ...extra,
  };
}

function relatorio(id: string, status: RelatorioFonte["status"] = "ok"): RelatorioFonte {
  return { id, nome: id, status, tempo_ms: 100, ofertas: 1, mensagem: null };
}

const meta = {
  consulta: "tv",
  endereco: null,
  pagamento: "melhor" as const,
  ordem: "relevancia" as const,
  fontes: [
    { id: "a", nome: "A", ativa: true, saude: null },
    { id: "b", nome: "B", ativa: true, saude: null },
    { id: "c", nome: "C", ativa: false, saude: null },
  ],
};

function iniciado() {
  return reduzir(reduzir(INICIAL, { tipo: "iniciar" }), { tipo: "inicio", dados: meta });
}

describe("redutor da transmissão", () => {
  it("lista todas as fontes e marca as desativadas", () => {
    const s = iniciado();
    expect(s.fontes.map((c) => c.situacao)).toEqual(["aguardando", "aguardando", "desativada"]);
    expect(progresso(s)).toEqual({ responderam: 0, total: 2 });
  });

  it("troca o lote do catálogo pelo final em vez de somar", () => {
    let s = iniciado();
    const catalogo = [oferta("a:1", 100), oferta("a:2", 200)];
    s = reduzir(s, {
      tipo: "lote",
      dados: { fonte: relatorio("a"), fase: "catalogo", ofertas: catalogo, melhor_total: 100 },
    });
    expect(s.fontes[0].situacao).toBe("catalogo");
    expect(progresso(s).responderam).toBe(0);
    s = reduzir(s, {
      tipo: "lote",
      dados: {
        fonte: relatorio("a"),
        fase: "final",
        ofertas: [oferta("a:1", 150)],
        melhor_total: 150,
      },
    });
    expect(todasOfertas(s).map((o) => o.total)).toEqual([150]);
    expect(progresso(s)).toEqual({ responderam: 1, total: 2 });
  });

  it("descarta a prévia da loja que falhou", () => {
    let s = iniciado();
    s = reduzir(s, {
      tipo: "lote",
      dados: {
        fonte: relatorio("b"),
        fase: "catalogo",
        ofertas: [oferta("b:1", 1)],
        melhor_total: 1,
      },
    });
    s = reduzir(s, { tipo: "falha_fonte", dados: { fonte: relatorio("b", "tempo_esgotado") } });
    expect(todasOfertas(s)).toEqual([]);
    expect(s.fontes[1].situacao).toBe("tempo_esgotado");
  });

  it("aplica os grupos finais no fim", () => {
    let s = iniciado();
    s = reduzir(s, {
      tipo: "lote",
      dados: { fonte: relatorio("a"), fase: "final", ofertas: [oferta("a:1", 1)], melhor_total: 1 },
    });
    s = reduzir(s, {
      tipo: "fim",
      dados: {
        tempo_ms: 10,
        total: 1,
        grupos_por_oferta: { "a:1": "g:789" },
        facetas: {
          lojas: [],
          voltagens: {},
          condicoes: {},
          preco_min: null,
          preco_max: null,
          com_total_exato: 1,
          frete_gratis: 0,
          origens: {},
        },
        fontes: [],
      },
    });
    expect(s.fase).toBe("concluida");
    expect(todasOfertas(s)[0].grupo).toBe("g:789");
  });
});

describe("ranking ao vivo", () => {
  const ofertas = [
    oferta("a:1", 300, { relevancia: 95 }),
    oferta("b:1", 100, { relevancia: 100 }),
    oferta("c:1", 200, { relevancia: 100, total_exato: false }),
  ];

  it("ordena por relevância e, no empate, pelo menor total mesmo sem frete cotado", () => {
    const barata = oferta("d:1", 50, { relevancia: 100, total_exato: false });
    expect(rankingAoVivo([...ofertas, barata], FILTROS_PADRAO).map((o) => o.id)).toEqual([
      "d:1",
      "b:1",
      "c:1",
      "a:1",
    ]);
  });

  it("ordena pelo total do pagamento escolhido", () => {
    const pix = oferta("p:1", 500, { totais: { pix: 50, avista: 500, parcelado: null } });
    const ordenadas = rankingAoVivo([...ofertas, pix], {
      ...FILTROS_PADRAO,
      ordem: "menor_total",
      pagamento: "pix",
    });
    expect(ordenadas[0].id).toBe("p:1");
  });

  it("põe o mais barato na frente mesmo sem frete cotado", () => {
    const semFrete = oferta("x:1", 50, {
      total_exato: false,
      frete: { ...ofertas[0].frete, status: "nao_informado", valor: null },
    });
    const ordenadas = rankingAoVivo([semFrete, ...ofertas], {
      ...FILTROS_PADRAO,
      ordem: "menor_total",
    });
    expect(ordenadas.map((o) => o.id)).toEqual(["x:1", "b:1", "c:1", "a:1"]);
  });

  it("nunca destaca resultado fraco nem preço com alerta", () => {
    const parte = oferta("p:1", 10, { relevancia: 80 });
    const sinalizada = oferta("f:1", 20, { alertas: ["preco_fora_da_curva"] });
    expect(maisBarata([parte, sinalizada, ...ofertas], FILTROS_PADRAO)?.id).toBe("b:1");
  });

  it("acha só o menor total exato", () => {
    expect(maisBarata(ofertas, FILTROS_PADRAO)?.id).toBe("b:1");
    expect(maisBarata([ofertas[2]], FILTROS_PADRAO)).toBeNull();
  });
});

describe("facetas da busca em andamento", () => {
  const ofertas = [
    oferta("a:1", 1000, { voltagem: "110V" }),
    oferta("b:1", 800, { condicao: "usado", voltagem: "220V" }),
    oferta("b:2", 700, { condicao: "usado" }),
    oferta("c:1", 5, { relevancia: 10 }),
  ];

  it("conta lojas, preços e voltagens só do que aparece na lista", () => {
    const f = facetasDe(ofertas, FILTROS_PADRAO)!;
    expect(f.lojas.map((l) => [l.id, l.quantidade])).toEqual([["a", 1]]);
    expect([f.preco_min, f.preco_max]).toEqual([1000, 1000]);
    expect(f.voltagens).toEqual({ "110V": 1 });
  });

  it("conta todas as condições e diz quantas estão escondidas", () => {
    const f = facetasDe(ofertas, FILTROS_PADRAO)!;
    expect(f.condicoes).toEqual({ usado: 2, novo: 1 });
    expect(ocultasPorCondicao(f, FILTROS_PADRAO)).toBe(2);
    expect(ocultasPorCondicao(f, { ...FILTROS_PADRAO, condicao: ["novo", "usado"] })).toBe(0);
  });

  it("conta os filtros ativos fora ordem e pagamento", () => {
    expect(contarFiltrosAtivos(FILTROS_PADRAO)).toBe(0);
    expect(
      contarFiltrosAtivos({
        ...FILTROS_PADRAO,
        ordem: "menor_total",
        lojas: ["a", "b"],
        preco_max: 100,
      }),
    ).toBe(3);
  });
});

describe("filtros que a loja decide", () => {
  const eletricos = (n: number, total: number) =>
    facetasDe(
      Array.from({ length: total }, (_, i) =>
        oferta(`a:${i}`, 100 + i, i < n ? { voltagem: "110V" } : {}),
      ),
      FILTROS_PADRAO,
    );

  it("só oferece voltagem quando produtos elétricos são parte real da busca", () => {
    expect(voltagemFazSentido(eletricos(2, 40))).toBe(false);
    expect(voltagemFazSentido(eletricos(3, 40))).toBe(false);
    expect(voltagemFazSentido(eletricos(10, 40))).toBe(true);
    expect(voltagemFazSentido(eletricos(2, 2))).toBe(false);
    expect(voltagemFazSentido(eletricos(3, 4))).toBe(true);
    expect(voltagemFazSentido(null)).toBe(false);
  });

  it("ignora precisão vinda da URL e não a grava", () => {
    const f = filtrosDosParametros(new URLSearchParams("relevancia_min=0"));
    expect(f.relevancia_min).toBe(FILTROS_PADRAO.relevancia_min);
    expect(filtrosParaParametros({ ...f, relevancia_min: 10 }).has("relevancia_min")).toBe(false);
    expect(contarFiltrosAtivos({ ...FILTROS_PADRAO, relevancia_min: 10 })).toBe(0);
  });
});
