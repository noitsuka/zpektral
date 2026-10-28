import { describe, expect, it } from "vitest";

import {
  ROTAS,
  altitude,
  ehTerra,
  pontoNaEsfera,
  pontosDaEsfera,
  trechoDoArco,
} from "@/nucleo/globo";

describe("mapa da terra", () => {
  it.each([
    ["São Paulo", -23.55, -46.63],
    ["Manaus", -3.12, -60.02],
    ["Pequim", 39.9, 116.4],
    ["Paris", 48.85, 2.35],
    ["Saara", 23, 13],
    ["Alice Springs", -23.7, 133.88],
    ["Antártida", -85, 0],
  ])("%s é terra", (_, lat, lon) => {
    expect(ehTerra(lat, lon)).toBe(true);
  });

  it.each([
    ["Atlântico Sul", -10, -25],
    ["Pacífico", 0, -150],
    ["Índico", -20, 75],
    ["Atlântico Norte", 40, -40],
  ])("%s é mar", (_, lat, lon) => {
    expect(ehTerra(lat, lon)).toBe(false);
  });
});

describe("esfera", () => {
  it("coloca pontos na superfície de raio 1", () => {
    for (const p of pontosDaEsfera(500)) expect(Math.hypot(...p)).toBeCloseTo(1, 6);
    expect(pontosDaEsfera(500)).toHaveLength(500);
  });

  it("converte latitude e longitude em um ponto da esfera", () => {
    expect(pontoNaEsfera(90, 0)[1]).toBeCloseTo(1, 6);
    expect(Math.hypot(...pontoNaEsfera(-23.55, -46.63))).toBeCloseTo(1, 6);
  });

  it("faz o arco sair da origem, chegar ao destino e subir no meio", () => {
    const a = pontoNaEsfera(22.54, 114.06);
    const b = pontoNaEsfera(-23.55, -46.63);
    const inicio = trechoDoArco(a, b, 0);
    const fim = trechoDoArco(a, b, 1);
    const meio = trechoDoArco(a, b, 0.5);
    inicio.forEach((v, i) => expect(v).toBeCloseTo(a[i], 6));
    fim.forEach((v, i) => expect(v).toBeCloseTo(b[i], 6));
    expect(Math.hypot(...meio)).toBeGreaterThan(1.05);
  });
});

describe("rotas", () => {
  it("só ligam lugares em terra e todas chegam ao Brasil", () => {
    expect(ROTAS.length).toBeGreaterThanOrEqual(10);
    for (const r of ROTAS) {
      expect(ehTerra(r.de.lat, r.de.lon), r.de.nome).toBe(true);
      expect(ehTerra(r.para.lat, r.para.lon), r.para.nome).toBe(true);
      expect(r.para.lat).toBeLessThan(6);
      expect(r.para.lon).toBeLessThan(-34);
    }
  });
});

describe("altitude", () => {
  it.each([
    ["Himalaia", 28, 87, 3000],
    ["Altiplano andino", -16.5, -68.5, 3000],
    ["Montanhas Rochosas", 39.5, -106, 2000],
  ])("%s é alto", (_, lat, lon, minimo) => {
    expect(altitude(lat, lon)).toBeGreaterThan(minimo);
  });

  it.each([
    ["Amazônia", -3, -60],
    ["Pacífico", 0, -150],
  ])("%s é baixo", (_, lat, lon) => {
    expect(altitude(lat, lon)).toBeLessThan(300);
  });
});
