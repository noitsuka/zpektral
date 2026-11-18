"use client";

import { ArrowUpRight, RotateCw } from "lucide-react";

import {
  CarimboTotal,
  LinhaOferta,
  ListaSelos,
  Parcelas,
  rotuloDoTotal,
  textoDoFrete,
  type Contexto,
} from "@/componentes/linha-oferta";
import { Foto } from "@/componentes/foto";
import { linkDaOferta, totalPara } from "@/nucleo/filtros";
import { dataEntrega, haQuanto, mascararCep, plural, reais } from "@/nucleo/formato";
import type { Oferta } from "@/nucleo/tipos";
import { estadoDoTotal, type Grupo, type MelhorOferta, type MotivoVazio } from "@/nucleo/vitrine";

const idDoGrupo = (chave: string) => `produto-${chave.replace(/[^a-z0-9]/gi, "-")}`;

function faixaDoGrupo(ofertas: Oferta[], contexto: Contexto): string | null {
  const totais = ofertas
    .filter((o) => o.disponivel && o.frete.status !== "nao_entrega")
    .map((o) => totalPara(o, contexto.pagamento));
  const lojas = new Set(ofertas.map((o) => o.loja.id)).size;
  if (lojas < 2 || !totais.length) return null;
  const menor = Math.min(...totais);
  const maior = Math.max(...totais);
  return menor === maior
    ? `${reais(menor)} em ${lojas} lojas`
    : `De ${reais(menor)} a ${reais(maior)} em ${lojas} lojas`;
}

export function CartaoGrupo({
  grupo,
  contexto,
  motivo,
}: {
  grupo: Grupo;
  contexto: Contexto;
  motivo?: string;
}) {
  const [primeira] = grupo.ofertas;
  const comFoto = grupo.ofertas.find((o) => o.imagem) ?? primeira;
  const faixa = faixaDoGrupo(grupo.ofertas, contexto);
  const id = idDoGrupo(grupo.chave);
  const disponiveis = grupo.ofertas.filter((o) => o.disponivel && o.frete.status !== "nao_entrega");
  const maisBarata =
    disponiveis.length > 1
      ? disponiveis.reduce((m, o) =>
          totalPara(o, contexto.pagamento) < totalPara(m, contexto.pagamento) ? o : m,
        )
      : null;
  const extras = [
    primeira.marca,
    primeira.voltagem,
    primeira.condicao !== "novo" ? primeira.condicao : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <section
      id={id}
      aria-labelledby={`${id}-titulo`}
      className="scroll-mt-32 overflow-hidden rounded-etiqueta border border-fio bg-etiqueta"
    >
      <header className="flex gap-3 px-4 pt-4 pb-3">
        <Foto imagem={comFoto.imagem} tamanho="size-16" />
        <div className="min-w-0">
          <h3 id={`${id}-titulo`} className="line-clamp-2 leading-snug font-semibold">
            {primeira.titulo}
          </h3>
          {(extras || faixa) && (
            <p className="mt-1 text-[0.8125rem] text-tinta-2">
              {extras && <span className="capitalize">{extras}</span>}
              {extras && faixa && " · "}
              {faixa && <span className="numero">{faixa}</span>}
            </p>
          )}
          {motivo && <p className="mt-1 text-[0.8125rem] font-medium text-alerta">{motivo}</p>}
        </div>
      </header>
      <ol className="divide-y divide-fio border-t border-fio">
        {grupo.ofertas.map((o) => (
          <li key={o.id}>
            <LinhaOferta oferta={o} contexto={contexto} destaque={o === maisBarata} />
          </li>
        ))}
      </ol>
    </section>
  );
}

function Campo({
  rotulo,
  bordas,
  children,
}: {
  rotulo: string;
  bordas: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`min-w-0 border-tinta px-4 py-3 ${bordas}`}>
      <dt className="rotulo-campo">{rotulo}</dt>
      <dd className="numero mt-1 font-semibold">{children}</dd>
    </div>
  );
}

