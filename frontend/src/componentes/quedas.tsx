"use client";

import { ArrowUpRight, ChevronDown, RotateCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { Foto } from "@/componentes/foto";
import { ErroApi, quedasDePreco } from "@/nucleo/api";
import { haQuanto, plural, porcentagem, reais } from "@/nucleo/formato";
import type { RespostaQuedas } from "@/nucleo/tipos";

const PERIODOS = [7, 30, 90];
// a API só lista quedas de 10% ou mais, então o padrão já é esse
const QUEDAS_MINIMAS = [
  { valor: 0, rotulo: "10% ou mais" },
  { valor: 0.2, rotulo: "20% ou mais" },
  { valor: 0.3, rotulo: "30% ou mais" },
];

type Resposta = { chave: string } & (
  { fase: "erro"; mensagem: string } | { fase: "pronto"; dados: RespostaQuedas; agora: Date }
);

const SEM_ITENS: RespostaQuedas["itens"] = [];

function Segmentos<T extends string | number>({
  rotulo,
  valor,
  opcoes,
  aoMudar,
}: {
  rotulo: string;
  valor: T;
  opcoes: { valor: T; rotulo: string }[];
  aoMudar: (v: T) => void;
}) {
  return (
    <div role="group" aria-label={rotulo}>
      <p className="text-[0.8125rem] text-apagado" aria-hidden>
        {rotulo}
      </p>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {opcoes.map((o) => (
          <button
            key={o.valor}
            type="button"
            aria-pressed={o.valor === valor}
            onClick={() => aoMudar(o.valor)}
            className={`min-h-11 rounded-quadro border px-3 text-[0.875rem] transition-colors ${
              o.valor === valor
                ? "border-ouro/50 bg-ouro-suave text-ouro"
                : "border-traco-forte text-apagado hover:text-tinta"
            }`}
          >
            {o.rotulo}
          </button>
        ))}
      </div>
    </div>
  );
}

export function Quedas() {
  const [dias, setDias] = useState(30);
  const [loja, setLoja] = useState("");
  const [quedaMinima, setQuedaMinima] = useState(0);
  const [tentativa, setTentativa] = useState(0);
  const [resposta, setResposta] = useState<Resposta | null>(null);
  const chave = `${dias}|${tentativa}`;
  const estado = resposta?.chave === chave ? resposta : ({ fase: "carregando" } as const);

  useEffect(() => {
    const controlador = new AbortController();
    quedasDePreco(dias, controlador.signal)
      .then((dados) => setResposta({ chave, fase: "pronto", dados, agora: new Date() }))
      .catch((e: Error) => {
        if (e.name === "AbortError") return;
        setResposta({
          chave,
          fase: "erro",
          mensagem:
            e instanceof ErroApi && e.status === 0
              ? e.message
              : "Não foi possível carregar as quedas de preço agora.",
        });
      });
    return () => controlador.abort();
  }, [dias, chave]);

  const itens = estado.fase === "pronto" ? estado.dados.itens : SEM_ITENS;
  const lojas = useMemo(
    () =>
      [...new Map(itens.map((i) => [i.loja.id, i.loja.nome]))].sort((a, b) =>
        a[1].localeCompare(b[1], "pt-BR"),
      ),
    [itens],
  );
  const filtrados = itens
    .filter((i) => (!loja || i.loja.id === loja) && -i.variacao >= quedaMinima)
    .sort((a, b) => a.variacao - b.variacao);
  const temFiltro = loja !== "" || quedaMinima > 0;
  const agora = estado.fase === "pronto" ? estado.agora : new Date(0);

  return (
    <>
      <div className="mt-8 flex flex-wrap items-end gap-x-8 gap-y-5">
        <Segmentos
          rotulo="Período"
          valor={dias}
          opcoes={PERIODOS.map((d) => ({ valor: d, rotulo: `${d} dias` }))}
          aoMudar={setDias}
        />
        <Segmentos
          rotulo="Queda"
          valor={quedaMinima}
          opcoes={QUEDAS_MINIMAS}
          aoMudar={setQuedaMinima}
        />
        <label className="flex flex-col">
          <span className="text-[0.8125rem] text-apagado">Loja</span>
          <span className="seletor mt-1.5">
            <select
              value={loja}
              onChange={(e) => setLoja(e.target.value)}
              disabled={!lojas.length}
              className="h-[2.625rem] min-w-44 cursor-pointer appearance-none bg-transparent pr-9 pl-3 text-[0.875rem] outline-none disabled:cursor-not-allowed"
            >
              <option value="">Todas as lojas</option>
              {lojas.map(([id, nome]) => (
                <option key={id} value={id}>
                  {nome}
                </option>
              ))}
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-2.5 size-4 text-apagado"
              aria-hidden
            />
          </span>
        </label>
      </div>

      <div className="mt-8 max-w-4xl" aria-live="polite" aria-busy={estado.fase === "carregando"}>
        {estado.fase === "carregando" && (
          <ul aria-hidden>
            {[0, 1, 2, 3].map((i) => (
              <li key={i} className="flex gap-4 border-t border-traco py-5">
                <div className="esqueleto size-14" />
                <div className="flex-1 space-y-2 pt-1">
                  <div className="esqueleto h-4 w-3/4" />
                  <div className="esqueleto h-3.5 w-1/3" />
                </div>
                <div className="esqueleto h-6 w-24" />
              </li>
            ))}
          </ul>
        )}

        {estado.fase === "erro" && (
          <div
            role="alert"
            className="rounded-quadro border border-falha/35 bg-falha-suave px-5 py-5"
          >
            <h2 className="font-medium">{estado.mensagem}</h2>
            <p className="mt-1 text-apagado">
              Tente de novo daqui a pouco. A busca continua funcionando.
            </p>
            <button
              type="button"
              onClick={() => setTentativa((n) => n + 1)}
              className="botao botao-linha mt-4"
            >
              <RotateCw className="size-4" aria-hidden />
              Tentar de novo
            </button>
          </div>
        )}

        {estado.fase === "pronto" && (
          <>
            {/* sem quedas, o aviso abaixo já diz; a hora em que a lista foi montada não ajuda */}
            {filtrados.length > 0 && (
              <p className="numero text-[0.875rem] text-apagado">
                {plural(filtrados.length, "queda", "quedas")}
              </p>
            )}
            {filtrados.length ? (
              <ul className="mt-3">
                {filtrados.map((i, n) => (
                  <li
                    key={i.oferta}
                    style={{ "--i": n } as CSSProperties}
                    className="linha-oferta grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-3 border-t border-traco py-5 sm:grid-cols-[auto_minmax(0,1fr)_auto]"
                  >
                    <Foto imagem={i.imagem} tamanho="size-14" />
                    <div className="min-w-0">
                      <h2 className="line-clamp-2 leading-snug font-medium">{i.titulo}</h2>
                      <p className="mt-0.5 text-[0.875rem] text-apagado">
                        <span className="text-tinta">{i.loja.nome}</span>
                        {haQuanto(i.visto_em, agora) && ` · visto ${haQuanto(i.visto_em, agora)}`}
                      </p>
                      <p className="mt-1.5 text-[0.875rem] text-exato">
                        {porcentagem(-i.variacao)} abaixo do habitual desta loja
                      </p>
                      <details className="gaveta-detalhes text-[0.875rem]">
                        <summary className="botao-texto cursor-pointer">
                          Ver o histórico
                          <ChevronDown className="chevron size-4" aria-hidden />
                        </summary>
                        <div className="numero space-y-0.5 pb-1 text-apagado">
                          <p>
                            Habitual {reais(i.mediana)}, menor {reais(i.menor)}, maior{" "}
                            {reais(i.maior)} em{" "}
                            {plural(i.dias_observados, "dia observado", "dias observados")}.
                          </p>
                          {i.preco_original !== null && i.preco_original > i.preco && (
                            <p>
                              A loja anuncia “de{" "}
                              <s className="text-tenue">{reais(i.preco_original)}</s>”
                              {i.preco_original > i.maior && ", acima do maior preço visto aqui"}.
                            </p>
                          )}
                        </div>
                      </details>
                    </div>
                    <div className="col-span-full flex items-end justify-between gap-4 sm:col-span-1 sm:flex-col sm:items-end sm:justify-start">
                      <div className="sm:text-right">
                        <p className="font-mono text-[1.1875rem] leading-tight font-medium tabular-nums">
                          {reais(i.preco)}
                        </p>
                        <p className="mt-0.5 text-[0.8125rem] text-apagado">Sem frete</p>
                      </div>
                      <a
                        href={i.link}
                        target="_blank"
                        rel="noopener noreferrer nofollow"
                        className="botao botao-linha"
                      >
                        Ver na loja
                        <ArrowUpRight className="seta size-4" aria-hidden />
                        <span className="sr-only"> {i.loja.nome} (abre em nova aba)</span>
                      </a>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="mt-3 border-t border-traco py-10">
                {temFiltro ? (
                  <>
                    <h2 className="text-[1.1875rem] font-semibold">
                      Nenhuma queda com esses filtros
                    </h2>
                    <button
                      type="button"
                      onClick={() => {
                        setLoja("");
                        setQuedaMinima(0);
                      }}
                      className="botao botao-ouro mt-5"
                    >
                      Limpar os filtros
                    </button>
                  </>
                ) : (
                  <>
                    <h2 className="text-[1.1875rem] font-semibold">
                      Nenhuma queda observada nos últimos {dias} dias
                    </h2>
                    <p className="mt-1.5 max-w-[60ch] text-apagado">
                      A lista cresce conforme as pessoas buscam no Zpektral.
                    </p>
                    <div className="mt-5 flex flex-wrap gap-2">
                      <Link href="/" className="botao botao-ouro">
                        Fazer uma busca
                      </Link>
                      {dias < 90 && (
                        <button
                          type="button"
                          onClick={() => setDias(90)}
                          className="botao botao-linha"
                        >
                          Ver os últimos 90 dias
                        </button>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}
