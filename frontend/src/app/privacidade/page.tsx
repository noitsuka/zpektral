import type { Metadata } from "next";
import Link from "next/link";

import { Logo } from "@/componentes/logo";

export const metadata: Metadata = {
  title: "Privacidade",
  description: "O que o zpektral guarda, por quanto tempo e com quem compartilha.",
};

const ITENS = [
  {
    titulo: "CEP",
    texto:
      "Fica salvo no seu navegador para a próxima busca e vai para a API a cada consulta. A API repassa o CEP às lojas, na simulação de carrinho que calcula o frete, e à BrasilAPI e ao ViaCEP para descobrir a cidade. Para apagar, limpe os dados do site no navegador.",
  },
  {
    titulo: "Buscas recentes",
    texto:
      "As últimas seis buscas ficam só no seu navegador, para aparecer na página inicial. Não vão para a API. O botão de cada uma apaga aquela busca da lista.",
  },
  {
    titulo: "Histórico de preços",
    texto:
      "Cada busca grava o preço de cada oferta na própria loja, com frete, total e os 5 primeiros dígitos do CEP, que identificam a região e não o endereço. É isso que permite dizer se o preço de hoje está abaixo ou acima do habitual daquela loja. Nada liga esse registro a quem buscou, e registros com mais de 180 dias são apagados.",
  },
  {
    titulo: "Endereço IP",
    texto:
      "Usado só para limitar o número de buscas por pessoa. Fica na memória do servidor, nunca é gravado em disco nem em log e some quando o processo reinicia.",
  },
  {
    titulo: "O que não existe aqui",
    texto:
      "Conta, login, cookies de rastreamento, anúncios e ferramentas de analytics. A página não carrega scripts de terceiros.",
  },
  {
    titulo: "Lojas",
    texto:
      "Ao abrir uma oferta você vai para o site da loja ou do Buscapé, e a partir daí vale a política de privacidade deles.",
  },
];

export default function Privacidade() {
  return (
    <div className="min-h-dvh">
      <header className="border-b border-traco">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3.5 sm:px-6">
          <Logo />
          <Link href="/" className="rotulo text-apagado transition-colors hover:text-tinta">
            Voltar
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-14 sm:px-6">
        <p className="rotulo text-tenue">Privacidade</p>
        <h1 className="mt-3 text-3xl font-bold tracking-[-0.03em] sm:text-4xl">
          O que fica guardado, e onde
        </h1>
        <dl className="mt-10 divide-y divide-traco border-y border-traco">
          {ITENS.map((item) => (
            <div key={item.titulo} className="grid gap-2 py-6 sm:grid-cols-[12rem_1fr] sm:gap-8">
              <dt className="font-semibold">{item.titulo}</dt>
              <dd className="text-[15px] leading-relaxed text-apagado">{item.texto}</dd>
            </div>
          ))}
        </dl>
      </main>
    </div>
  );
}
