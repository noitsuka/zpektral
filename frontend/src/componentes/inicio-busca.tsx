"use client";

import { ArrowRight, X } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import type { FormEvent } from "react";

import { useAtalhoBusca } from "@/ganchos/use-atalho-busca";
import { useBuscasRecentes } from "@/ganchos/use-buscas-recentes";
import { useEnviarBusca } from "@/ganchos/use-enviar-busca";
import { mascararCep } from "@/nucleo/formato";

const CLASSE_GLOBO =
  "-mx-5 aspect-square max-h-[22rem] w-[calc(100%+2.5rem)] sm:mx-auto sm:max-h-[28rem] sm:w-full lg:order-2 lg:max-h-[min(42rem,78vh)]";

const GloboRotas = dynamic(() => import("@/componentes/globo-rotas").then((m) => m.GloboRotas), {
  ssr: false,
  loading: () => <div aria-hidden className={CLASSE_GLOBO} />,
});

export function InicioBusca() {
  const busca = useEnviarBusca({});
  useAtalhoBusca();
  const { recentes, remover } = useBuscasRecentes();

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault();
    busca.enviar();
  }

  return (
    <div className="mx-auto grid w-full max-w-6xl items-center gap-2 px-5 sm:px-8 lg:grid-cols-[minmax(0,32rem)_minmax(0,1fr)] lg:gap-6">
      <GloboRotas className={CLASSE_GLOBO} />
      <div className="lg:order-1">
        <h1 className="text-[2.1rem] leading-[1.12] font-semibold tracking-[-0.02em] [font-stretch:108%] sm:text-[2.6rem]">
          Compare o preço final de cada loja, já com o frete do{" "}
          <span className="whitespace-nowrap">
            <span className="underline decoration-ouro decoration-2 underline-offset-[0.2em]">
              seu CEP
            </span>
            .
          </span>
        </h1>

        <form onSubmit={aoEnviar} role="search" noValidate className="mt-10">
          <div className="flex flex-col border border-traco-forte bg-fundo/80 backdrop-blur-sm transition-colors focus-within:border-ouro/70 sm:flex-row">
            <label className="group flex min-w-0 flex-1 flex-col px-4 pt-3 pb-2.5">
              <span className="rotulo text-tenue transition-colors group-focus-within:text-ouro">
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
                className="mt-1 w-full bg-transparent text-[17px] outline-none"
              />
            </label>
            <label className="group flex flex-col border-t border-traco-forte px-4 pt-3 pb-2.5 sm:w-40 sm:border-t-0 sm:border-l">
              <span className="rotulo text-tenue transition-colors group-focus-within:text-ouro">
                CEP de entrega
              </span>
              <input
                value={busca.cep}
                onChange={(e) => busca.setCep(e.target.value)}
                inputMode="numeric"
                autoComplete="postal-code"
                placeholder="00000-000"
                className="mt-1 w-full bg-transparent font-mono text-[16px] tabular-nums outline-none placeholder:text-white/20"
              />
            </label>
            <button
              type="submit"
              aria-label="Buscar"
              className="botao-ouro grid h-12 place-items-center bg-ouro text-fundo sm:h-auto sm:w-16"
            >
              <ArrowRight className="size-5" aria-hidden />
            </button>
          </div>
          <p role={busca.erro ? "alert" : undefined} className="mt-2 min-h-5 text-sm text-falha">
            {busca.erro}
          </p>
        </form>

        {recentes.length > 0 && (
          <section aria-label="Buscas recentes" className="mt-4">
            <h2 className="rotulo text-tenue">Buscas recentes</h2>
            <ul className="mt-2.5 flex flex-wrap gap-1.5">
              {recentes.map((r) => {
                const params = new URLSearchParams({ q: r.q });
                if (r.cep) params.set("cep", r.cep);
                return (
                  <li
                    key={`${r.q}|${r.cep}`}
                    className="group flex items-stretch border border-traco-forte bg-fundo/70 text-[13px] transition-colors hover:border-tenue"
                  >
                    <Link
                      href={`/busca?${params}`}
                      className="flex items-baseline gap-2 py-1.5 pl-2.5 text-apagado transition-colors group-hover:text-tinta"
                    >
                      {r.q}
                      {r.cep && (
                        <span className="font-mono text-[11px] text-tenue">
                          {mascararCep(r.cep)}
                        </span>
                      )}
                    </Link>
                    <button
                      type="button"
                      onClick={() => remover(r)}
                      aria-label={`Remover ${r.q} das recentes`}
                      className="grid w-7 place-items-center text-tenue transition-colors hover:text-tinta"
                    >
                      <X className="size-3" aria-hidden />
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
