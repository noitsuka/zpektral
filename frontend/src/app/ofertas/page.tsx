import type { Metadata } from "next";

import { Cabecalho, Rodape } from "@/componentes/moldura";
import { Quedas } from "@/componentes/quedas";

export const metadata: Metadata = {
  title: "Quedas de preço",
  description:
    "Preços abaixo do habitual da própria loja, observados nas buscas feitas no Zpektral.",
};

export default function PaginaQuedas() {
  return (
    <div className="flex min-h-dvh flex-col">
      <Cabecalho />
      <main className="mx-auto w-full max-w-4xl flex-1 px-4 pt-6 pb-16 sm:px-6 sm:pt-10">
        <h1 className="text-[1.875rem] leading-tight font-semibold tracking-[-0.02em] sm:text-[2.25rem]">
          Quedas de preço
        </h1>
        <p className="mt-2 max-w-[65ch] text-tinta-2">
          Ofertas abaixo do preço habitual da própria loja, segundo o que o Zpektral viu nas buscas
          feitas aqui. Só entram produtos que alguém já buscou, então a lista não cobre todas as
          lojas nem todos os produtos. O preço é o do produto, sem frete; o total no seu CEP aparece
          quando você busca.
        </p>
        <Quedas />
      </main>
      <Rodape />
    </div>
  );
}
