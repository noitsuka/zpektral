"use client";

import { ArrowRight, LoaderCircle, X } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState, useTransition, type FormEvent } from "react";

import { useAtalhoBusca } from "@/ganchos/use-atalho-busca";
import { useBuscasRecentes } from "@/ganchos/use-buscas-recentes";
import { useEnviarBusca } from "@/ganchos/use-enviar-busca";
import { ErroApi, enderecoDoCep } from "@/nucleo/api";
import { digitosCep, ehCep, mascararCep } from "@/nucleo/formato";
import type { Endereco } from "@/nucleo/tipos";

// A caixa do globo existe desde o primeiro HTML, então ele chega sem empurrar nada.
const CLASSE_GLOBO =
  "mx-auto aspect-square w-full max-w-[20rem] sm:max-w-[26rem] lg:max-w-none lg:max-h-[min(40rem,74vh)]";

const GloboRotas = dynamic(() => import("@/componentes/globo-rotas").then((m) => m.GloboRotas), {
  ssr: false,
  loading: () => <div aria-hidden className={CLASSE_GLOBO} />,
});

export function InicioBusca() {
  const busca = useEnviarBusca({});
  const [enviando, iniciar] = useTransition();
  useAtalhoBusca();
  const { recentes, remover } = useBuscasRecentes();
  const endereco = useEnderecoDoCep(busca.cep);

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault();
    iniciar(() => busca.enviar());
  }

  return (
    <div className="mx-auto grid w-full max-w-6xl items-center gap-x-12 gap-y-8 px-4 sm:px-6 lg:grid-cols-[minmax(0,33rem)_minmax(0,1fr)]">
      <div>
        <h1 className="text-[2.125rem] leading-[1.08] font-semibold tracking-[-0.025em] [font-stretch:108%] sm:text-[2.875rem]">
          Compare o preço final de cada loja, já com o frete do{" "}
          <span className="whitespace-nowrap">
            <span className="underline decoration-ouro decoration-2 underline-offset-[0.16em]">
              seu CEP
            </span>
            .
          </span>
        </h1>

        <form onSubmit={aoEnviar} role="search" noValidate className="mt-9 sm:mt-11">
          <div className="campo flex flex-col sm:flex-row">
            <label className="group flex min-w-0 flex-1 cursor-text flex-col px-4 pt-3 pb-2.5">
              <span className="text-[0.8125rem] text-apagado transition-colors group-focus-within:text-ouro">
                Produto
              </span>
              <input
                value={busca.consulta}
                onChange={(e) => busca.setConsulta(e.target.value)}
                maxLength={120}
                autoFocus
                autoComplete="off"
                enterKeyHint="search"
                spellCheck={false}
                className="mt-0.5 w-full bg-transparent text-[1.0625rem] outline-none"
              />
            </label>
            <label className="group flex cursor-text flex-col border-t border-traco-forte px-4 pt-3 pb-2.5 sm:w-40 sm:border-t-0 sm:border-l">
              <span className="text-[0.8125rem] text-apagado transition-colors group-focus-within:text-ouro">
                CEP de entrega
              </span>
              <input
                value={busca.cep}
                onChange={(e) => busca.setCep(e.target.value)}
                inputMode="numeric"
                autoComplete="postal-code"
                enterKeyHint="search"
                placeholder="00000-000"
                aria-describedby="ajuda-cep"
                className="mt-0.5 w-full bg-transparent font-mono text-[1rem] tabular-nums outline-none"
              />
            </label>
            <div className="p-1.5 sm:pl-0">
              <button
                type="submit"
                aria-busy={enviando}
                className="botao botao-ouro h-full w-full px-5 text-[0.9375rem] sm:w-auto"
              >
                Comparar
                {enviando ? (
                  <LoaderCircle className="size-4 animate-spin" aria-hidden />
                ) : (
                  <ArrowRight className="size-4" aria-hidden />
                )}
              </button>
            </div>
          </div>
          <p id="ajuda-cep" aria-live="polite" className="mt-3 text-[0.875rem] text-apagado">
            {endereco === "nao_encontrado" ? (
              <span className="text-alerta">Não achamos esse CEP. Confira os números.</span>
            ) : endereco ? (
              <span className="text-tinta">Entrega em {descreverEndereco(endereco)}</span>
            ) : (
              "O CEP é opcional."
            )}
          </p>
          <p role="alert" className="mt-1 min-h-6 text-[0.875rem] font-medium text-falha">
            {busca.erro}
          </p>
        </form>

        {recentes.length > 0 && (
          <section aria-labelledby="titulo-recentes" className="mt-4">
            <h2 id="titulo-recentes" className="text-[0.8125rem] text-tenue">
              Buscas recentes
            </h2>
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {recentes.map((r) => {
                const params = new URLSearchParams({ q: r.q });
                if (r.cep) params.set("cep", r.cep);
                return (
                  <li
                    key={`${r.q}|${r.cep}`}
                    className="group flex items-stretch rounded-quadro border border-traco-forte text-[0.875rem] transition-colors hover:border-[#3d413f]"
                  >
                    <Link
                      href={`/busca?${params}`}
                      className="flex min-h-9 items-center gap-2 pl-3 text-apagado transition-colors group-hover:text-tinta pointer-coarse:min-h-11"
                    >
                      {r.q}
                      {r.cep && (
                        <span className="font-mono text-[0.8125rem] text-tenue">
                          {mascararCep(r.cep)}
                        </span>
                      )}
                    </Link>
                    <button
                      type="button"
                      onClick={() => remover(r)}
                      aria-label={`Remover ${r.q} das buscas recentes`}
                      className="grid w-9 place-items-center text-tenue transition-colors hover:text-tinta pointer-coarse:w-11"
                    >
                      <X className="size-3.5" aria-hidden />
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        )}
      </div>

      <GloboRotas className={CLASSE_GLOBO} />
    </div>
  );
}

function descreverEndereco(e: Endereco): string {
  return [e.logradouro, e.bairro, `${e.cidade}/${e.uf}`].filter(Boolean).join(", ");
}

// Confirma o endereço antes da busca: o frete de cada loja é cotado para este CEP.
function useEnderecoDoCep(cep: string): Endereco | "nao_encontrado" | null {
  const digitos = digitosCep(cep);
  const [achado, setAchado] = useState<{ cep: string; endereco: Endereco | "nao_encontrado" }>();
  useEffect(() => {
    if (!ehCep(digitos)) return;
    const controlador = new AbortController();
    enderecoDoCep(digitos, controlador.signal)
      .then((endereco) => setAchado({ cep: digitos, endereco }))
      .catch((e: Error) => {
        // fora do 404, a falha da consulta não deve impedir a busca: só não mostra o endereço
        if (e instanceof ErroApi && e.status === 404)
          setAchado({ cep: digitos, endereco: "nao_encontrado" });
      });
    return () => controlador.abort();
  }, [digitos]);
  return achado?.cep === digitos ? achado.endereco : null;
}
