import { describe, expect, it } from "vitest";

import { FILTROS_PADRAO } from "@/nucleo/filtros";
import {
  agrupar,
  estadoDoTotal,
  fatiar,
  lojasFora,
  melhorOferta,
  motivoDoVazio,
  separarParecidos,
} from "@/nucleo/vitrine";
import type { Frete, Oferta } from "@/nucleo/tipos";

const FRETE: Frete = {
  status: "calculado",
  valor: 1000,
  prazo: null,
  prazo_dias: 3,
  opcoes: [],
  modalidade: null,
  transportadora: null,
  entrega_ate: null,
  cotado_em: null,
};

function oferta(id: string, total: number, extra: Partial<Oferta> = {}): Oferta {
  return {
    id,
    titulo: id,
    loja: { id: id.split(":")[0], nome: id.split(":")[0].toUpperCase() },
    preco: total,
    preco_pix: null,
    melhor_preco: total,
    total,
    totais: null,
    total_exato: true,
    relevancia: 100,
    disponivel: true,
    origem: "loja",
    frete: FRETE,
    alertas: [],
    grupo: null,
    importacao: null,
    ...extra,
  } as Oferta;
}

describe("estado do total", () => {
  const com = (frete: Partial<Frete>, extra: Partial<Oferta> = {}) =>
    oferta("a:1", 100, { total_exato: false, frete: { ...FRETE, ...frete }, ...extra });

  it("só confirma o total lido no carrinho", () => {
    expect(estadoDoTotal(oferta("a:1", 100), true)).toBe("confirmado");
    expect(estadoDoTotal(com({ status: "calculado" }), true)).toBe("estimado");
    expect(estadoDoTotal(com({ status: "estimado" }), true)).toBe("estimado");
  });

  it("nunca trata frete desconhecido como grátis", () => {
    expect(estadoDoTotal(com({ status: "nao_informado", valor: null }), true)).toBe("desconhecido");
    expect(estadoDoTotal(com({ status: "gratis_anunciado", valor: 0 }), true)).toBe("estimado");
  });

  it("separa sem CEP, não entrega e frete em cálculo", () => {
    expect(estadoDoTotal(com({ status: "sem_cep", valor: null }), false)).toBe("sem_cep");
    expect(estadoDoTotal(com({ status: "nao_informado", valor: null }), false)).toBe("sem_cep");
    expect(estadoDoTotal(com({ status: "nao_entrega" }), true)).toBe("nao_entrega");
    expect(estadoDoTotal(com({ status: "calculando" }), true)).toBe("calculando");
    expect(estadoDoTotal(com({ status: "calculado" }, { disponivel: false }), true)).toBe(
      "indisponivel",
    );
  });
});

describe("parecidos", () => {
  it("separa o que não tem todos os termos ou tem relevância abaixo de 90", () => {
    const certa = oferta("a:1", 100);
    const semTermo = oferta("b:1", 90, { termos_ausentes: ["inox"] });
    const fraca = oferta("c:1", 80, { relevancia: 85 });
    const vazia = oferta("d:1", 70, { termos_ausentes: [] });
    const { principais, parecidos } = separarParecidos([certa, semTermo, fraca, vazia]);
    expect(principais.map((o) => o.id)).toEqual(["a:1", "d:1"]);
    expect(parecidos.map((o) => o.id)).toEqual(["b:1", "c:1"]);
  });
});

describe("grupos do mesmo produto", () => {
  const lista = [
    oferta("a:1", 100, { grupo: "g:1" }),
    oferta("b:1", 120),
    oferta("c:1", 130, { grupo: "g:1" }),
    oferta("d:1", 140, { grupo: "g:2" }),
    oferta("e:1", 150, { grupo: "g:1" }),
  ];

  it("junta pelo grupo e mantém a ordem do ranking", () => {
    const grupos = agrupar(lista);
    expect(grupos.map((g) => g.ofertas.map((o) => o.id))).toEqual([
      ["a:1", "c:1", "e:1"],
      ["b:1"],
      ["d:1"],
    ]);
  });

  it("mostra grupos inteiros até o limite de ofertas, com pelo menos um", () => {
    const grupos = agrupar(lista);
    expect(fatiar(grupos, 4).map((g) => g.chave)).toEqual(["g:1", "b:1"]);
    expect(fatiar(grupos, 1).map((g) => g.chave)).toEqual(["g:1"]);
    expect(fatiar(grupos, 40)).toHaveLength(3);
  });
});

