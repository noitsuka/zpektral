import type { Metadata } from "next";

import { Cabecalho, Rodape } from "@/componentes/moldura";

export const metadata: Metadata = {
  title: "Privacidade",
  description: "O que o Zpektral guarda, por quanto tempo e com quem compartilha.",
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
      "Cada busca grava o preço de cada oferta na própria loja, com frete e total, a busca em forma simplificada (sem acentos nem maiúsculas) e os 5 primeiros dígitos do CEP, que identificam a região e não o endereço. É isso que permite dizer se o preço de hoje está abaixo ou acima do habitual daquela loja. Se a busca tiver um e-mail ou uma sequência longa de números, como CPF ou telefone, o texto não é gravado. O texto da busca é apagado depois de 14 dias; o restante, depois de 180. O registro não guarda IP, conta nem nada que identifique quem buscou. A página Quedas de preço usa esse mesmo histórico.",
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
      "Ao abrir uma oferta, você vai para o site da loja ou do Buscapé, e a partir daí vale a política de privacidade deles.",
  },
];

export default function Privacidade() {
  return (
    <div className="flex min-h-dvh flex-col">
      <Cabecalho />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 pt-8 pb-16 sm:px-6 sm:pt-14">
        <h1 className="text-[1.875rem] leading-tight font-semibold tracking-[-0.02em] [font-stretch:104%] sm:text-[2.25rem]">
          O que fica guardado, e onde
        </h1>
        <div className="mt-10 max-w-4xl">
          {ITENS.map((item) => (
            <section
              key={item.titulo}
              className="grid gap-1.5 border-t border-traco py-6 sm:grid-cols-[11rem_1fr] sm:gap-8"
            >
              <h2 className="font-medium">{item.titulo}</h2>
              <p className="max-w-[65ch] leading-relaxed text-apagado">{item.texto}</p>
            </section>
          ))}
        </div>
      </main>
      <Rodape />
    </div>
  );
}
