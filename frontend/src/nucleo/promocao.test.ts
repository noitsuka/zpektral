import { describe, expect, it } from "vitest";

import { avaliarPromocao } from "@/nucleo/promocao";
import type { Oferta, PontoHistorico } from "@/nucleo/tipos";

const HOJE = "2026-11-17";

function oferta(extra: Partial<Oferta> = {}): Oferta {
  return {
    id: "a:1",
    preco: 26000,
    preco_original: null,
    preco_pix: null,
    ...extra,
  } as Oferta;
}

const serie = (lista: [string, number][]): PontoHistorico[] =>
  lista.map(([dia, preco]) => ({ dia, preco }));

// mediana 29.500, menor 28.000, maior 31.000, 77 dias
const HABITUAL = serie([
  ["2026-09-01", 30000],
  ["2026-09-20", 28000],
  ["2026-10-10", 29000],
  ["2026-10-20", 31000],
]);

const tipos = (o: Oferta, s?: PontoHistorico[]) =>
  avaliarPromocao(o, s, HOJE).selos.map((x) => x.tipo);

describe("selos de promoção com evidência", () => {
  it("mostra o desconto anunciado como da loja e o confirma pelo histórico", () => {
    const p = avaliarPromocao(oferta({ preco_original: 30500 }), HABITUAL, HOJE);
    expect(p.selos.map((s) => s.tipo)).toEqual(["menor_em_dias", "anunciado"]);
    const anunciado = p.selos.find((s) => s.tipo === "anunciado")!;
    expect(anunciado.texto).toMatch(/anunciado pela loja/);
    expect(anunciado.evidencia).toContain("R$ 305,00");
    expect(p.economiaVerificada).toBeCloseTo(1 - 26000 / 29500);
    expect(p.quedaVerificada).toBe(true);
  });

  it("alerta quando o preço de antes nunca foi visto nesta loja", () => {
    const p = avaliarPromocao(oferta({ preco_original: 45000 }), HABITUAL, HOJE);
    const alerta = p.selos.find((s) => s.tipo === "sem_respaldo")!;
    expect(alerta.tom).toBe("alerta");
    expect(alerta.evidencia).toContain("R$ 450,00");
    expect(alerta.evidencia).toContain("R$ 310,00");
  });

  it("alerta quando o preço de hoje não está abaixo do habitual", () => {
    const p = avaliarPromocao(oferta({ preco: 29500, preco_original: 31000 }), HABITUAL, HOJE);
    expect(p.selos.map((s) => s.tipo)).toEqual(["anunciado", "sem_respaldo"]);
    expect(p.selos[1].evidencia).toContain("R$ 295,00");
    expect(p.economiaVerificada).toBe(0);
    expect(p.quedaVerificada).toBe(false);
  });

  it("avisa que falta histórico para confirmar o desconto anunciado", () => {
    expect(tipos(oferta({ preco_original: 35000 }))).toEqual([
      "anunciado",
      "historico_insuficiente",
    ]);
    expect(tipos(oferta({ preco_original: 35000 }), HABITUAL.slice(0, 2))).toEqual([
      "anunciado",
      "historico_insuficiente",
    ]);
    expect(avaliarPromocao(oferta({ preco_original: 35000 }), [], HOJE).economiaVerificada).toBe(0);
  });

  it("não inventa desconto sem preço de antes nem histórico", () => {
    expect(avaliarPromocao(oferta(), undefined, HOJE)).toEqual({
      selos: [],
      economiaVerificada: 0,
      quedaVerificada: false,
    });
    expect(tipos(oferta({ preco_original: 26000 }))).toEqual([]);
  });

  it("mostra o desconto do Pix sem somar com a queda do histórico", () => {
    const p = avaliarPromocao(oferta({ preco: 28500, preco_pix: 25650 }), HABITUAL, HOJE);
    expect(p.selos.map((s) => s.tipo)).toEqual(["abaixo_do_habitual", "pix"]);
    expect(p.selos[1].texto).toBe("R$ 28,50 a menos no Pix");
    expect(p.economiaVerificada).toBeCloseTo(1 - 28500 / 29500);
  });

  it("diz quando o preço está acima do habitual desta loja", () => {
    const p = avaliarPromocao(oferta({ preco: 33000 }), HABITUAL, HOJE);
    expect(p.selos.map((s) => [s.tipo, s.tom])).toEqual([["acima_do_habitual", "alerta"]]);
    expect(p.quedaVerificada).toBe(false);
  });

  it("lista as promoções que a loja informa, no máximo três e sem repetir", () => {
    const p = avaliarPromocao(
      oferta({
        promocoes: ["Semana do Cliente", " ", "Semana do Cliente", "Frete Turbo", "A", "B"],
      }),
      undefined,
      HOJE,
    );
    expect(p.selos.map((s) => s.texto)).toEqual(["Semana do Cliente", "Frete Turbo", "A"]);
    expect(p.selos.every((s) => s.evidencia === "informada pela loja")).toBe(true);
  });

  it("mostra a validade só quando a loja informa e ela ainda não passou", () => {
    const valida = avaliarPromocao(oferta({ preco_valido_ate: "2026-11-20" }), undefined, HOJE);
    expect(valida.selos.map((s) => s.tipo)).toEqual(["validade"]);
    expect(valida.selos[0].texto).toMatch(/20/);
    expect(tipos(oferta({ preco_valido_ate: "2026-11-16" }))).toEqual([]);
    expect(tipos(oferta({ preco_valido_ate: null }))).toEqual([]);
    expect(tipos(oferta({ preco_valido_ate: "data ruim" }))).toEqual([]);
  });
});