describe("melhor oferta", () => {
  it("escolhe o menor total confirmado e diz quanto a segunda custa a mais", () => {
    const m = melhorOferta(
      [
        oferta("a:1", 300),
        oferta("b:1", 250),
        oferta("c:1", 100, { total_exato: false, frete: { ...FRETE, status: "nao_informado" } }),
        oferta("d:1", 200),
      ],
      FILTROS_PADRAO,
      true,
    )!;
    expect(m.oferta.id).toBe("d:1");
    expect(m.motivo).toBe("confirmado");
    expect(m.comparadas).toBe(3);
    expect(m.segunda?.id).toBe("b:1");
    expect(m.diferenca).toBe(50);
  });

  it("sem CEP, o preço da versão mais barata de um anúncio não é a melhor oferta", () => {
    const semCep = { ...FRETE, status: "sem_cep" as const, valor: null };
    const m = melhorOferta(
      [
        oferta("a:1", 200, { total_exato: false, frete: semCep }),
        oferta("s:1", 50, {
          total_exato: false,
          frete: semCep,
          alertas: ["preco_varia_por_versao"],
        }),
      ],
      FILTROS_PADRAO,
      false,
    )!;
    expect(m.oferta.id).toBe("a:1");
  });

  it("ignora a segunda oferta da mesma loja na comparação", () => {
    const m = melhorOferta(
      [oferta("a:1", 100), oferta("a:2", 110), oferta("b:1", 150)],
      FILTROS_PADRAO,
      true,
    )!;
    expect(m.segunda?.id).toBe("b:1");
  });

  it("sem CEP compara o preço do produto e avisa o motivo", () => {
    const semCep = { ...FRETE, status: "sem_cep" as const, valor: null };
    const m = melhorOferta(
      [
        oferta("a:1", 300, { total_exato: false, frete: semCep }),
        oferta("b:1", 200, { total_exato: false, frete: semCep }),
      ],
      FILTROS_PADRAO,
      false,
    )!;
    expect(m.oferta.id).toBe("b:1");
    expect(m.motivo).toBe("sem_cep");
  });

  it("não recomenda nada sem total confirmado quando há CEP", () => {
    const naoInformado = { ...FRETE, status: "nao_informado" as const, valor: null };
    expect(
      melhorOferta(
        [oferta("a:1", 300, { total_exato: false, frete: naoInformado })],
        FILTROS_PADRAO,
        true,
      ),
    ).toBeNull();
    expect(melhorOferta([], FILTROS_PADRAO, true)).toBeNull();
  });
});

describe("motivo da lista vazia", () => {
  const ok = [{ situacao: "final" as const }, { situacao: "desativada" as const }];

  it("diferencia lojas fora, nada correspondente, CEP sem entrega e filtros", () => {
    const naoEntrega = { ...FRETE, status: "nao_entrega" as const };
    expect(
      motivoDoVazio({ fontes: [{ situacao: "erro" }, { situacao: "bloqueada" }], ofertas: [] }),
    ).toBe("nenhuma_loja_respondeu");
    expect(motivoDoVazio({ fontes: ok, ofertas: [] })).toBe("nada_correspondente");
    expect(motivoDoVazio({ fontes: ok, ofertas: [oferta("a:1", 1, { relevancia: 20 })] })).toBe(
      "nada_correspondente",
    );
    expect(motivoDoVazio({ fontes: ok, ofertas: [oferta("a:1", 1, { frete: naoEntrega })] })).toBe(
      "cep_nao_atendido",
    );
    expect(motivoDoVazio({ fontes: ok, ofertas: [oferta("a:1", 1)] })).toBe("filtros_escondem");
  });

  it("aponta as lojas que ficaram de fora", () => {
    const fontes = [
      { id: "a", nome: "A", situacao: "final" as const },
      { id: "b", nome: "B", situacao: "bloqueada" as const },
      { id: "c", nome: "C", situacao: "tempo_esgotado" as const },
      { id: "d", nome: "D", situacao: "desativada" as const },
    ];
    expect(lojasFora(fontes).map((f) => f.id)).toEqual(["b", "c"]);
  });
});

describe("filtro padrão", () => {
  it("começa sem exigir queda verificada", () => {
    expect(FILTROS_PADRAO.queda_verificada).toBe(false);
  });
});
