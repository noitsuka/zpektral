"use client";

import { ArrowUpRight, ChevronDown, RotateCw, TrendingDown } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Foto } from "@/componentes/vitrine";
import { ErroApi, quedasDePreco } from "@/nucleo/api";
import { haQuanto, plural, porcentagem, reais } from "@/nucleo/formato";
import type { RespostaQuedas } from "@/nucleo/tipos";

const PERIODOS = [7, 30];
const QUEDAS_MINIMAS = [
  { valor: 0, rotulo: "Qualquer" },
  { valor: 0.1, rotulo: "10% ou mais" },
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
      <p className="text-[0.8125rem] font-semibold text-tinta-2" aria-hidden>
        {rotulo}
      </p>
      <div className="mt-1 flex flex-wrap gap-1.5">
        {opcoes.map((o) => (
          <button
            key={o.valor}
            type="button"
            aria-pressed={o.valor === valor}
            onClick={() => aoMudar(o.valor)}
            className={`min-h-10 rounded-controle border px-3 text-[0.875rem] font-medium ${
              o.valor === valor
                ? "border-tinta bg-tinta text-etiqueta"
                : "border-borda bg-etiqueta text-tinta hover:border-tinta"
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
      <div className="mt-6 flex flex-wrap items-end gap-x-6 gap-y-4">
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
          <span className="text-[0.8125rem] font-semibold text-tinta-2">Loja</span>
          <span className="campo relative mt-1 flex h-10 items-center">
            <select
              value={loja}
              onChange={(e) => setLoja(e.target.value)}
              disabled={!lojas.length}
              className="h-full min-w-44 cursor-pointer appearance-none bg-transparent pr-9 pl-3 text-[0.9375rem] outline-none"
            >
              <option value="">Todas as lojas</option>
              {lojas.map(([id, nome]) => (
                <option key={id} value={id}>
                  {nome}
                </option>
              ))}
            </select>
            <ChevronDown
              className="pointer-events-none absolute right-2.5 size-4 text-tinta-2"
              aria-hidden
            />
          </span>
        </label>
      </div>

      <div className="mt-6" aria-live="polite" aria-busy={estado.fase === "carregando"}>
        {estado.fase === "carregando" && (
          <ul aria-hidden className="space-y-3">
            {[0, 1, 2, 3].map((i) => (
              <li key={i} className="flex gap-4 rounded-etiqueta border border-fio bg-etiqueta p-4">
                <div className="esqueleto size-16" />
                <div className="flex-1 space-y-2 pt-1">
                  <div className="esqueleto h-4 w-3/4" />
                  <div className="esqueleto h-3 w-1/3" />
                  <div className="esqueleto h-5 w-40" />
                </div>
              </li>
            ))}
          </ul>
        )}

        {estado.fase === "erro" && (
          <div
            role="alert"
            className="rounded-etiqueta border border-falha/40 bg-falha-suave px-5 py-6"
          >
            <h2 className="font-semibold text-falha">{estado.mensagem}</h2>
            <p className="mt-1 text-tinta-2">
              Tente de novo daqui a pouco. A busca continua funcionando.
            </p>
            <button
              type="button"
              onClick={() => setTentativa((n) => n + 1)}
              className="botao botao-secundario mt-4"
            >
              <RotateCw className="size-4" aria-hidden />
              Tentar de novo
            </button>
          </div>
        )}

        {estado.fase === "pronto" && (
          <>
            <p className="numero text-[0.9375rem] text-tinta-2">
              {plural(filtrados.length, "queda", "quedas")}
              {haQuanto(estado.dados.gerado_em, agora) &&
                ` · lista montada ${haQuanto(estado.dados.gerado_em, agora)}`}
            </p>
            {filtrados.length ? (
              <ul className="mt-3 space-y-3">
                {filtrados.map((i) => (
                  <li
                    key={i.oferta}
                    className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-3 rounded-etiqueta border border-fio bg-etiqueta p-4 sm:grid-cols-[auto_minmax(0,1fr)_auto]"
                  >
                    <Foto imagem={i.imagem} tamanho="size-16" />
                    <div className="min-w-0">
                      <h2 className="line-clamp-2 leading-snug font-semibold">{i.titulo}</h2>
                      <p className="mt-0.5 text-[0.875rem] text-tinta-2">
                        <span className="font-medium text-tinta">{i.loja.nome}</span>
                        {haQuanto(i.visto_em, agora) && ` · visto ${haQuanto(i.visto_em, agora)}`}
                      </p>
                      <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
                        <span className="selo bg-economia-suave font-medium text-economia">
                          <TrendingDown className="size-3.5" aria-hidden />
                          {porcentagem(-i.variacao)} abaixo do habitual desta loja
                        </span>
                      </p>
                      <p className="numero mt-2 text-[0.8125rem] text-tinta-2">
                        Habitual {reais(i.mediana)} · menor {reais(i.menor)} · maior{" "}
                        {reais(i.maior)} em{" "}
                        {plural(i.dias_observados, "dia observado", "dias observados")}
                      </p>
                      {i.preco_original !== null && i.preco_original > i.preco && (
                        <p className="numero mt-1 text-[0.8125rem] text-tinta-3">
                          A loja anuncia “de {reais(i.preco_original)}”
                          {i.preco_original > i.maior && ", acima do maior preço visto aqui"}
                        </p>
                      )}
                    </div>
                    <div className="col-span-full flex items-end justify-between gap-3 sm:col-span-1 sm:flex-col">
                      <div className="sm:text-right">
                        <p className="text-[0.75rem] text-tinta-3">Preço do produto</p>
                        <p className="numero text-[1.25rem] leading-tight font-semibold">
                          {reais(i.preco)}
                        </p>
                      </div>
                      <a
                        href={i.link}
                        target="_blank"
                        rel="noopener noreferrer nofollow"
                        className="botao botao-secundario min-h-10 text-[0.875rem]"
                      >
                        Ver na loja
                        <ArrowUpRight className="size-4" aria-hidden />
                        <span className="sr-only"> {i.loja.nome} (abre em nova aba)</span>
                      </a>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="mt-3 rounded-etiqueta border border-fio bg-etiqueta px-5 py-6">
                {temFiltro ? (
                  <>
                    <h2 className="font-semibold">Nenhuma queda com esses filtros</h2>
                    <button
                      type="button"
                      onClick={() => {
                        setLoja("");
                        setQuedaMinima(0);
                      }}
                      className="botao botao-secundario mt-4"
                    >
                      Limpar os filtros
                    </button>
                  </>
                ) : (
                  <>
                    <h2 className="font-semibold">
                      Nenhuma queda observada nos últimos {dias} dias
                    </h2>
                    <p className="mt-1 max-w-[60ch] text-tinta-2">
                      A lista cresce conforme as pessoas buscam no Zpektral e o mesmo produto é
                      visto mais de uma vez na mesma loja.
                    </p>
                    <Link href="/" className="botao botao-primario mt-4">
                      Fazer uma busca
                    </Link>
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
