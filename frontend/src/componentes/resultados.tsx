"use client";

import { ChevronDown, MapPin, RotateCw } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { BotaoFiltros, ChipsFiltros } from "@/componentes/painel-filtros";
import { Logo, Simbolo } from "@/componentes/logo";
import { LinhaOferta } from "@/componentes/linha-oferta";
import { filtrarAoVivo, rebaixarMuitoAbaixo, usarPaginaDoServidor } from "@/nucleo/ao-vivo";
import { comparadoAoTipico, precosTipicos } from "@/nucleo/referencia";
import { FormularioBusca } from "@/componentes/formulario-busca";
import { StatusBusca } from "@/componentes/status-busca";
import { useAtalhoBusca } from "@/ganchos/use-atalho-busca";
import { useHistoricoOfertas } from "@/ganchos/use-historico-ofertas";
import { useFaviconVivo } from "@/ganchos/use-favicon-vivo";
import { useTransmissaoBusca } from "@/ganchos/use-transmissao-busca";
import { ErroApi, buscarPagina } from "@/nucleo/api";
import {
  filtrosDosParametros,
  facetasDe,
  filtrosParaParametros,
  ocultasPorCondicao,
  ORDENS,
  PAGAMENTOS,
} from "@/nucleo/filtros";
import { hojeEmBrasilia, quantidade, mascararCep, plural } from "@/nucleo/formato";
import { REPOUSO, espectroDe } from "@/nucleo/espectro";
import { todasOfertas, rankingAoVivo, progresso } from "@/nucleo/transmissao";
import type { Filtros, Oferta, PaginaResultados } from "@/nucleo/tipos";

function useAtrasado<T>(valor: T, ms: number): T {
  const [atual, setAtual] = useState(valor);
  useEffect(() => {
    const id = setTimeout(() => setAtual(valor), ms);
    return () => clearTimeout(id);
  }, [valor, ms]);
  return atual;
}

const LIMITE_AO_VIVO = 40;

