"use client";

import { ChevronDown, RotateCw, TrendingDown } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { FormularioBusca, ID_CAMPO_CEP, ID_CAMPO_PRODUTO } from "@/componentes/formulario-busca";
import type { Contexto } from "@/componentes/linha-oferta";
import { Logo } from "@/componentes/logo";
import { BotaoFiltros, ChipsFiltros } from "@/componentes/painel-filtros";
import { LinhaProgresso, StatusBusca } from "@/componentes/status-busca";
import {
  EsqueletoGrupos,
  EsqueletoMelhor,
  GrupoProduto,
  MelhorTotal,
  Vazio,
} from "@/componentes/vitrine";
import { useAtalhoBusca } from "@/ganchos/use-atalho-busca";
import { useFaviconVivo } from "@/ganchos/use-favicon-vivo";
import { useHistoricoOfertas } from "@/ganchos/use-historico-ofertas";
import { useInteracao } from "@/ganchos/use-interacao";
import { useTransmissaoBusca } from "@/ganchos/use-transmissao-busca";
import { useVistos } from "@/ganchos/use-vistos";
import { filtrarAoVivo, rebaixarMuitoAbaixo } from "@/nucleo/ao-vivo";
import { ErroApi, buscarPagina } from "@/nucleo/api";
import { REPOUSO, espectroDe } from "@/nucleo/espectro";
import {
  ORDENS,
  ORDENS_LOCAIS,
  PAGAMENTOS,
  facetasDe,
  filtrosDosParametros,
  filtrosParaParametros,
  limparFiltros,
  ocultasPorCondicao,
} from "@/nucleo/filtros";
import { hojeEmBrasilia, mascararCep, plural } from "@/nucleo/formato";
import { destaqueSeguro, foraDeOrdem, ordemEstavel } from "@/nucleo/ordem-estavel";
import { avaliarPromocao, type Promocao } from "@/nucleo/promocao";
import { comparadoAoTipico, precosTipicos } from "@/nucleo/referencia";
import { rankingAoVivo, todasOfertas } from "@/nucleo/transmissao";
import type { Filtros, Oferta, PaginaResultados } from "@/nucleo/tipos";
import {
  agrupar,
  fatiar,
  lojasFora,
  melhorOferta,
  motivoDoVazio,
  separarParecidos,
  type MelhorOferta,
} from "@/nucleo/vitrine";

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

