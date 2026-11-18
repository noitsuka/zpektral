"use client";

import { ArrowRight, LoaderCircle, Search } from "lucide-react";
import { useTransition, type FormEvent } from "react";

import { useEnviarBusca } from "@/ganchos/use-enviar-busca";

export const ID_CAMPO_CEP = "campo-cep";
export const ID_CAMPO_PRODUTO = "campo-produto";

export function FormularioBusca({
  consultaInicial,
  cepInicial,
}: {
  consultaInicial?: string;
  cepInicial?: string;
}) {
  const busca = useEnviarBusca({ consultaInicial, cepInicial });
  const [enviando, iniciar] = useTransition();

  function aoEnviar(evento: FormEvent) {
    evento.preventDefault();
    iniciar(() => busca.enviar());
  }

  return (
    <form onSubmit={aoEnviar} className="w-full" role="search" noValidate>
      <div className="campo flex h-11 w-full items-stretch overflow-hidden">
        <label className="flex min-w-0 flex-1 cursor-text items-center gap-2.5 pl-3">
          <Search className="size-4 shrink-0 text-tenue" aria-hidden />
          <span className="sr-only">Produto</span>
          <input
            id={ID_CAMPO_PRODUTO}
            value={busca.consulta}
            onChange={(e) => busca.setConsulta(e.target.value)}
            maxLength={120}
            autoComplete="off"
            enterKeyHint="search"
            className="w-full min-w-0 bg-transparent text-[0.9375rem] outline-none"
          />
        </label>
        <label className="flex shrink-0 cursor-text items-center border-l border-traco-forte px-2.5">
          <span className="sr-only">CEP de entrega</span>
          <input
            id={ID_CAMPO_CEP}
            value={busca.cep}
            onChange={(e) => busca.setCep(e.target.value)}
            inputMode="numeric"
            autoComplete="postal-code"
            placeholder="CEP"
            className="w-[9ch] bg-transparent font-mono text-[0.875rem] tabular-nums outline-none placeholder:font-sans sm:w-[6.5rem]"
          />
        </label>
        <button
          type="submit"
          aria-busy={enviando}
          className="botao-ouro grid w-11 shrink-0 place-items-center"
        >
          {enviando ? (
            <LoaderCircle className="size-4 animate-spin" aria-hidden />
          ) : (
            <ArrowRight className="size-4" aria-hidden />
          )}
          <span className="sr-only">Comparar</span>
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
