import type { Parcelamento } from "@/nucleo/tipos";

const ITERACOES = 60;
const TOLERANCIA = 1e-10;
const FOLGA_CENTAVOS = 1;

function valorPresente(parcela: number, n: number, taxa: number): number {
  return taxa === 0 ? parcela * n : (parcela * (1 - Math.pow(1 + taxa, -n))) / taxa;
}

function derivada(parcela: number, n: number, taxa: number): number {
  const fator = Math.pow(1 + taxa, -n);
  return (parcela * (n * fator * taxa - (1 - fator) * (1 + taxa))) / (taxa * taxa * (1 + taxa));
}

export function taxaMensal(aVista: number, parcela: number, n: number): number | null {
  if (!(aVista > 0) || !(parcela > 0) || !Number.isInteger(n) || n < 1) return null;
  if (parcela * n <= aVista + FOLGA_CENTAVOS * n) return 0;
  if (n === 1) return parcela / aVista - 1;
  let taxa = (2 * (parcela * n - aVista)) / (aVista * (n + 1));
  for (let i = 0; i < ITERACOES; i++) {
    const erro = valorPresente(parcela, n, taxa) - aVista;
    const passo = erro / derivada(parcela, n, taxa);
    taxa = Math.max(1e-9, taxa - passo);
    if (Math.abs(passo) < TOLERANCIA) return taxa;
  }
  return Number.isFinite(taxa) ? taxa : null;
}

export function taxaAnual(mensal: number): number {
  return Math.pow(1 + mensal, 12) - 1;
}

type CustoParcelamento = { juros: number; mensal: number; anual: number };

export function custoDoParcelamento(
  aVista: number,
  parcelamento: Parcelamento,
): CustoParcelamento | null {
  const mensal = taxaMensal(aVista, parcelamento.valor, parcelamento.parcelas);
  if (mensal === null) return null;
  return {
    juros: Math.max(0, parcelamento.valor * parcelamento.parcelas - aVista),
    mensal,
    anual: taxaAnual(mensal),
  };
}
