"use client";

import Link from "next/link";

export default function PaginaErro({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-3 px-4">
      <h1 className="text-[1.5rem] font-semibold [font-stretch:104%]">
        Esta página parou de funcionar
      </h1>
      <p className="text-apagado">
        Tente de novo. Se o erro continuar, volte daqui a alguns minutos.
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button" onClick={reset} className="botao botao-ouro">
          Tentar de novo
        </button>
        <Link href="/" className="botao botao-linha">
          Voltar para a busca
        </Link>
      </div>
    </main>
  );
}
