import { FILTROS_PADRAO, totalPara } from "@/nucleo/filtros";
import { maisBarata, type EstadoFonte } from "@/nucleo/transmissao";
import type { Filtros, Oferta } from "@/nucleo/tipos";

export type EstadoTotal =
  | "confirmado"
  | "estimado"
  | "desconhecido"
  | "sem_cep"
  | "nao_entrega"
  | "indisponivel"
  | "calculando";

export function estadoDoTotal(o: Oferta, temCep: boolean): EstadoTotal {
  if (!o.disponivel) return "indisponivel";
  if (o.frete.status === "nao_entrega") return "nao_entrega";
  if (o.total_exato) return "confirmado";
  if (o.frete.status === "calculando") return "calculando";
  if (!temCep || o.frete.status === "sem_cep") return "sem_cep";
  if (o.frete.status === "nao_informado") return "desconhecido";
  return "estimado";
}

const RELEVANCIA_PRINCIPAL = 90;

export function separarParecidos(ofertas: Oferta[]): { principais: Oferta[]; parecidos: Oferta[] } {
  const principais: Oferta[] = [];
  const parecidos: Oferta[] = [];
  for (const o of ofertas) {
    const parecido = (o.termos_ausentes?.length ?? 0) > 0 || o.relevancia < RELEVANCIA_PRINCIPAL;
    (parecido ? parecidos : principais).push(o);
  }
  return { principais, parecidos };
}

export type Grupo = { chave: string; ofertas: Oferta[] };

export function agrupar(ofertas: Oferta[]): Grupo[] {
  const grupos = new Map<string, Oferta[]>();
  for (const o of ofertas) {
    const chave = o.grupo ?? o.id;
    const lista = grupos.get(chave);
    if (lista) lista.push(o);
    else grupos.set(chave, [o]);
  }
  return [...grupos].map(([chave, lista]) => ({ chave, ofertas: lista }));
}

export function fatiar(grupos: Grupo[], limite: number): Grupo[] {
  const saida: Grupo[] = [];
  let soma = 0;
  for (const g of grupos) {
    if (saida.length && soma + g.ofertas.length > limite) break;
    saida.push(g);
    soma += g.ofertas.length;
  }
  return saida;
}

export type MelhorOferta = {
  oferta: Oferta;
  motivo: "confirmado" | "sem_cep";
  comparadas: number;
  segunda: Oferta | null;
  diferenca: number | null;
};

function elegivel(o: Oferta): boolean {
  return (
    o.relevancia >= RELEVANCIA_PRINCIPAL &&
    o.disponivel &&
    o.frete.status !== "nao_entrega" &&
    !o.alertas.includes("preco_fora_da_curva")
  );
}

export function melhorOferta(
  principais: Oferta[],
  filtros: Filtros,
  temCep: boolean,
): MelhorOferta | null {
  const total = (o: Oferta) => totalPara(o, filtros.pagamento);
  const menor = (lista: Oferta[]) =>
    lista.reduce<Oferta | null>((m, o) => (!m || total(o) < total(m) ? o : m), null);
  const conjunto = principais.filter((o) => elegivel(o) && (!temCep || o.total_exato));
  const oferta = temCep ? maisBarata(conjunto, filtros) : menor(conjunto);
  if (!oferta) return null;
  const segunda = menor(conjunto.filter((o) => o.loja.id !== oferta.loja.id));
  return {
    oferta,
    motivo: temCep ? "confirmado" : "sem_cep",
    comparadas: conjunto.length,
    segunda,
    diferenca: segunda ? total(segunda) - total(oferta) : null,
  };
}

export type MotivoVazio =
  "nenhuma_loja_respondeu" | "nada_correspondente" | "cep_nao_atendido" | "filtros_escondem";

const FORA = new Set<EstadoFonte>(["erro", "tempo_esgotado", "bloqueada"]);

export function lojasFora<T extends { situacao: EstadoFonte }>(fontes: T[]): T[] {
  return fontes.filter((f) => FORA.has(f.situacao));
}

export function motivoDoVazio({
  fontes,
  ofertas,
}: {
  fontes: { situacao: EstadoFonte }[];
  ofertas: Oferta[];
}): MotivoVazio {
  if (!fontes.some((f) => f.situacao === "final" || f.situacao === "catalogo"))
    return "nenhuma_loja_respondeu";
  const relevantes = ofertas.filter(
    (o) => o.relevancia >= FILTROS_PADRAO.relevancia_min && o.disponivel,
  );
  if (!relevantes.length) return "nada_correspondente";
  if (relevantes.every((o) => o.frete.status === "nao_entrega")) return "cep_nao_atendido";
  return "filtros_escondem";
}
