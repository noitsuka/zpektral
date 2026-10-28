import { mediana } from "@/nucleo/referencia";
import type { PontoHistorico } from "@/nucleo/tipos";

const DIAS_MINIMOS = 3;
const ESTAVEL = 0.03;
const MS_POR_DIA = 86_400_000;

type Situacao = "menor" | "abaixo" | "acima" | "estavel";

export type AvaliacaoHistorico = {
  situacao: Situacao;
  variacao: number;
  dias: number;
  menor: number;
  mediana: number;
};

function diasEntre(de: string, ate: string): number {
  return Math.round((Date.parse(`${ate}T12:00:00Z`) - Date.parse(`${de}T12:00:00Z`)) / MS_POR_DIA);
}

export function avaliarHistorico(
  atual: number,
  pontos: PontoHistorico[],
  hoje: string,
): AvaliacaoHistorico | null {
  const passado = pontos.filter((p) => p.dia < hoje);
  if (!(atual > 0) || passado.length < DIAS_MINIMOS) return null;
  const precos = passado.map((p) => p.preco);
  const menor = Math.min(...precos);
  const centro = mediana(precos)!;
  const variacao = atual / centro - 1;
  const dias = diasEntre(passado[0].dia, hoje);
  let situacao: Situacao;
  if (atual <= menor && atual < centro) situacao = "menor";
  else if (variacao <= -ESTAVEL) situacao = "abaixo";
  else if (variacao >= ESTAVEL) situacao = "acima";
  else situacao = "estavel";
  return { situacao, variacao, dias, menor, mediana: centro };
}
