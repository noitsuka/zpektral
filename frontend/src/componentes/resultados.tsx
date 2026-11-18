"use client";

import { ChevronDown, MapPin, RotateCw } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { FormularioBusca, ID_CAMPO_CEP } from "@/componentes/formulario-busca";
import type { Contexto } from "@/componentes/linha-oferta";
import { Logo } from "@/componentes/logo";
import { BotaoFiltros, ChipsFiltros, PainelFiltros } from "@/componentes/painel-filtros";
import { StatusBusca } from "@/componentes/status-busca";
import {
  CartaoGrupo,
  EsqueletoGrupos,
  EsqueletoMelhor,
  EtiquetaMelhor,
  Vazio,
} from "@/componentes/vitrine";
import { useAtalhoBusca } from "@/ganchos/use-atalho-busca";
import { useFaviconVivo } from "@/ganchos/use-favicon-vivo";
import { useHistoricoOfertas } from "@/ganchos/use-historico-ofertas";
import { useTransmissaoBusca } from "@/ganchos/use-transmissao-busca";
import { filtrarAoVivo, rebaixarMuitoAbaixo } from "@/nucleo/ao-vivo";
import { ErroApi, buscarPagina } from "@/nucleo/api";
import { REPOUSO, espectroDe } from "@/nucleo/espectro";
import {
  FILTROS_PADRAO,
  ORDENS,
  ORDENS_LOCAIS,
  facetasDe,
  filtrosDosParametros,
  filtrosParaParametros,
  ocultasPorCondicao,
} from "@/nucleo/filtros";
import { hojeEmBrasilia, mascararCep, plural } from "@/nucleo/formato";
import { avaliarPromocao, type Promocao } from "@/nucleo/promocao";
import { comparadoAoTipico, precosTipicos } from "@/nucleo/referencia";
import { rankingAoVivo, todasOfertas } from "@/nucleo/transmissao";
import type { Filtros, Oferta, PaginaResultados } from "@/nucleo/tipos";
import { agrupar, fatiar, melhorOferta, motivoDoVazio, separarParecidos } from "@/nucleo/vitrine";

function useAtrasado<T>(valor: T, ms: number): T {
  const [atual, setAtual] = useState(valor);
  useEffect(() => {
    const id = setTimeout(() => setAtual(valor), ms);
    return () => clearTimeout(id);
  }, [valor, ms]);
  return atual;
}