export function Resultados() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const q = (params.get("q") ?? "").trim();
  const cep = params.get("cep");
  const [filtros, setEstadoFiltros] = useState(() => filtrosDosParametros(params));
  const assentado = useAtrasado(filtros, 250);

  const [tentativa, setTentativa] = useState(0);
  const transmissao = useTransmissaoBusca(q, cep, filtros, tentativa);
  const [pagina, setPagina] = useState<PaginaResultados | null>(null);
  const [extra, setExtra] = useState<Oferta[]>([]);
  const [proximaPagina, setProximaPagina] = useState(2);
  const [erro, setErro] = useState<string | null>(null);
  const [carregandoMais, setCarregandoMais] = useState(false);
  useAtalhoBusca();
  const sentinela = useRef<HTMLDivElement>(null);
  const [preso, setPreso] = useState(false);

  useEffect(() => {
    const elemento = sentinela.current;
    if (!elemento) return;
    const observador = new IntersectionObserver(
      ([entrada]) => setPreso(!entrada.isIntersecting && entrada.boundingClientRect.top < 120),
      { rootMargin: "-80px 0px 0px 0px" },
    );
    observador.observe(elemento);
    return () => observador.disconnect();
  }, []);
  const cabecalho = useRef<HTMLElement>(null);
  const requisicao = useRef<AbortController | null>(null);

  const setFiltros = useCallback(
    (proximo: Filtros) => {
      setEstadoFiltros(proximo);
      const consulta = filtrosParaParametros(proximo, new URLSearchParams(window.location.search));
      router.replace(`${pathname}?${consulta}`, { scroll: false });
    },
    [pathname, router],
  );

  const transmissaoTerminou = transmissao.fase === "concluida";
  const transmissaoFalhou = transmissao.fase === "falhou";
  useEffect(() => {
    if (!q || !(transmissaoTerminou || transmissaoFalhou)) return;
    requisicao.current?.abort();
    const controlador = new AbortController();
    requisicao.current = controlador;
    const pedir = (esperaMs: number) =>
      buscarPagina(q, cep, assentado, 1, { signal: controlador.signal, esperaMs });
    pedir(transmissaoFalhou ? 15000 : 0)
      .then((resultado) => (resultado.pronto ? resultado : pedir(15000)))
      .then((resultado) => {
        setPagina(resultado);
        setExtra([]);
        setProximaPagina(2);
        setErro(null);
      })
      .catch((e: Error) => {
        if (e.name !== "AbortError") setErro(e instanceof ErroApi ? e.message : "Algo deu errado.");
      });
    return () => controlador.abort();
  }, [q, cep, assentado, transmissaoTerminou, transmissaoFalhou]);

  const transmitido = useMemo(() => todasOfertas(transmissao), [transmissao]);
  const aoVivo = useMemo(
    () => rankingAoVivo(filtrarAoVivo(rebaixarMuitoAbaixo(transmitido), filtros), filtros),
    [transmitido, filtros],
  );
  const final = usarPaginaDoServidor(pagina, aoVivo.length) ? pagina : null;
  const ofertas = final ? [...final.ofertas, ...extra] : aoVivo.slice(0, LIMITE_AO_VIVO);
  const tipicos = useMemo(
    () => precosTipicos(transmitido, filtros.pagamento),
    [transmitido, filtros.pagamento],
  );
  const varrendo = transmissao.fase === "transmitindo";
  const terminou = !varrendo && transmissao.fase !== "parada";
  const historico = useHistoricoOfertas(
    ofertas.map((o) => o.id),
    terminou,
  );
  const hoje = useMemo(() => hojeEmBrasilia(), []);
  const espectro = useMemo(
    () => (varrendo ? REPOUSO : espectroDe(transmitido, filtros.pagamento)),
    [varrendo, transmitido, filtros.pagamento],
  );
  useFaviconVivo(espectro, varrendo);
  const { responderam, total } = progresso(transmissao);
  const endereco = transmissao.inicio?.endereco ?? final?.endereco ?? null;
  const facetasAoVivo = useMemo(() => facetasDe(transmitido, filtros), [transmitido, filtros]);
  const facetas = final?.facetas ?? transmissao.fim?.facetas ?? facetasAoVivo;
  const totalResultados = final?.total ?? aoVivo.length;

  async function carregarMais() {
    if (!final) return;
    setCarregandoMais(true);
    try {
      const signal = requisicao.current?.signal;
      const proximo = await buscarPagina(q, cep, assentado, proximaPagina, { signal });
      if (signal?.aborted) return;
      setExtra((anterior) => [...anterior, ...proximo.ofertas]);
      setProximaPagina((n) => n + 1);
    } catch (e) {
      if ((e as Error).name !== "AbortError")
        setErro(e instanceof ErroApi ? e.message : "Algo deu errado.");
    } finally {
      setCarregandoMais(false);
    }
  }

  useEffect(() => {
    const elemento = cabecalho.current;
    if (!elemento) return;
    const medir = () =>
      document.documentElement.style.setProperty(
        "--altura-cabecalho",
        `${elemento.getBoundingClientRect().height}px`,
      );
    medir();
    const observador = new ResizeObserver(medir);
    observador.observe(elemento);
    return () => observador.disconnect();
  }, []);

  const ocultas = ocultasPorCondicao(facetas, filtros);

  const podeCarregarMais = final !== null && final.ofertas.length + extra.length < final.total;

  return (
    <div className="min-h-dvh">
      <header
        ref={cabecalho}
        className="sticky top-0 z-30 border-b border-traco bg-fundo/92 backdrop-blur-md"
      >
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3 sm:gap-6 sm:px-6">
          <Logo compacto espectro={espectro} />
          <div className="min-w-0 flex-1">
            <FormularioBusca
              key={`${q}-${cep}`}
              consultaInicial={q}
              cepInicial={cep ? mascararCep(cep) : undefined}
            />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 pt-6 pb-24 sm:px-6">
        <section className="animate-surgir">
          <div className="min-w-0">
            <h1 className="text-[1.75rem] leading-tight font-bold tracking-[-0.03em] break-words sm:text-4xl">
              {q}
            </h1>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
              {cep ? (
                <span className="inline-flex items-center gap-1.5 rounded-peca border border-traco px-2.5 py-1 text-apagado">
                  <MapPin className="size-3.5" aria-hidden />
                  {endereco?.cidade ? `${endereco.cidade}, ${endereco.uf}` : "CEP"}
                  <span className="font-mono text-tenue">{mascararCep(cep)}</span>
                </span>
              ) : (
                <span className="rounded-peca border border-alerta/30 bg-alerta-suave px-2.5 py-1 text-alerta">
                  Sem CEP: os totais não incluem frete
                </span>
              )}
            </div>
          </div>
        </section>

        <div className="mt-5">
          <StatusBusca responderam={responderam} total={total} terminou={terminou} />
        </div>

        {(erro || transmissao.erro) && !final && (
          <div
            role="alert"
            className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-quadro border border-falha/30 bg-falha-suave p-4 text-sm"
          >
            <span>{erro ?? transmissao.erro}</span>
            <button
              type="button"
              onClick={() => {
                setPagina(null);
                setErro(null);
                setTentativa((n) => n + 1);
              }}
              className="inline-flex items-center gap-1.5 rounded-peca border border-traco px-3 py-1.5 text-xs hover:border-tinta/25"
            >
              <RotateCw className="size-3.5" aria-hidden /> Tentar de novo
            </button>
          </div>
        )}

        <div ref={sentinela} aria-hidden className="mt-6 h-px" />
        <div
          className={`sticky top-[var(--altura-cabecalho,4.5rem)] z-20 -mx-4 border-b border-traco bg-fundo/92 px-4 py-2.5 backdrop-blur-md transition-shadow duration-300 sm:-mx-6 sm:px-6 ${
            preso ? "preso" : ""
          }`}
        >
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs text-apagado">
              <span className="font-mono text-tinta">{quantidade(totalResultados)}</span>{" "}
              {totalResultados === 1 ? "oferta" : "ofertas"}
            </p>

            <div className="ml-auto flex items-center gap-2">
              <Seletor
                rotulo="Pagar com"
                valor={filtros.pagamento}
                opcoes={PAGAMENTOS}
                aoMudar={(valor) => setFiltros({ ...filtros, pagamento: valor })}
              />
              <Seletor
                rotulo="Ordenar"
                valor={filtros.ordem}
                opcoes={ORDENS}
                aoMudar={(valor) => setFiltros({ ...filtros, ordem: valor })}
              />
              <BotaoFiltros filtros={filtros} facetas={facetas} onChange={setFiltros} />
            </div>
          </div>
        </div>

        <div className="mt-3 flex flex-col gap-2">
          <ChipsFiltros filtros={filtros} facetas={facetas} onChange={setFiltros} />
          {ocultas > 0 && (
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-peca border border-traco bg-painel/60 px-3 py-2 text-xs text-apagado">
              <span>
                {plural(
                  ocultas,
                  "oferta usada ou recondicionada está escondida",
                  "ofertas usadas ou recondicionadas estão escondidas",
                )}
                .
              </span>
              <button
                type="button"
                onClick={() =>
                  setFiltros({ ...filtros, condicao: ["novo", "recondicionado", "usado"] })
                }
                className="font-medium text-ouro underline-offset-4 hover:underline"
              >
                Mostrar também
              </button>
            </p>
          )}
        </div>

        <div className="mt-3">
          <div className="overflow-hidden rounded-quadro border border-traco bg-painel/40">
            {ofertas.length ? (
              ofertas.map((o, i) => (
                <LinhaOferta
                  key={o.id}
                  oferta={o}
                  pagamento={filtros.pagamento}
                  cep={cep || null}
                  diferencaDoTipico={comparadoAoTipico(o, filtros.pagamento, tipicos)}
                  historico={historico[o.id]}
                  hoje={hoje}
                  indice={i}
                />
              ))
            ) : (
              <Vazio fase={transmissao.fase} />
            )}
          </div>

          {podeCarregarMais && (
            <button
              type="button"
              onClick={carregarMais}
              disabled={carregandoMais}
              className="mx-auto mt-6 block rounded-peca border border-traco px-5 py-2.5 text-sm text-apagado transition-colors hover:border-tinta/25 hover:text-tinta disabled:opacity-50"
            >
              {carregandoMais
                ? "Carregando"
                : `Mais ofertas (${plural(final!.total - ofertas.length, "restante", "restantes")})`}
            </button>
          )}
        </div>
      </main>
    </div>
  );
}