export function EtiquetaMelhor({
  melhor,
  contexto,
  outrasLojas,
  chaveGrupo,
  provisoria,
}: {
  melhor: MelhorOferta;
  contexto: Contexto;
  outrasLojas: number;
  chaveGrupo: string;
  provisoria: boolean;
}) {
  const { oferta } = melhor;
  const estado = estadoDoTotal(oferta, contexto.cep !== null);
  const total = totalPara(oferta, contexto.pagamento);
  const frete = oferta.frete;
  const t = oferta.totais;
  const quando = oferta.consultado_em ? haQuanto(oferta.consultado_em, contexto.agora) : null;
  const selos = contexto.promocoes(oferta).selos;
  const entrega = frete.entrega_ate
    ? `até ${dataEntrega(frete.entrega_ate)}`
    : (frete.prazo ?? "não informada");

  return (
    <section
      aria-labelledby="titulo-melhor"
      className="overflow-hidden rounded-etiqueta border-2 border-tinta bg-etiqueta"
    >
      <h2
        id="titulo-melhor"
        className="bg-tinta px-4 py-2 text-[0.9375rem] font-semibold text-etiqueta"
      >
        {melhor.motivo === "confirmado"
          ? `Menor total com entrega no CEP ${mascararCep(contexto.cep ?? "")}`
          : "Menor preço, ainda sem o frete"}
      </h2>

      <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-3 p-4 sm:grid-cols-[auto_minmax(0,1fr)_auto]">
        <Foto imagem={oferta.imagem} tamanho="size-16 sm:size-20" />
        <div className="min-w-0">
          <p className="line-clamp-3 text-[1.0625rem] leading-snug font-semibold">
            {oferta.titulo}
          </p>
          <p className="mt-1 text-[0.875rem] text-tinta-2">
            <span className="font-semibold text-tinta">{oferta.loja.nome}</span>
            {oferta.origem === "marketplace" && oferta.vendedor && (
              <> · vendido por {oferta.vendedor}</>
            )}
          </p>
        </div>
        <div className="col-span-full sm:col-span-1 sm:text-right">
          <p className="text-[0.8125rem] text-tinta-2">{rotuloDoTotal(estado, oferta)}</p>
          <p className="numero text-[2rem] leading-none font-bold tracking-tight">{reais(total)}</p>
          <p className="mt-1 text-[0.8125rem] text-tinta-2">
            <Parcelas oferta={oferta} />
          </p>
        </div>
        {selos.length > 0 && (
          <div className="col-span-full">
            <ListaSelos selos={selos} />
          </div>
        )}
      </div>

      <dl className="grid grid-cols-2 border-t-2 border-tinta sm:grid-cols-4">
        <Campo rotulo="Produto" bordas="border-r border-b sm:border-b-0">
          {reais(oferta.preco)}
        </Campo>
        <Campo
          rotulo={contexto.cep ? `Frete ${mascararCep(contexto.cep)}` : "Frete"}
          bordas="border-b sm:border-r sm:border-b-0"
        >
          <span className="flex flex-wrap items-center gap-1.5">
            {estado === "confirmado"
              ? frete.valor
                ? reais(frete.valor)
                : "Grátis"
              : "Não incluído"}
            <CarimboTotal estado={estado} />
          </span>
        </Campo>
        <Campo rotulo="No Pix" bordas="border-r">
          {t?.pix != null && t.pix < t.avista ? (
            reais(t.pix)
          ) : (
            <span className="font-normal text-tinta-2">sem desconto</span>
          )}
        </Campo>
        <Campo rotulo="Entrega" bordas="">
          {estado === "confirmado" ? (
            entrega
          ) : (
            <span className="font-normal text-tinta-2">
              {textoDoFrete(oferta, estado, contexto.cep)}
            </span>
          )}
        </Campo>
      </dl>

      <div className="flex flex-col gap-3 border-t-2 border-tinta p-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-[60ch] text-[0.875rem] text-tinta-2">
          <p>
            {melhor.motivo === "confirmado"
              ? `É o menor total entre ${plural(melhor.comparadas, "oferta com frete confirmado", "ofertas com frete confirmado")} para este CEP.`
              : `É o menor preço entre ${plural(melhor.comparadas, "oferta", "ofertas")}. Informe o CEP para comparar com o frete.`}
            {melhor.segunda && melhor.diferenca !== null && (
              <>
                {" "}
                A próxima loja, {melhor.segunda.loja.nome}, cobra{" "}
                <span className="numero font-semibold text-tinta">{reais(melhor.diferenca)}</span> a
                mais.
              </>
            )}
          </p>
          {(quando || provisoria) && (
            <p className="mt-1 text-tinta-3">
              {quando && `Preço consultado ${quando}. `}
              {provisoria && "Ainda há lojas respondendo; o menor total pode mudar."}
            </p>
          )}
          {outrasLojas > 0 && (
            <a
              href={`#${idDoGrupo(chaveGrupo)}`}
              className="mt-2 inline-block font-medium text-acao underline"
            >
              Comparar este produto em {plural(outrasLojas, "outra loja", "outras lojas")}
            </a>
          )}
        </div>
        <a
          href={linkDaOferta(oferta)}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="botao botao-primario w-full shrink-0 sm:w-auto"
        >
          Ir para {oferta.loja.nome}
          <ArrowUpRight className="size-4" aria-hidden />
          <span className="sr-only"> (abre em nova aba)</span>
        </a>
      </div>
    </section>
  );
}

