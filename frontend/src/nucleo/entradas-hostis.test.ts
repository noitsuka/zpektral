import { describe, expect, it } from "vitest";

import { FILTROS_PADRAO, filtrosDosParametros, filtrosParaParametros } from "@/nucleo/filtros";
import { digitosCep, ehCep, mascararCep } from "@/nucleo/formato";
import { lerRecentes } from "@/nucleo/recentes";

const PEDACOS = [
  "",
  "tv",
  "-1",
  "1e309",
  "NaN",
  "999999999999999999999",
  "<script>",
  "../",
  "%00",
  "🔥",
  "novo,usado,xpto",
  "110V,220V,380V",
  "menor_total",
  "pix",
  "\u0000",
  ",,,",
];
const CAMPOS = [
  "ordem",
  "pagamento",
  "condicao",
  "preco_min",
  "preco_max",
  "lojas",
  "voltagem",
  "voltagem_estrita",
  "frete",
  "relevancia_min",
];

function sorteador(semente: number) {
  let estado = semente;
  return () => {
    estado = (estado * 1103515245 + 12345) % 2147483648;
    return estado / 2147483648;
  };
}

describe("URL editada à mão", () => {
  const sortear = sorteador(20261027);
  const escolher = <T>(lista: T[]) => lista[Math.floor(sortear() * lista.length)];

  it("sempre vira filtros válidos e volta para a URL sem lixo", () => {
    for (let i = 0; i < 500; i++) {
      const params = new URLSearchParams();
      for (const campo of CAMPOS) if (sortear() < 0.5) params.set(campo, escolher(PEDACOS));
      const f = filtrosDosParametros(params);
      expect([
        "relevancia",
        "menor_total",
        "custo_beneficio",
        "menor_preco",
        "maior_preco",
        "entrega_rapida",
        "maior_desconto",
      ]).toContain(f.ordem);
      expect(["melhor", "pix", "avista", "parcelado"]).toContain(f.pagamento);
      expect(f.relevancia_min).toBe(FILTROS_PADRAO.relevancia_min);
      expect(f.condicao.every((c) => ["novo", "usado", "recondicionado"].includes(c))).toBe(true);
      expect(f.voltagem.every((v) => ["110V", "220V", "bivolt"].includes(v))).toBe(true);
      for (const preco of [f.preco_min, f.preco_max]) {
        expect(preco === null || (Number.isInteger(preco) && preco >= 0)).toBe(true);
      }
      const ida = filtrosParaParametros(f);
      expect(filtrosDosParametros(ida)).toEqual(f);
    }
  });
});

describe("CEP digitado de qualquer jeito", () => {
  it("nunca quebra e só aceita oito dígitos", () => {
    for (const bruto of [
      "",
      "abc",
      "01310-100",
      "01310100",
      "0131010",
      "013101000",
      "01.310-100",
      "🔥01310100",
      "\u0000",
    ]) {
      expect(() => mascararCep(bruto)).not.toThrow();
      expect(digitosCep(mascararCep(bruto)).length).toBeLessThanOrEqual(8);
    }
    expect(ehCep(mascararCep("01310100"))).toBe(true);
    expect(ehCep(mascararCep("0131010"))).toBe(false);
  });
});

describe("armazenamento local adulterado", () => {
  it("buscas recentes corrompidas viram lista vazia ou filtrada", () => {
    for (const bruto of [
      "",
      "null",
      "1",
      "[]",
      "[1,2]",
      '{"q":1}',
      '[{"q":"' + "x".repeat(500) + '"}]',
      "[[[[",
      '[{"q":"ok","cep":{"a":1}}]',
    ]) {
      expect(Array.isArray(lerRecentes(bruto))).toBe(true);
    }
    expect(lerRecentes('[{"q":"' + "x".repeat(500) + '"}]')).toEqual([]);
  });
});