function useAgora(ms: number): Date {
  const [agora, setAgora] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setAgora(new Date()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return agora;
}

const POR_VEZ = 40;
const ESPERA_MS = 15_000;

function focarCep() {
  const campo = document.getElementById(ID_CAMPO_CEP) as HTMLInputElement | null;
  campo?.focus();
  campo?.select();
}

export function Resultados() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const q = (params.get("q") ?? "").trim();
  const cep = params.get("cep") || null;
  const [filtros, setEstadoFiltros] = useState(() => filtrosDosParametros(params));
  const assentado = useAtrasado(filtros, 250);

  const [tentativa, setTentativa] = useState(0);
  const transmissao = useTransmissaoBusca(q, cep, tentativa);
  const [pagina, setPagina] = useState<PaginaResultados | null>(null);
  const [extra, setExtra] = useState<Oferta[]>([]);
  const [proximaPagina, setProximaPagina] = useState(2);
  const [visiveis, setVisiveis] = useState({ chave: "", quantas: POR_VEZ });
  const [erro, setErro] = useState<string | null>(null);
  const [carregandoMais, setCarregandoMais] = useState(false);
  const cabecalho = useRef<HTMLElement>(null);
  const requisicao = useRef<AbortController | null>(null);
  const agora = useAgora(30_000);
  const hoje = useMemo(() => hojeEmBrasilia(), []);
  useAtalhoBusca();

  const setFiltros = useCallback(
    (proximo: Filtros) => {
      setEstadoFiltros(proximo);
      const consulta = filtrosParaParametros(proximo, new URLSearchParams(window.location.search));
      router.replace(`${pathname}?${consulta}`, { scroll: false });
    },
    [pathname, router],
  );

  const transmissaoFalhou = transmissao.fase === "falhou";
  useEffect(() => {
    if (!q || !transmissaoFalhou) return;
    requisicao.current?.abort();
    const controlador = new AbortController();
    requisicao.current = controlador;
    buscarPagina(q, cep, assentado, 1, { signal: controlador.signal, esperaMs: ESPERA_MS })
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
  }, [q, cep, assentado, transmissaoFalhou]);

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

  const transmitido = useMemo(() => todasOfertas(transmissao), [transmissao]);
  const final = transmissaoFalhou ? pagina : null;
  const varrendo = transmissao.fase === "transmitindo";
  const terminou = !varrendo && transmissao.fase !== "parada";
  const { historico, carregando: carregandoHistorico, pedir } = useHistoricoOfertas();

  const base = useMemo(
    () => (final ? [...final.ofertas, ...extra] : transmitido),
    [final, extra, transmitido],
  );
  const promocaoDe = useMemo(() => {
    const avaliadas = new Map<string, Promocao>(
      base.map((o) => [o.id, avaliarPromocao(o, historico[o.id], hoje)]),
    );
    return (o: Oferta) => avaliadas.get(o.id) ?? avaliarPromocao(o, historico[o.id], hoje);
  }, [base, historico, hoje]);
  const ranqueadas = useMemo(() => {
    const queda = (o: Oferta) => promocaoDe(o).quedaVerificada;
    const economia = (o: Oferta) => promocaoDe(o).economiaVerificada;
    if (final) {
      const lista = filtros.queda_verificada ? base.filter(queda) : base;
      return ORDENS_LOCAIS.has(filtros.ordem) ? rankingAoVivo(lista, filtros, economia) : lista;
    }
    return rankingAoVivo(
      filtrarAoVivo(rebaixarMuitoAbaixo(base), filtros, queda),
      filtros,
      economia,
    );
  }, [base, final, filtros, promocaoDe]);

  const { principais, parecidos } = useMemo(() => separarParecidos(ranqueadas), [ranqueadas]);
  const grupos = useMemo(() => agrupar(principais), [principais]);
  const gruposParecidos = useMemo(() => agrupar(parecidos), [parecidos]);
  const chaveVisiveis = `${q}|${cep}|${JSON.stringify(filtros)}`;
  const quantas = visiveis.chave === chaveVisiveis ? visiveis.quantas : POR_VEZ;
  const mostrados = fatiar(grupos, quantas);
  const ofertasMostradas = mostrados.reduce((n, g) => n + g.ofertas.length, 0);
  const melhor = useMemo(
    () => melhorOferta(principais, filtros, cep !== null),
    [principais, filtros, cep],
  );

  const precisaDeTudo = filtros.queda_verificada || ORDENS_LOCAIS.has(filtros.ordem);
  const idsDoHistorico = (
    precisaDeTudo
      ? base.map((o) => o.id)
      : [
          ...mostrados.flatMap((g) => g.ofertas.map((o) => o.id)),
          ...(melhor ? [melhor.oferta.id] : []),
        ]
  ).join(",");
  useEffect(() => {
    if (terminou && idsDoHistorico) pedir(idsDoHistorico.split(","));
  }, [terminou, idsDoHistorico, pedir]);

  const espectro = useMemo(
    () => (varrendo ? REPOUSO : espectroDe(transmitido, filtros.pagamento)),
    [varrendo, transmitido, filtros.pagamento],
  );
  useFaviconVivo(espectro, varrendo);

  const tipicos = useMemo(() => precosTipicos(base, filtros.pagamento), [base, filtros.pagamento]);
  const endereco = transmissao.inicio?.endereco ?? final?.endereco ?? null;
  const facetasAoVivo = useMemo(() => facetasDe(transmitido, filtros), [transmitido, filtros]);
  const facetas = final?.facetas ?? facetasAoVivo;
  const ocultas = ocultasPorCondicao(facetas, filtros);
  const totalPrincipais = final
    ? Math.max(final.total - parecidos.length, principais.length)
    : principais.length;
  const restantes = totalPrincipais - ofertasMostradas;
  const podeCarregarMais = restantes > 0;
  const grupoDoMelhor = melhor
    ? mostrados.find((g) => g.ofertas.includes(melhor.oferta))
    : undefined;
  const outrasLojas = grupoDoMelhor
    ? new Set(grupoDoMelhor.ofertas.map((o) => o.loja.id)).size - 1
    : 0;

  const contexto: Contexto = {
    pagamento: filtros.pagamento,
    cep,
    hoje,
    agora,
    historico,
    promocoes: promocaoDe,
    tipico: (o) => comparadoAoTipico(o, filtros.pagamento, tipicos),
  };

  async function carregarMais() {
    if (!final || ofertasMostradas < principais.length) {
      setVisiveis({ chave: chaveVisiveis, quantas: quantas + POR_VEZ });
      return;
    }
    setCarregandoMais(true);
    try {
      const signal = requisicao.current?.signal;
      const proximo = await buscarPagina(q, cep, assentado, proximaPagina, {
        signal,
        esperaMs: ESPERA_MS,
      });
      if (signal?.aborted) return;
      setExtra((anterior) => [...anterior, ...proximo.ofertas]);
      setProximaPagina((n) => n + 1);
      setVisiveis({ chave: chaveVisiveis, quantas: quantas + POR_VEZ });
    } catch (e) {
      if ((e as Error).name !== "AbortError")
        setErro(e instanceof ErroApi ? e.message : "Algo deu errado.");
    } finally {
      setCarregandoMais(false);
    }
  }

  function tentarDeNovo() {
    setPagina(null);
    setErro(null);
    setTentativa((n) => n + 1);
  }

  const semCep = new URLSearchParams(params);
  semCep.delete("cep");
  const mensagemDeErro = erro ?? (final ? null : transmissao.erro);
  const esperandoHistorico = precisaDeTudo && terminou && carregandoHistorico;
  const vazio = terminou && !ranqueadas.length && !esperandoHistorico && !mensagemDeErro;

  return (
    <div className="min-h-dvh">
      <header
        ref={cabecalho}
        className="sticky top-0 z-30 border-b border-fio bg-etiqueta/95 backdrop-blur-sm"
      >
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-2.5 sm:gap-5 sm:px-6">
          <Logo compacto espectro={espectro} />
          <div className="min-w-0 flex-1">
            <FormularioBusca
              key={`${q}-${cep}`}
              consultaInicial={q}
              cepInicial={cep ? mascararCep(cep) : undefined}
            />
          </div>
          <Link
            href="/ofertas"
            className="hidden shrink-0 text-[0.875rem] font-medium text-tinta-2 hover:text-tinta lg:block"
          >
            Quedas de preço
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 pt-5 pb-24 sm:px-6">
        <h1 className="text-[1.5rem] leading-tight font-semibold tracking-[-0.01em] break-words sm:text-[1.75rem]">
          {q}
        </h1>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 text-[0.9375rem]">
          {cep ? (
            <p className="flex items-start gap-1.5 text-tinta-2">
              <MapPin className="mt-1 size-4 shrink-0" aria-hidden />
              <span>
                <span className="hidden sm:inline">Entrega em </span>
                {endereco?.cidade && `${endereco.cidade}, ${endereco.uf} · `}
                <span className="numero font-semibold whitespace-nowrap text-acao">
                  CEP {mascararCep(cep)}
                </span>
              </span>
            </p>
          ) : (
            <p className="text-tinta-2">Sem CEP de entrega</p>
          )}
          <button
            type="button"
            onClick={focarCep}
            className="min-h-11 text-[0.875rem] font-medium whitespace-nowrap text-acao underline"
          >
            {cep ? (
              <>
                Trocar<span className="sr-only sm:not-sr-only"> CEP</span>
              </>
            ) : (
              "Informar CEP"
            )}
          </button>
        </div>
        <div className="mt-2">
          <StatusBusca
            fontes={transmissao.fontes}
            terminou={terminou}
            ofertas={ranqueadas.length}
            interrompida={transmissaoFalhou && !final}
          />
        </div>

        {!cep && (
          <p className="mt-3 rounded-etiqueta border border-alerta/40 bg-alerta-suave px-4 py-3 text-[0.9375rem] text-alerta">
            Sem CEP, os valores mostram só o preço do produto. Informe o CEP para incluir o frete de
            cada loja no total.
          </p>
        )}

        {mensagemDeErro && (
          <div
            role="alert"
            className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-etiqueta border border-falha/40 bg-falha-suave px-4 py-3 text-falha"
          >
            <span>{mensagemDeErro}</span>
            <button type="button" onClick={tentarDeNovo} className="botao botao-secundario">
              <RotateCw className="size-4" aria-hidden />
              Tentar de novo
            </button>
          </div>
        )}

        <div className="mt-5 lg:grid lg:grid-cols-[14.5rem_minmax(0,1fr)] lg:gap-8">
          <aside
            aria-label="Filtros"
            className="hidden lg:sticky lg:top-[calc(var(--altura-cabecalho,4rem)+1rem)] lg:block lg:max-h-[calc(100dvh-var(--altura-cabecalho,4rem)-2rem)] lg:overflow-y-auto lg:pr-2"
          >
            <PainelFiltros filtros={filtros} facetas={facetas} onChange={setFiltros} />
          </aside>

          <div className="min-w-0">
            <div className="sticky top-[var(--altura-cabecalho,4rem)] z-20 -mx-4 border-b border-fio bg-fundo/95 px-4 py-2 backdrop-blur-sm sm:-mx-6 sm:px-6 lg:static lg:mx-0 lg:border-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none">
              <div className="flex items-center gap-2">
                <p className="numero hidden flex-1 text-[0.9375rem] text-tinta-2 lg:block">
                  {plural(principais.length, "oferta", "ofertas")}
                  {grupos.length !== principais.length &&
                    ` de ${plural(grupos.length, "produto", "produtos")}`}
                </p>
                <div className="flex flex-1 gap-2 lg:hidden">
                  <BotaoFiltros
                    filtros={filtros}
                    facetas={facetas}
                    onChange={setFiltros}
                    visiveis={ranqueadas.length}
                  />
                </div>
                <label className="campo relative flex h-11 flex-1 items-center lg:flex-none">
                  <span className="sr-only lg:not-sr-only lg:pl-3 lg:text-[0.875rem] lg:text-tinta-2">
                    Ordenar
                  </span>
                  <select
                    value={filtros.ordem}
                    onChange={(e) =>
                      setFiltros({ ...filtros, ordem: e.target.value as Filtros["ordem"] })
                    }
                    className="h-full w-full cursor-pointer appearance-none bg-transparent pr-8 pl-3 text-[0.9375rem] font-medium outline-none lg:w-auto lg:pl-1.5"
                  >
                    {ORDENS.map((o) => (
                      <option key={o.valor} value={o.valor}>
                        {o.rotulo}
                      </option>
                    ))}
                  </select>
                  <ChevronDown
                    className="pointer-events-none absolute right-2.5 size-4 text-tinta-2"
                    aria-hidden
                  />
                </label>
              </div>
            </div>

            <div className="mt-3 space-y-2">
              <ChipsFiltros filtros={filtros} facetas={facetas} onChange={setFiltros} />
              {ocultas > 0 && (
                <p className="text-[0.875rem] text-tinta-2">
                  {plural(
                    ocultas,
                    "oferta usada ou recondicionada está escondida.",
                    "ofertas usadas ou recondicionadas estão escondidas.",
                  )}{" "}
                  <button
                    type="button"
                    onClick={() =>
                      setFiltros({ ...filtros, condicao: ["novo", "recondicionado", "usado"] })
                    }
                    className="font-medium text-acao underline"
                  >
                    Mostrar também
                  </button>
                </p>
              )}
              {esperandoHistorico && (
                <p role="status" className="text-[0.875rem] text-tinta-2">
                  Conferindo o histórico de preço das ofertas.
                </p>
              )}
            </div>

            <div className="mt-4 space-y-4">
              {melhor ? (
                <EtiquetaMelhor
                  melhor={melhor}
                  contexto={contexto}
                  outrasLojas={outrasLojas}
                  chaveGrupo={grupoDoMelhor?.chave ?? ""}
                  provisoria={varrendo}
                />
              ) : !terminou ? (
                <EsqueletoMelhor />
              ) : cep && principais.length > 0 ? (
                <p className="rounded-etiqueta border border-fio bg-etiqueta px-4 py-3 text-[0.9375rem] text-tinta-2">
                  Nenhuma loja confirmou o frete para este CEP nas ofertas abaixo, então não há um
                  total para recomendar. Os valores mostram o preço sem frete.
                </p>
              ) : null}

              {vazio ? (
                <Vazio
                  motivo={motivoDoVazio({ fontes: transmissao.fontes, ofertas: transmitido })}
                  q={q}
                  cep={cep}
                  aoTentarDeNovo={tentarDeNovo}
                  aoLimparFiltros={() =>
                    setFiltros({
                      ...FILTROS_PADRAO,
                      ordem: filtros.ordem,
                      pagamento: filtros.pagamento,
                    })
                  }
                  hrefSemCep={`${pathname}?${semCep}`}
                />
              ) : (
                <section aria-labelledby="titulo-ofertas">
                  <h2 id="titulo-ofertas" className="sr-only">
                    Ofertas por produto
                  </h2>
                  {mostrados.length ? (
                    <div className="space-y-3">
                      {mostrados.map((g) => (
                        <CartaoGrupo key={g.chave} grupo={g} contexto={contexto} />
                      ))}
                    </div>
                  ) : !terminou || esperandoHistorico ? (
                    <EsqueletoGrupos />
                  ) : null}

                  {podeCarregarMais && mostrados.length > 0 && (
                    <button
                      type="button"
                      onClick={carregarMais}
                      disabled={carregandoMais}
                      className="botao botao-secundario mx-auto mt-5 flex"
                    >
                      {carregandoMais
                        ? "Carregando"
                        : `Mais ofertas (${plural(restantes, "restante", "restantes")})`}
                    </button>
                  )}
                </section>
              )}

              {gruposParecidos.length > 0 && (
                <Parecidos
                  grupos={gruposParecidos}
                  quantas={parecidos.length}
                  contexto={contexto}
                  abertos={!principais.length}
                />
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function motivoDoParecido(ofertas: Oferta[]): string {
  const termos = [...new Set(ofertas.flatMap((o) => o.termos_ausentes ?? []))];
  return termos.length
    ? `Sem ${termos.map((t) => `“${t}”`).join(", ")} no título`
    : "Pode não ser o produto buscado";
}

function Parecidos({
  grupos,
  quantas,
  contexto,
  abertos,
}: {
  grupos: ReturnType<typeof agrupar>;
  quantas: number;
  contexto: Contexto;
  abertos: boolean;
}) {
  const [limite, setLimite] = useState(POR_VEZ);
  const mostrados = fatiar(grupos, limite);
  return (
    <details open={abertos} className="gaveta-detalhes group">
      <summary className="flex min-h-12 cursor-pointer items-center justify-between gap-3 rounded-etiqueta border border-fio bg-etiqueta px-4">
        <span>
          <h2 className="inline font-semibold">Parecidos</h2>
          <span className="text-tinta-2">
            {" "}
            · {plural(quantas, "oferta que não bate", "ofertas que não batem")} com tudo o que foi
            buscado
          </span>
        </span>
        <ChevronDown className="seta-detalhes size-5 shrink-0 transition-transform" aria-hidden />
      </summary>
      <div className="mt-3 space-y-3">
        {mostrados.map((g) => (
          <CartaoGrupo
            key={g.chave}
            grupo={g}
            contexto={contexto}
            motivo={motivoDoParecido(g.ofertas)}
          />
        ))}
        {mostrados.length < grupos.length && (
          <button
            type="button"
            onClick={() => setLimite((n) => n + POR_VEZ)}
            className="botao botao-secundario mx-auto flex"
          >
            Mais parecidos
          </button>
        )}
      </div>
    </details>
  );
}
