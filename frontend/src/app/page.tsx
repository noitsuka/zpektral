import Link from "next/link";

import { Cabecalho, Rodape } from "@/componentes/moldura";
import { InicioBusca } from "@/componentes/inicio-busca";

const CAMPOS = [
  {
    rotulo: "Produto",
    texto: "Lido no carrinho da loja sempre que ela permite.",
  },
  {
    rotulo: "Frete para o seu CEP",
    texto: "Cotado para o seu CEP. Quando a loja não confirma o valor, a oferta fica marcada.",
  },
  {
    rotulo: "Pagamento",
    texto: "Desconto no Pix e o custo dos juros do parcelamento, em reais.",
  },
  {
    rotulo: "Total",
    texto: "O que a loja vai cobrar. As ofertas são comparadas por ele.",
  },
];

export default function Inicio() {
  return (
    <div className="flex min-h-dvh flex-col">
      <Cabecalho />

      <main className="flex-1 px-4 pt-6 pb-16 sm:px-6 sm:pt-[9vh]">
        <InicioBusca />

        <section aria-labelledby="titulo-total" className="mx-auto mt-16 w-full max-w-3xl sm:mt-24">
          <h2 id="titulo-total" className="text-[1.1875rem] font-semibold">
            O que entra no total
          </h2>
          <p className="mt-1 max-w-[62ch] text-tinta-2">
            Quando a loja permite, o Zpektral põe o produto no carrinho com o seu CEP e lê o valor
            que seria cobrado. As ofertas aparecem conforme as lojas respondem.
          </p>
          <dl className="mt-4 grid overflow-hidden rounded-etiqueta border-2 border-tinta bg-etiqueta sm:grid-cols-2">
            {CAMPOS.map((c, i) => (
              <div
                key={c.rotulo}
                className={`px-4 py-3.5 ${i > 0 ? "border-t border-tinta" : ""} ${
                  i === 1 ? "sm:border-t-0 sm:border-l" : i === 3 ? "sm:border-l" : ""
                }`}
              >
                <dt className="rotulo-campo">{c.rotulo}</dt>
                <dd className="mt-1 text-[0.9375rem]">{c.texto}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-6 text-[0.9375rem] text-tinta-2">
            Quer ver o que baixou de preço?{" "}
            <Link href="/ofertas" className="font-medium text-acao underline">
              Quedas de preço observadas nas buscas
            </Link>
          </p>
        </section>
      </main>

      <Rodape />
    </div>
  );
}
