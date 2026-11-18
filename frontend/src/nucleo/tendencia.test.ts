import { describe, expect, it } from "vitest";

import { avaliarHistorico, janelasDisponiveis, recortar, trechos } from "@/nucleo/tendencia";

const HOJE = "2026-10-28";
const pontos = (lista: [string, number][]) => lista.map(([dia, preco]) => ({ dia, preco }));

describe("preço atual contra o histórico da mesma loja", () => {
  const passado = pontos([
    ["2026-09-01", 30000],
    ["2026-09-10", 29500],
    ["2026-09-20", 28000],
    ["2026-10-01", 29500],
    ["2026-10-10", 29000],
    ["2026-10-20", 31000],
  ]);

  it("aponta o menor preço do período", () => {
    const a = avaliarHistorico(26000, passado, HOJE)!;
    expect(a.situacao).toBe("menor");
    expect(a.dias).toBe(57);
    expect(a.menor).toBe(28000);
    expect(a.mediana).toBe(29500);
  });

  it("empate com o menor do período também conta como menor", () => {
    expect(avaliarHistorico(28000, passado, HOJE)!.situacao).toBe("menor");
  });

  it("diz abaixo, acima ou estável em relação à mediana", () => {
    expect(avaliarHistorico(29000, passado, HOJE)!.situacao).toBe("estavel");
    const acima = avaliarHistorico(33000, passado, HOJE)!;
    expect(acima.situacao).toBe("acima");
    expect(acima.variacao).toBeCloseTo(33000 / 29500 - 1);
    const pouco = pontos([
      ["2026-09-01", 30000],
      ["2026-09-20", 25000],
      ["2026-10-01", 29000],
      ["2026-10-10", 32000],
      ["2026-10-15", 31000],
    ]);
    expect(avaliarHistorico(28000, pouco, HOJE)!.situacao).toBe("abaixo");
  });

  it("ignora o próprio dia e exige três dias de histórico", () => {
    const curto = pontos([
      ["2026-10-20", 30000],
      ["2026-10-27", 29000],
      [HOJE, 10000],
    ]);
    expect(avaliarHistorico(20000, curto, HOJE)).toBeNull();
    expect(avaliarHistorico(20000, [], HOJE)).toBeNull();
    expect(avaliarHistorico(0, passado, HOJE)).toBeNull();
  });
});

describe("janelas do gráfico de histórico", () => {
  it("oferece só as janelas que os dados preenchem", () => {
    expect(janelasDisponiveis([], HOJE)).toEqual([]);
    expect(janelasDisponiveis(pontos([["2026-10-25", 1]]), HOJE)).toEqual([7]);
    expect(janelasDisponiveis(pontos([["2026-10-15", 1]]), HOJE)).toEqual([7, 30]);
    expect(janelasDisponiveis(pontos([["2026-08-20", 1]]), HOJE)).toEqual([7, 30, 90]);
    expect(janelasDisponiveis(pontos([["2026-05-01", 1]]), HOJE)).toEqual([7, 30, 90, 180]);
  });

  it("recorta os últimos dias da janela, contando hoje", () => {
    const lista = pontos([
      ["2026-10-21", 1],
      ["2026-10-22", 2],
      ["2026-10-28", 3],
    ]);
    expect(recortar(lista, HOJE, 7).map((p) => p.dia)).toEqual(["2026-10-22", "2026-10-28"]);
  });

  it("não liga dias que não têm preço", () => {
    const lista = pontos([
      ["2026-10-01", 1],
      ["2026-10-02", 2],
      ["2026-10-05", 3],
      ["2026-10-09", 4],
      ["2026-10-10", 5],
    ]);
    expect(trechos(lista).map((t) => t.map((p) => p.preco))).toEqual([[1, 2], [3], [4, 5]]);
    expect(trechos([])).toEqual([]);
  });
});
