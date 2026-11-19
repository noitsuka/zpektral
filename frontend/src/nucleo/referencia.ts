import { totalPara } from "@/nucleo/filtros";
import type { Oferta, Pagamento } from "@/nucleo/tipos";

const LOJAS_MINIMAS = 3;
const DIFERENCA_MINIMA = 0.03;

// Total com frete só se compara com total com frete; sem CEP, todos são o preço do produto.
// O preço da versão mais barata de um anúncio não é o preço do produto procurado.
const comparavel = (o: Oferta) =>
  (o.total_exato || o.frete.status === "sem_cep") && !o.alertas.includes("preco_varia_por_versao");

export function mediana(valores: number[]): number | null {
  if (!valores.length) return null;
  const ordenados = [...valores].sort((a, b) => a - b);
  const meio = ordenados.length >> 1;
  return ordenados.length % 2 ? ordenados[meio] : (ordenados[meio - 1] + ordenados[meio]) / 2;
}

export function precosTipicos(ofertas: Oferta[], pagamento: Pagamento): Map<string, number> {
  const porGrupo = new Map<string, Map<string, number>>();
  for (const o of ofertas) {
    if (!o.grupo || !o.disponivel || !comparavel(o)) continue;
    const lojas = porGrupo.get(o.grupo) ?? new Map<string, number>();
    const total = totalPara(o, pagamento);
    const atual = lojas.get(o.loja.id);
    if (atual === undefined || total < atual) lojas.set(o.loja.id, total);
    porGrupo.set(o.grupo, lojas);
  }
  const tipicos = new Map<string, number>();
  for (const [grupo, lojas] of porGrupo) {
    if (lojas.size < LOJAS_MINIMAS) continue;
    const valor = mediana([...lojas.values()]);
    if (valor !== null) tipicos.set(grupo, valor);
  }
  return tipicos;
}

export function comparadoAoTipico(
  oferta: Oferta,
  pagamento: Pagamento,
  tipicos: Map<string, number>,
): number | null {
  const tipico = oferta.grupo ? tipicos.get(oferta.grupo) : undefined;
  if (!tipico || !comparavel(oferta)) return null;
  const diferenca = totalPara(oferta, pagamento) / tipico - 1;
  return Math.abs(diferenca) < DIFERENCA_MINIMA ? null : diferenca;
}
