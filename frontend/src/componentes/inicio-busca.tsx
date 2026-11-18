"use client";

import { X } from "lucide-react";
import Link from "next/link";
import type { FormEvent } from "react";

import { useAtalhoBusca } from "@/ganchos/use-atalho-busca";
import { useBuscasRecentes } from "@/ganchos/use-buscas-recentes";
import { useEnviarBusca } from "@/ganchos/use-enviar-busca";
import { mascararCep } from "@/nucleo/formato";

export function InicioBusca() {
  const busca = useEnviarBusca({});
  useAtalhoBusca();
  const { recentes, remover } = useBuscasRecentes();

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault();
    busca.enviar();
  }

  return (
    <section aria-labelledby="titulo-inicio" className="mx-auto w-full max-w-3xl">
      <h1
        id="titulo-inicio"
        className="max-w-[22ch] text-[1.875rem] leading-[1.12] font-semibold tracking-[-0.02em] sm:text-[2.625rem]"
      >
        Quanto cada loja cobra, já com o frete até a sua casa.
      </h1>

      <form onSubmit={aoEnviar} role="search" noValidate className="mt-6 sm:mt-8">
        <div className="grid grid-cols-[minmax(0,1fr)_auto] overflow-hidden rounded-etiqueta border-2 border-tinta bg-etiqueta sm:grid-cols-[minmax(0,1fr)_11rem_auto]">
          <label className="col-span-2 block border-b-2 border-tinta px-4 py-3 focus-within:bg-acao-suave/50 focus-within:ring-2 focus-within:ring-acao focus-within:ring-inset sm:col-span-1 sm:border-r-2 sm:border-b-0">
            <span className="rotulo-campo">Produto</span>
            <input
              value={busca.consulta}
              onChange={(e) => busca.setConsulta(e.target.value)}
              maxLength={120}
              autoFocus
              autoComplete="off"
              enterKeyHint="search"
              spellCheck={false}
              placeholder="nome, marca ou modelo"
              className="mt-0.5 block w-full bg-transparent text-[1.125rem] outline-none"
            />
          </label>
          <label className="block px-4 py-3 focus-within:bg-acao-suave/50 focus-within:ring-2 focus-within:ring-acao focus-within:ring-inset sm:border-r-2 sm:border-tinta">
            <span className="rotulo-campo">CEP de entrega</span>
            <input
              value={busca.cep}
              onChange={(e) => busca.setCep(e.target.value)}
              inputMode="numeric"
              autoComplete="postal-code"
              enterKeyHint="search"
              placeholder="00000-000"
              aria-describedby="ajuda-cep"
              className="numero mt-0.5 block w-full bg-transparent text-[1.125rem] font-semibold text-acao outline-none"
            />
          </label>
          <div className="flex items-stretch p-2">
            <button type="submit" className="botao botao-primario w-full px-5 text-base">
              Comparar
            </button>
          </div>
        </div>
        <p id="ajuda-cep" className="mt-2.5 max-w-[62ch] text-[0.9375rem] text-tinta-2">
          O CEP é opcional. Com ele, o total inclui o frete que cada loja cobra até você; sem ele, a
          comparação fica só no preço do produto.
        </p>
        <p role="alert" className="mt-1 min-h-6 text-[0.9375rem] font-medium text-falha">
          {busca.erro}
        </p>
      </form>

      {recentes.length > 0 && (
        <section aria-labelledby="titulo-recentes" className="mt-3">
          <h2 id="titulo-recentes" className="text-[0.875rem] font-semibold text-tinta-2">
            Buscas recentes
          </h2>
          <ul className="mt-2 flex flex-wrap gap-2">
            {recentes.map((r) => {
              const params = new URLSearchParams({ q: r.q });
              if (r.cep) params.set("cep", r.cep);
              return (
                <li
                  key={`${r.q}|${r.cep}`}
                  className="flex items-stretch rounded-controle border border-fio bg-etiqueta text-[0.9375rem] hover:border-borda"
                >
                  <Link
                    href={`/busca?${params}`}
                    className="flex min-h-11 items-center gap-2 pl-3 sm:min-h-9"
                  >
                    {r.q}
                    {r.cep && (
                      <span className="numero text-[0.8125rem] text-tinta-3">
                        {mascararCep(r.cep)}
                      </span>
                    )}
                  </Link>
                  <button
                    type="button"
                    onClick={() => remover(r)}
                    aria-label={`Remover ${r.q} das buscas recentes`}
                    className="grid w-10 place-items-center text-tinta-3 hover:text-tinta"
                  >
                    <X className="size-4" aria-hidden />
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </section>
  );
}
