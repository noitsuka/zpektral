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

export const JANELAS = [7, 30, 90, 180] as const;

export function janelasDisponiveis(pontos: PontoHistorico[], hoje: string): number[] {
  if (!pontos.length) return [];
  const alcance = diasEntre(pontos[0].dia, hoje);
  return JANELAS.filter((janela, i) => i === 0 || alcance >= JANELAS[i - 1]);
}

export function recortar(pontos: PontoHistorico[], hoje: string, janela: number): PontoHistorico[] {
  return pontos.filter((p) => diasEntre(p.dia, hoje) < janela);
}

export function trechos(pontos: PontoHistorico[]): PontoHistorico[][] {
  const saida: PontoHistorico[][] = [];
  for (const p of pontos) {
    const atual = saida.at(-1);
    if (atual && diasEntre(atual.at(-1)!.dia, p.dia) === 1) atual.push(p);
    else saida.push([p]);
  }
  return saida;
}
