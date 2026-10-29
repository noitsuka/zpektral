import { FILTROS_PADRAO, filtrosParaParametros } from "@/nucleo/filtros";
import type { Filtros, HistoricoOfertas, PaginaResultados } from "@/nucleo/tipos";

const URL_API = (process.env.NEXT_PUBLIC_URL_API ?? "http://localhost:8000").replace(/\/$/, "");
const LIMITE_MS = 30_000;

export class ErroApi extends Error {
  constructor(
    readonly status: number,
    mensagem: string,
    readonly tentarDepois?: number,
  ) {
    super(mensagem);
  }
}

async function obter<T>(caminho: string, signal?: AbortSignal): Promise<T> {
  let resposta: Response;
  try {
    resposta = await fetch(`${URL_API}${caminho}`, {
      signal: signal
        ? AbortSignal.any([signal, AbortSignal.timeout(LIMITE_MS)])
        : AbortSignal.timeout(LIMITE_MS),
    });
  } catch (erro) {
    if ((erro as Error).name === "AbortError" && signal?.aborted) throw erro;
    if ((erro as Error).name === "TimeoutError")
      throw new ErroApi(0, "O servidor demorou demais para responder. Tente de novo.");
    throw new ErroApi(0, "Sem conexão com o servidor. Verifique sua internet.");
  }
  const corpo = await resposta.json().catch(() => null);
  if (!resposta.ok) {
    const tentarDeNovo = Number(resposta.headers.get("retry-after")) || undefined;
    const detalhe = typeof corpo?.detail === "string" ? corpo.detail : "Algo deu errado.";
    const id = typeof corpo?.id === "string" ? corpo.id : null;
    if (id)
      throw new ErroApi(resposta.status, `${detalhe} (código ${id.slice(0, 8)})`, tentarDeNovo);
    throw new ErroApi(resposta.status, detalhe, tentarDeNovo);
  }
  return corpo as T;
}

function parametrosDaBusca(q: string, cep: string | null, filtros: Filtros): URLSearchParams {
  const params = filtrosParaParametros(filtros);
  params.set("q", q);
  if (cep) params.set("cep", cep);
  return params;
}

const TAMANHO_PAGINA = 40;

export function buscarPagina(
  q: string,
  cep: string | null,
  filtros: Filtros,
  pagina: number,
  { signal, esperaMs = 0 }: { signal?: AbortSignal; esperaMs?: number } = {},
): Promise<PaginaResultados> {
  const params = parametrosDaBusca(q, cep, filtros);
  params.set("pagina", String(pagina));
  params.set("por_pagina", String(TAMANHO_PAGINA));
  params.set("espera_ms", String(esperaMs));
  return obter<PaginaResultados>(`/busca?${params}`, signal);
}

const TODAS_AS_OFERTAS: Filtros = {
  ...FILTROS_PADRAO,
  condicao: ["novo", "recondicionado", "usado"],
};

export function urlTransmissao(q: string, cep: string | null): string {
  return `${URL_API}/busca/transmissao?${parametrosDaBusca(q, cep, TODAS_AS_OFERTAS)}`;
}

export function historicoDasOfertas(
  ids: string[],
  signal?: AbortSignal,
): Promise<HistoricoOfertas> {
  return obter<HistoricoOfertas>(
    `/historico/ofertas?${new URLSearchParams({ ids: ids.join(",") })}`,
    signal,
  );
}