function Seletor<T extends string>({
  rotulo,
  valor,
  opcoes,
  aoMudar,
}: {
  rotulo: string;
  valor: T;
  opcoes: { valor: T; rotulo: string }[];
  aoMudar: (valor: T) => void;
}) {
  return (
    <label className="relative inline-flex h-9 items-center rounded-peca border border-traco text-xs transition-colors focus-within:border-ouro/50 hover:border-tinta/25">
      <span className="hidden pl-3 text-tenue md:inline">{rotulo}</span>
      <select
        value={valor}
        onChange={(e) => aoMudar(e.target.value as T)}
        aria-label={rotulo}
        className="h-full max-w-[9.5rem] cursor-pointer appearance-none bg-transparent pr-7 pl-3 font-medium text-tinta outline-none md:pl-1.5"
      >
        {opcoes.map((o) => (
          <option key={o.valor} value={o.valor} className="bg-painel">
            {o.rotulo}
          </option>
        ))}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-2 size-3.5 text-tenue"
        aria-hidden
      />
    </label>
  );
}

function Vazio({ fase }: { fase: string }) {
  if (fase === "transmitindo" || fase === "parada") {
    return (
      <div className="space-y-px">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="flex gap-4 border-b border-traco p-4">
            <div className="esqueleto size-16 rounded-peca" />
            <div className="flex-1 space-y-2 pt-1">
              <div className="esqueleto h-3 w-3/4 rounded-peca" />
              <div className="esqueleto h-3 w-1/3 rounded-peca" />
            </div>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="flex flex-col items-center p-10 text-center">
      <Simbolo tamanho={40} className="mb-4 opacity-60" />
      <p className="font-medium">Nenhuma oferta com esses filtros.</p>
      <p className="mt-1 text-sm text-tenue">
        Abra os filtros e tire o limite de preço ou inclua usados.
      </p>
    </div>
  );
}
