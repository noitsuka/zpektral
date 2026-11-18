import { ChevronDown } from "lucide-react";
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
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pt-6 pb-16 sm:px-6 sm:pt-10">
        <h1 className="text-[1.875rem] leading-tight font-semibold tracking-[-0.02em] [font-stretch:104%] sm:text-[2.25rem]">
          Quedas de preço
        </h1>
        <p className="mt-2 max-w-[60ch] text-apagado">
          Ofertas abaixo do preço habitual da própria loja, segundo o que o Zpektral viu nas buscas
          feitas aqui.
        </p>
        <details className="gaveta-detalhes mt-1 text-[0.9375rem]">
          <summary className="botao-texto cursor-pointer">
            Como a lista é feita
            <ChevronDown className="chevron size-4" aria-hidden />
          </summary>
          <div className="max-w-[62ch] space-y-2 pt-1 pb-2 text-apagado">
            <p>
              Só entram produtos que alguém já buscou, então a lista não cobre todas as lojas nem
              todos os produtos. Uma queda aparece quando o mesmo produto foi visto na mesma loja em
              pelo menos 5 dias, e a última vez foi há menos de 48 horas.
            </p>
            <p>
              O preço é o do produto, sem frete, e vale para a última vez que ele foi visto; confira
              na loja antes de comprar. O total no seu CEP aparece quando você busca.
            </p>
          </div>
        </details>
        <Quedas />
      </main>
      <Rodape />
    </div>
  );
}
