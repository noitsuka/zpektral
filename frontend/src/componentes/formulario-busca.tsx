"use client";

import { Search } from "lucide-react";
import type { FormEvent } from "react";

import { useEnviarBusca } from "@/ganchos/use-enviar-busca";

export const ID_CAMPO_CEP = "campo-cep";

export function FormularioBusca({
  consultaInicial,
  cepInicial,
}: {
  consultaInicial?: string;
  cepInicial?: string;
}) {
  const busca = useEnviarBusca({ consultaInicial, cepInicial });

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault();
    busca.enviar();
  }

  return (
    <form onSubmit={aoEnviar} className="w-full" role="search" noValidate>
      <div className="campo flex h-11 w-full items-stretch overflow-hidden">
        <label className="flex min-w-0 flex-1 items-center gap-2.5 pl-3">
          <Search className="size-4 shrink-0 text-tinta-3" aria-hidden />
          <span className="sr-only">Produto</span>
          <input
            value={busca.consulta}
            onChange={(e) => busca.setConsulta(e.target.value)}
            maxLength={120}
            autoComplete="off"
            enterKeyHint="search"
            className="w-full min-w-0 bg-transparent text-base outline-none"
          />
        </label>
        <label className="flex shrink-0 items-center border-l border-fio px-2">
          <span className="sr-only">CEP de entrega</span>
          <input
            id={ID_CAMPO_CEP}
            value={busca.cep}
            onChange={(e) => busca.setCep(e.target.value)}
            inputMode="numeric"
            autoComplete="postal-code"
            placeholder="CEP"
            className="numero w-[9ch] bg-transparent text-base text-acao outline-none sm:w-[6.25rem]"
          />
        </label>
        <button
          type="submit"
          className="grid w-11 shrink-0 place-items-center bg-acao text-sobre-acao hover:bg-acao-forte sm:w-auto sm:px-4 sm:font-semibold"
        >
          <Search className="size-4 sm:hidden" aria-hidden />
          <span className="sr-only sm:not-sr-only">Comparar</span>
        </button>
      </div>
      {busca.erro && (
        <p role="alert" className="mt-1.5 text-[0.875rem] text-falha">
          {busca.erro}
        </p>
      )}
    </form>
  );
}