export function EsqueletoMelhor() {
  return (
    <div aria-hidden className="rounded-etiqueta border-2 border-fio bg-etiqueta">
      <div className="h-9 border-b border-fio" />
      <div className="flex gap-4 p-4">
        <div className="esqueleto size-16 sm:size-20" />
        <div className="flex-1 space-y-2 pt-1">
          <div className="esqueleto h-4 w-4/5" />
          <div className="esqueleto h-4 w-2/5" />
        </div>
        <div className="esqueleto hidden h-9 w-32 sm:block" />
      </div>
      <div className="h-[8.5rem] border-t border-fio sm:h-[7.75rem]" />
    </div>
  );
}

export function EsqueletoGrupos() {
  return (
    <div aria-hidden className="space-y-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="rounded-etiqueta border border-fio bg-etiqueta">
          <div className="flex gap-3 p-4">
            <div className="esqueleto size-16" />
            <div className="flex-1 space-y-2 pt-1">
              <div className="esqueleto h-4 w-3/4" />
              <div className="esqueleto h-3 w-1/3" />
            </div>
          </div>
          <div className="flex justify-between border-t border-fio p-4">
            <div className="esqueleto h-4 w-28" />
            <div className="esqueleto h-6 w-24" />
          </div>
        </div>
      ))}
    </div>
  );
}

const TEXTOS_VAZIO: Record<MotivoVazio, (q: string, cep: string | null) => [string, string]> = {
  nenhuma_loja_respondeu: () => [
    "Nenhuma loja respondeu",
    "As lojas não responderam a tempo ou recusaram a consulta. Tente de novo daqui a alguns minutos.",
  ],
  nada_correspondente: (q) => [
    `Nenhuma loja tem “${q}”`,
    "Confira a grafia ou tente menos palavras, como só a marca e o modelo.",
  ],
  cep_nao_atendido: (_, cep) => [
    `Nenhuma loja entrega no CEP ${mascararCep(cep ?? "")}`,
    "As lojas que têm o produto não atendem esse endereço. Dá para ver os preços sem o frete.",
  ],
  filtros_escondem: () => [
    "Os filtros escondem todas as ofertas",
    "Tire algum filtro para ver as ofertas que as lojas mandaram.",
  ],
};

export function Vazio({
  motivo,
  q,
  cep,
  aoTentarDeNovo,
  aoLimparFiltros,
  hrefSemCep,
}: {
  motivo: MotivoVazio;
  q: string;
  cep: string | null;
  aoTentarDeNovo: () => void;
  aoLimparFiltros: () => void;
  hrefSemCep: string;
}) {
  const [titulo, texto] = TEXTOS_VAZIO[motivo](q, cep);
  return (
    <div className="rounded-etiqueta border border-fio bg-etiqueta px-5 py-8 sm:px-8">
      <h2 className="text-[1.1875rem] font-semibold">{titulo}</h2>
      <p className="mt-1.5 max-w-[60ch] text-tinta-2">{texto}</p>
      <div className="mt-5 flex flex-wrap gap-2">
        {motivo === "nenhuma_loja_respondeu" && (
          <button type="button" onClick={aoTentarDeNovo} className="botao botao-primario">
            <RotateCw className="size-4" aria-hidden />
            Tentar de novo
          </button>
        )}
        {motivo === "filtros_escondem" && (
          <button type="button" onClick={aoLimparFiltros} className="botao botao-primario">
            Limpar os filtros
          </button>
        )}
        {motivo === "cep_nao_atendido" && (
          <a href={hrefSemCep} className="botao botao-secundario">
            Ver preços sem o CEP
          </a>
        )}
      </div>
    </div>
  );
}
