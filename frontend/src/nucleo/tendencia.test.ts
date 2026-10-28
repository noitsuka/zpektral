import { describe, expect, it } from "vitest";

import { avaliarHistorico } from "@/nucleo/tendencia";

const HOJE = "2026-10-28";
const pontos = (lista: [string, number][]) => lista.map(([dia, preco]) => ({ dia, preco }));

describe("preço atual contra o histórico da mesma loja", () => {
  const passado = pontos([
    ["2026-09-01", 30000],
    ["2026-09-20", 28000],
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
      ["2026-10-10", 32000],
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