function focar(id: string) {
  const campo = document.getElementById(id) as HTMLInputElement | null;
  campo?.focus();
  campo?.select();
}
const focarCep = () => focar(ID_CAMPO_CEP);

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
  const [erro, setErro] = useState<Error | null>(null);
  const [carregandoMais, setCarregandoMais] = useState(false);
  const [reordenacoes, setReordenacoes] = useState(0);
  const cabecalho = useRef<HTMLElement>(null);
  const lista = useRef<HTMLElement>(null);
  const blocoDestaque = useRef<HTMLDivElement>(null);
  const requisicao = useRef<AbortController | null>(null);
  const agora = useAgora(30_000);
  // recalculado a cada render: uma aba aberta que passa da meia-noite muda de dia
  const hoje = hojeEmBrasilia();
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
        if (e.name !== "AbortError") setErro(e);
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
  const { historico, carregando: carregandoHistorico, pedir } = useHistoricoOfertas(cep);

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
  const chaveVisiveis = `${q}|${cep}|${JSON.stringify(filtros)}`;
  // Enquanto as lojas respondem, o que já passou pela tela fica no lugar. Mudar a ordem, um
  // filtro, a busca ou pedir a ordem atualizada volta ao ranking puro.
  const vistos = useVistos(lista, varrendo, `${chaveVisiveis}|${tentativa}|${reordenacoes}`);
  const ordenadas = useMemo(() => ordemEstavel(principais, vistos), [principais, vistos]);
  const grupos = useMemo(() => agrupar(ordenadas), [ordenadas]);
  const gruposParecidos = useMemo(() => agrupar(parecidos), [parecidos]);
  const quantas = visiveis.chave === chaveVisiveis ? visiveis.quantas : POR_VEZ;
  const mostrados = fatiar(grupos, quantas);
  const ofertasMostradas = mostrados.reduce((n, g) => n + g.ofertas.length, 0);
  const melhor = useMemo(
    () => melhorOferta(principais, filtros, cep !== null),
    [principais, filtros, cep],
  );
  // O destaque só troca de oferta quando ninguém está com o ponteiro ou o foco nele.
  const interagindo = useInteracao(blocoDestaque);
  const [exibido, setExibido] = useState<MelhorOferta | null>(null);
  const destaque = destaqueSeguro(exibido, melhor, interagindo);
  if (destaque !== exibido) setExibido(destaque);
  // A oferta do destaque sai da lista, salvo se a pessoa já a viu lá: tirar empurraria o resto.
  const idDestaque = destaque?.oferta.id;
  const omitir = idDestaque && !vistos.includes(idDestaque) ? idDestaque : undefined;
  const foraDoRanking = useMemo(
    () =>
      terminou &&
      foraDeOrdem(
        ordenadas.filter((o) => o.id !== omitir),
        principais.filter((o) => o.id !== idDestaque),
      ),
    [terminou, ordenadas, principais, omitir, idDestaque],
  );

  const precisaDeTudo = filtros.queda_verificada || ORDENS_LOCAIS.has(filtros.ordem);
  const idsDoHistorico = (
    precisaDeTudo
      ? base.map((o) => o.id)
      : [
          ...mostrados.flatMap((g) => g.ofertas.map((o) => o.id)),
          ...(destaque ? [destaque.oferta.id] : []),
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
  const grupoDoMelhor = destaque
    ? mostrados.find((g) => g.ofertas.some((o) => o.id === destaque.oferta.id))
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
      if ((e as Error).name !== "AbortError") setErro(e as Error);
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
  const mensagemDeErro = erro
    ? erro instanceof ErroApi
      ? erro.message
      : "Algo deu errado."
    : final
      ? null
      : transmissao.erro;
  // a API só responde 404 na busca quando o CEP não existe: tentar de novo repetiria o erro
  const cepNaoExiste = erro instanceof ErroApi && erro.status === 404;
  const esperandoHistorico = precisaDeTudo && terminou && carregandoHistorico;
  const vazio = terminou && !ranqueadas.length && !esperandoHistorico && !mensagemDeErro;
  const motivo = vazio ? motivoDoVazio({ fontes: transmissao.fontes, ofertas: transmitido }) : null;
  // Sem nenhuma oferta para filtrar, filtros e ordenação só ocupam espaço.
  const semFerramentas =
    (vazio && motivo !== "filtros_escondem") || (!!mensagemDeErro && !ranqueadas.length);

  // com menos de três grupos na tela, o esqueleto segura o lugar dos que ainda vão chegar
  const comLinhas = mostrados.filter((g) => g.ofertas.some((o) => o.id !== omitir));
  const faltam = !terminou || esperandoHistorico ? Math.max(0, 3 - comLinhas.length) : 0;

  return (
    <div className="min-h-dvh">
      <a href="#ofertas" className="pular">
        Pular para as ofertas
      </a>
      <header ref={cabecalho} className="sticky top-0 z-30 bg-fundo/90 backdrop-blur-md">
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
            title="Quedas de preço"
            className="-mr-2 inline-flex min-h-11 min-w-11 shrink-0 items-center justify-center text-[0.875rem] text-apagado transition-colors hover:text-tinta md:mr-0 md:min-w-0"
          >
            <TrendingDown className="size-5 md:hidden" aria-hidden />
            <span className="sr-only md:not-sr-only">Quedas de preço</span>
          </Link>
        </div>
        <div className="relative border-b border-traco">
          <LinhaProgresso fontes={transmissao.fontes} terminou={terminou} />
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 pt-5 pb-24 sm:px-6 sm:pt-10">
        <h1 className="text-[1.625rem] leading-tight font-semibold tracking-[-0.02em] break-words [font-stretch:104%] sm:text-[2.25rem]">
          {q}
        </h1>
        {cepNaoExiste ? (
          <div
            role="alert"
            className="mt-4 rounded-quadro border border-falha/35 bg-falha-suave px-4 py-4"
          >
            <p className="max-w-[62ch]">
              Não achamos o CEP {mascararCep(cep ?? "")}. Confira os números ou busque sem CEP (os
              preços virão sem o frete).
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" onClick={focarCep} className="botao botao-linha">
                Corrigir o CEP
              </button>
              <Link href={`${pathname}?${semCep}`} className="botao botao-linha">
                Buscar sem CEP
              </Link>
            </div>
          </div>
        ) : (
          <>
            <div className="mt-1.5 flex min-w-0 items-center gap-x-2 text-[0.9375rem] text-apagado sm:mt-2">
              {cep ? (
                <p className="flex min-w-0 items-center gap-x-2">
                  {endereco?.cidade && (
                    <span className="truncate">
                      {/* no celular só a cidade: rua e bairro empurrariam as ofertas para baixo */}
                      <span className="hidden sm:inline">
                        {[endereco.logradouro, endereco.bairro].filter(Boolean).join(", ")}
                        {(endereco.logradouro || endereco.bairro) && ", "}
                      </span>
                      {endereco.cidade}/{endereco.uf}
                    </span>
                  )}
                  {endereco?.cidade && <span aria-hidden>·</span>}
                  <span className="font-mono text-[0.875rem] whitespace-nowrap text-tinta">
                    {mascararCep(cep)}
                  </span>
                </p>
              ) : (
                <p className="min-w-0">Sem CEP: os preços não incluem o frete.</p>
              )}
              <span aria-hidden>·</span>
              <button
                type="button"
                onClick={focarCep}
                className="botao-texto shrink-0 text-ouro underline decoration-ouro/40 hover:text-ouro hover:decoration-ouro"
              >
                {cep ? (
                  <span>
                    Trocar<span className="sr-only sm:not-sr-only"> CEP</span>
                  </span>
                ) : (
                  "Informar CEP"
                )}
              </button>
            </div>
            <StatusBusca
              fontes={transmissao.fontes}
              terminou={terminou}
              // só com parecidos na tela, "0 ofertas" desmentia a lista logo abaixo
              ofertas={principais.length || parecidos.length}
              interrompida={transmissaoFalhou && !final}
              acao={
                foraDoRanking && (
                  <button
                    type="button"
                    onClick={() => {
                      setReordenacoes((n) => n + 1);
                      document.getElementById("ofertas")?.focus({ preventScroll: true });
                    }}
                    className="botao-texto shrink-0 text-ouro underline decoration-ouro/40 hover:text-ouro hover:decoration-ouro pointer-coarse:-my-1"
                  >
                    Atualizar a ordem
                  </button>
                )
              }
            />
          </>
        )}

        {mensagemDeErro && !cepNaoExiste && (
          <div
            role="alert"
            className="mt-4 flex flex-wrap items-center justify-between gap-x-6 gap-y-3 rounded-quadro border border-falha/35 bg-falha-suave px-4 py-3.5"
          >
            <p>{mensagemDeErro}</p>
            <button type="button" onClick={tentarDeNovo} className="botao botao-linha">
              <RotateCw className="size-4" aria-hidden />
              Tentar de novo
            </button>
          </div>
        )}

        <div
          hidden={semFerramentas}
          className="sticky top-[var(--altura-cabecalho,4rem)] z-20 -mx-4 mt-3 border-b border-traco bg-fundo/90 px-4 py-2 backdrop-blur-md sm:-mx-6 sm:mt-4 sm:px-6 sm:py-2.5"
        >
          <div className="flex items-center gap-1.5 sm:justify-end sm:gap-2">
            <Seletor
              rotulo="Pagar com"
              curto="Pagar"
              classe="flex-[1.55]"
              valor={filtros.pagamento}
              opcoes={PAGAMENTOS}
              aoMudar={(pagamento) => setFiltros({ ...filtros, pagamento })}
            />
            <Seletor
              rotulo="Ordenar"
              valor={filtros.ordem}
              opcoes={ORDENS}
              aoMudar={(ordem) => setFiltros({ ...filtros, ordem })}
            />
            <BotaoFiltros
              filtros={filtros}
              facetas={facetas}
              onChange={setFiltros}
              visiveis={ranqueadas.length}
            />
          </div>
        </div>

        <div className="mt-3 space-y-2 empty:hidden">
          <ChipsFiltros filtros={filtros} facetas={facetas} onChange={setFiltros} />
          {esperandoHistorico && (
            <p role="status" className="text-[0.875rem] text-apagado">
              Conferindo o histórico de preço das ofertas.
            </p>
          )}
        </div>

        <div id="ofertas" tabIndex={-1} className="mt-4 scroll-mt-40 outline-none">
          <div ref={blocoDestaque}>
            {destaque ? (
              <MelhorTotal
                melhor={destaque}
                contexto={contexto}
                outrasLojas={outrasLojas}
                chaveGrupo={grupoDoMelhor?.chave ?? ""}
                provisoria={varrendo}
              />
            ) : !terminou ? (
              <EsqueletoMelhor />
            ) : cep && principais.length > 0 ? (
              <p className="text-[0.9375rem] text-apagado">
                Nenhuma loja confirmou o frete para este CEP; os valores são sem frete.
              </p>
            ) : null}
          </div>

          {vazio ? (
            <Vazio
              motivo={motivo ?? "nada_correspondente"}
              fora={lojasFora(transmissao.fontes)}
              q={q}
              cep={cep}
              aoTentarDeNovo={tentarDeNovo}
              aoLimparFiltros={() => setFiltros(limparFiltros(filtros))}
              aoCorrigirBusca={() => focar(ID_CAMPO_PRODUTO)}
              hrefSemCep={`${pathname}?${semCep}`}
            />
          ) : (
            <section ref={lista} aria-labelledby="titulo-ofertas">
              <h2 id="titulo-ofertas" className="sr-only">
                Ofertas por produto
              </h2>
              {mostrados.map((g) => (
                // pela primeira oferta: no fim da busca o grupo pode ganhar outra chave, e com a
                // chave dele o bloco seria remontado e as linhas entrariam de novo
                <GrupoProduto key={g.ofertas[0].id} grupo={g} contexto={contexto} omitir={omitir} />
              ))}
              {faltam > 0 && <EsqueletoGrupos quantos={faltam} />}

              {podeCarregarMais && mostrados.length > 0 && (
                <button
                  type="button"
                  onClick={carregarMais}
                  disabled={carregandoMais}
                  className="botao botao-linha mx-auto mt-8 flex"
                >
                  {carregandoMais
                    ? "Carregando"
                    : `Mais ofertas (${plural(restantes, "restante", "restantes")})`}
                </button>
              )}
            </section>
          )}

          {/* depois da lista: quando os dados chegam, acima dela este aviso empurrava as ofertas */}
          {ocultas > 0 && (
            <p className="mt-6 border-t border-traco py-3 text-[0.875rem] text-apagado sm:px-4">
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
                className="text-ouro underline decoration-ouro/40 hover:decoration-ouro"
              >
                Mostrar também
              </button>
            </p>
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
      </main>
    </div>
  );
}

function Seletor<T extends string>({
  rotulo,
  curto,
  classe = "flex-1",
  valor,
  opcoes,
  aoMudar,
}: {
  rotulo: string;
  /** rótulo visível no celular, onde o completo não cabe */
  curto?: string;
  classe?: string;
  valor: T;
  opcoes: { valor: T; rotulo: string }[];
  aoMudar: (valor: T) => void;
}) {
  return (
    <label className={`seletor min-w-0 sm:flex-none ${classe}`}>
      {curto && (
        <span aria-hidden className="shrink-0 pl-2 text-apagado sm:pl-2.5 md:hidden">
          {curto}
        </span>
      )}
      <span className="sr-only md:not-sr-only md:shrink-0 md:pl-3 md:text-apagado">{rotulo}</span>
      <select
        value={valor}
        onChange={(e) => aoMudar(e.target.value as T)}
        className={`h-[2.625rem] w-full min-w-0 cursor-pointer appearance-none truncate bg-transparent pr-6 text-[0.8125rem] font-medium sm:pr-8 sm:text-[0.875rem] md:w-auto md:max-w-[10.5rem] md:pl-1.5 ${
          curto ? "pl-1.5" : "pl-2 sm:pl-3"
        }`}
      >
        {opcoes.map((o) => (
          <option key={o.valor} value={o.valor}>
            {o.rotulo}
          </option>
        ))}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-1.5 size-3.5 text-apagado sm:right-2.5 sm:size-4"
        aria-hidden
      />
    </label>
  );
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
    <details open={abertos} className="gaveta-detalhes mt-10 border-t border-traco-forte">
      <summary className="flex min-h-14 cursor-pointer items-center justify-between gap-3 text-apagado transition-colors hover:text-tinta">
        <span>
          <h2 className="inline font-medium text-tinta">Parecidos</h2>
          {" · "}
          {plural(quantas, "oferta que não bate", "ofertas que não batem")} com tudo o que foi
          buscado
        </span>
        <ChevronDown className="chevron size-5 shrink-0" aria-hidden />
      </summary>
      <div>
        {mostrados.map((g) => (
          // o título da seção já diz que não batem com tudo; repetir o motivo em cada produto
          // ("Sem “mangá” no título") só enchia a lista
          <GrupoProduto key={g.chave} grupo={g} contexto={contexto} />
        ))}
        {mostrados.length < grupos.length && (
          <button
            type="button"
            onClick={() => setLimite((n) => n + POR_VEZ)}
            className="botao botao-linha mx-auto mt-6 flex"
          >
            Mais parecidos
          </button>
        )}
      </div>
    </details>
  );
}
