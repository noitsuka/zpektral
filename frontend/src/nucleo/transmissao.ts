import { totalPara } from "@/nucleo/filtros";
import type {
  EventoLote,
  EventoFim,
  EventoFalhaFonte,
  Filtros,
  EventoInicio,
  Oferta,
  InfoFonte,
} from "@/nucleo/tipos";

type EstadoFonte = "aguardando" | "catalogo" | "final" | "erro" | "tempo_esgotado" | "desativada";

type CelulaFonte = {
  id: string;
  nome: string;
  situacao: EstadoFonte;
  tempo_ms: number | null;
  ofertas: number;
  melhor_total: number | null;
};

type EstadoTransmissao = {
  fase: "parada" | "transmitindo" | "concluida" | "falhou";
  inicio: EventoInicio | null;
  fontes: CelulaFonte[];
  ofertas: Record<string, Oferta[]>;
  fim: EventoFim | null;
  erro: string | null;
};

export type AcaoTransmissao =
  | { tipo: "iniciar" }
  | { tipo: "inicio"; dados: EventoInicio }
  | { tipo: "lote"; dados: EventoLote }
  | { tipo: "falha_fonte"; dados: EventoFalhaFonte }
  | { tipo: "fim"; dados: EventoFim }
  | { tipo: "falha"; mensagem: string };

export const INICIAL: EstadoTransmissao = {
  fase: "parada",
  inicio: null,
  fontes: [],
  ofertas: {},
  fim: null,
  erro: null,
};

function celula(info: InfoFonte): CelulaFonte {
  return {
    id: info.id,
    nome: info.nome,
    situacao: info.ativa ? "aguardando" : "desativada",
    tempo_ms: null,
    ofertas: 0,
    melhor_total: null,
  };
}

function atualizarCelula(
  fontes: CelulaFonte[],
  id: string,
  alteracao: Partial<CelulaFonte>,
): CelulaFonte[] {
  return fontes.map((s) => (s.id === id ? { ...s, ...alteracao } : s));
}

export function reduzir(estado: EstadoTransmissao, acao: AcaoTransmissao): EstadoTransmissao {
  switch (acao.tipo) {
    case "iniciar":
      return { ...INICIAL, fase: "transmitindo" };
    case "inicio":
      return { ...estado, inicio: acao.dados, fontes: acao.dados.fontes.map(celula) };
    case "lote": {
      const { fonte, fase, ofertas, melhor_total } = acao.dados;
      return {
        ...estado,
        ofertas: { ...estado.ofertas, [fonte.id]: ofertas },
        fontes: atualizarCelula(estado.fontes, fonte.id, {
          situacao: fase === "final" ? "final" : "catalogo",
          tempo_ms: fonte.tempo_ms,
          ofertas: ofertas.length,
          melhor_total,
        }),
      };
    }
    case "falha_fonte": {
      const { fonte } = acao.dados;
      const resto = { ...estado.ofertas };
      delete resto[fonte.id];
      return {
        ...estado,
        ofertas: resto,
        fontes: atualizarCelula(estado.fontes, fonte.id, {
          situacao: fonte.status === "tempo_esgotado" ? "tempo_esgotado" : "erro",
          tempo_ms: fonte.tempo_ms,
          ofertas: 0,
        }),
      };
    }
    case "fim": {
      const grupos = acao.dados.grupos_por_oferta;
      const ofertas = Object.fromEntries(
        Object.entries(estado.ofertas).map(([id, lista]) => [
          id,
          lista.map((o) =>
            grupos[o.id] && grupos[o.id] !== o.grupo ? { ...o, grupo: grupos[o.id] } : o,
          ),
        ]),
      );
      return { ...estado, fase: "concluida", fim: acao.dados, ofertas };
    }
    case "falha":
      return { ...estado, fase: "falhou", erro: acao.mensagem };
  }
}

export function todasOfertas(estado: EstadoTransmissao): Oferta[] {
  return Object.values(estado.ofertas).flat();
}

const SEM_DIAS = Number.POSITIVE_INFINITY;

function certeza(o: Oferta): number {
  if (o.total_exato) return 0;
  return o.frete.status === "gratis_anunciado" ? 1 : 2;
}

function desconto(o: Oferta): number {
  return o.preco_original ? 1 - o.melhor_preco / o.preco_original : 0;
}

export function rankingAoVivo(ofertas: Oferta[], filtros: Filtros): Oferta[] {
  const pag = filtros.pagamento;
  const total = (o: Oferta) => totalPara(o, pag);
  const chaves: Record<Filtros["ordem"], (o: Oferta) => number[]> = {
    relevancia: (o) => [-o.relevancia, total(o), certeza(o)],
    menor_total: (o) => [total(o), certeza(o), -o.relevancia],
    custo_beneficio: (o) => [total(o), o.total_exato ? 0 : 1, -o.relevancia],
    menor_preco: (o) => [total(o) - (o.frete.valor ?? 0), -o.relevancia],
    maior_preco: (o) => [-(total(o) - (o.frete.valor ?? 0)), -o.relevancia],
    entrega_rapida: (o) => [o.frete.prazo_dias ?? SEM_DIAS, total(o)],
    maior_desconto: (o) => [-desconto(o), total(o)],
  };
  const chave = chaves[filtros.ordem];
  return [...ofertas]
    .map((o) => [chave(o), o] as const)
    .sort(([a], [b]) => {
      for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] - b[i];
      return 0;
    })
    .map(([, o]) => o);
}

export function progresso(estado: EstadoTransmissao): { responderam: number; total: number } {
  const ativo = estado.fontes.filter((s) => s.situacao !== "desativada");
  const responderam = ativo.filter((s) => s.situacao !== "aguardando" && s.situacao !== "catalogo");
  return { responderam: responderam.length, total: ativo.length };
}

const RELEVANCIA_MIN_DESTAQUE = 90;

export function maisBarata(ofertas: Oferta[], filtros: Filtros): Oferta | null {
  let melhor: Oferta | null = null;
  for (const o of ofertas) {
    if (!o.total_exato || o.relevancia < RELEVANCIA_MIN_DESTAQUE) continue;
    if (o.alertas.includes("preco_fora_da_curva")) continue;
    if (!melhor || totalPara(o, filtros.pagamento) < totalPara(melhor, filtros.pagamento))
      melhor = o;
  }
  return melhor;
}
