import { totalPara } from "@/nucleo/filtros";
import type { Oferta, Pagamento } from "@/nucleo/tipos";

export type Espectro = [number, number, number, number];

export const REPOUSO: Espectro = [0.7, 1, 0.15, 0.6];

const NIVEL_MIN = 0;

export function espectroDe(ofertas: Oferta[], pagamento: Pagamento): Espectro {
  const porLoja = new Map<string, number>();
  for (const o of ofertas) {
    if (!o.total_exato || o.relevancia < 90) continue;
    const total = totalPara(o, pagamento);
    const atual = porLoja.get(o.loja.id);
    if (atual === undefined || total < atual) porLoja.set(o.loja.id, total);
  }
  const totais = [...porLoja.values()].sort((a, b) => a - b);
  if (totais.length < 2) return REPOUSO;

  const baixo = totais[0];
  const alto = totais[totais.length - 1];
  const em = (q: number) => totais[Math.round(q * (totais.length - 1))];
  const nivel = (preco: number) =>
    alto === baixo ? 1 : NIVEL_MIN + ((preco - baixo) / (alto - baixo)) * (1 - NIVEL_MIN);

  return [nivel(em(2 / 3)), nivel(alto), nivel(baixo), nivel(em(1 / 3))];
}
