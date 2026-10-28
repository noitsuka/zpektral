"use client";

import { ArrowRight, Search } from "lucide-react";
import type { FormEvent } from "react";

import { useEnviarBusca } from "@/ganchos/use-enviar-busca";

export function FormularioBusca({
  consultaInicial,
  cepInicial,
  autoFocus,
}: {
  consultaInicial?: string;
  cepInicial?: string;
  autoFocus?: boolean;
}) {
  const busca = useEnviarBusca({ consultaInicial, cepInicial });

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault();
    busca.enviar();
  }

  return (
    <form onSubmit={aoEnviar} className="w-full" role="search" noValidate>
      <div className="flex h-11 w-full items-stretch border border-traco-forte bg-fundo transition-colors focus-within:border-ouro/60">
        <label className="flex min-w-0 flex-1 items-center gap-3 px-3.5">
          <Search className="size-4 shrink-0 text-tenue" aria-hidden />
          <span className="sr-only">Produto</span>
          <input
            value={busca.consulta}
            onChange={(e) => busca.setConsulta(e.target.value)}
            maxLength={120}
            autoFocus={autoFocus}
            autoComplete="off"
            enterKeyHint="search"
            className="w-full min-w-0 bg-transparent text-[15px] outline-none"
          />
        </label>
        <label className="flex shrink-0 items-center border-l border-traco-forte px-3">
          <span className="sr-only">CEP de entrega</span>
          <input
            value={busca.cep}
            onChange={(e) => busca.setCep(e.target.value)}
            inputMode="numeric"
            autoComplete="postal-code"
            placeholder="CEP"
            className="w-[5.6rem] bg-transparent font-mono text-[13px] tabular-nums outline-none placeholder:font-sans placeholder:text-tenue sm:w-[6.4rem]"
          />
        </label>
        <button
          type="submit"
          aria-label="Buscar"
          className="botao-ouro grid w-11 shrink-0 place-items-center bg-ouro text-fundo"
        >
          <ArrowRight className="size-4" aria-hidden />
        </button>
      </div>
      {busca.erro && (
        <p role="alert" className="mt-2 text-sm text-falha">
          {busca.erro}
        </p>
      )}
    </form>
  );
}
