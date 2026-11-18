"use client";

import { RotateCw } from "lucide-react";

import { Foto } from "@/componentes/foto";
import { LinhaOferta, type Contexto } from "@/componentes/linha-oferta";
import { mascararCep, plural, reais } from "@/nucleo/formato";
import type { EstadoFonte } from "@/nucleo/transmissao";
import type { Grupo, MelhorOferta, MotivoVazio } from "@/nucleo/vitrine";

const idDoGrupo = (chave: string) => `produto-${chave.replace(/[^a-z0-9]/gi, "-")}`;

const CONDICAO: Record<string, string> = { usado: "Usado", recondicionado: "Recondicionado" };

export function GrupoProduto({
  grupo,
  contexto,
  motivo,
  omitir,
}: {
  grupo: Grupo;
  contexto: Contexto;
  motivo?: string;
  /** oferta já mostrada no destaque do menor total */
  omitir?: string;
}) {
  const [primeira] = grupo.ofertas;
  const linhas = omitir ? grupo.ofertas.filter((o) => o.id !== omitir) : grupo.ofertas;
  if (!linhas.length) return null;
  const comFoto = grupo.ofertas.find((o) => o.imagem) ?? primeira;
  const id = idDoGrupo(grupo.chave);
  const condicao = primeira.condicao ? CONDICAO[primeira.condicao] : undefined;

  return (
    <section
      id={id}
      aria-labelledby={`${id}-titulo`}
      className="scroll-mt-40 border-t border-traco pt-5 pb-1"
    >
      {/* do tablet para cima a foto fica na coluna do recuo, e a primeira loja encosta no título */}
      <header className="flex items-start gap-4 sm:relative sm:pr-4 sm:pl-20">
        <Foto imagem={comFoto.imagem} tamanho="size-12 sm:absolute sm:top-0 sm:left-4" />
        <div className="min-w-0 pt-0.5">
          <h3 id={`${id}-titulo`} className="line-clamp-2 text-[1rem] leading-snug font-medium">
            {primeira.titulo}
          </h3>
          {(condicao || motivo) && (
            <p className="mt-0.5 text-[0.8125rem] text-alerta">
              {[condicao, motivo].filter(Boolean).join(" · ")}
            </p>
          )}
        </div>
      </header>
      <ol className="divide-y divide-traco sm:pl-16 [&>li:first-child>article]:pt-2 lg:[&>li:first-child>article]:pt-1">
        {linhas.map((o, i) => (
          <li key={o.id}>
            <LinhaOferta oferta={o} contexto={contexto} indice={i} />
          </li>
        ))}
      </ol>
    </section>
  );
}

// O menor total é a primeira linha da lista: mesmo desenho das outras, com o fio e o rótulo em ouro.
export function MelhorTotal({
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
  const confirmado = melhor.motivo === "confirmado";
  const { oferta } = melhor;
  return (
    <section aria-labelledby="titulo-melhor" className="border-t border-ouro/70 pt-4 pb-1">
      <h2 id="titulo-melhor" className="text-[0.8125rem] font-medium text-ouro sm:px-4">
        {confirmado ? "Menor total no seu CEP" : "Menor preço, ainda sem o frete"}
        {provisoria && <span className="font-normal text-apagado"> até agora</span>}
      </h2>
      <div className="mt-2 flex items-start gap-4 sm:relative sm:pr-4 sm:pl-20">
        <Foto imagem={oferta.imagem} tamanho="size-12 sm:absolute sm:top-0 sm:left-4" />
        <p className="line-clamp-2 pt-0.5 text-[1rem] leading-snug font-medium">{oferta.titulo}</p>
      </div>
      <div className="sm:pl-16 [&>article]:pt-2 lg:[&>article]:pt-1">
        <LinhaOferta
          oferta={oferta}
          contexto={contexto}
          principal
          antesDaConta={
            <p>
              {confirmado
                ? `É o menor total entre ${plural(melhor.comparadas, "oferta com frete confirmado", "ofertas com frete confirmado")} para este CEP.`
                : `É o menor preço entre ${plural(melhor.comparadas, "oferta", "ofertas")}. Informe o CEP para comparar com o frete.`}
              {melhor.segunda && melhor.diferenca !== null && (
                <>
                  {" "}
                  A próxima loja, {melhor.segunda.loja.nome}, cobra{" "}
                  <span className="numero whitespace-nowrap text-tinta">
                    {reais(melhor.diferenca)}
                  </span>{" "}
                  a mais.
                </>
              )}
              {outrasLojas > 0 && (
                <>
                  {" "}
                  <a
                    href={`#${idDoGrupo(chaveGrupo)}`}
                    className="text-tinta underline decoration-traco-forte hover:decoration-current"
                  >
                    Comparar em {plural(outrasLojas, "outra loja", "outras lojas")}
                  </a>
                </>
              )}
            </p>
          }
        />
      </div>
    </section>
  );
}

// Mesma estrutura de MelhorTotal nas duas larguras, para a chegada do bloco real não empurrar a lista.
export function EsqueletoMelhor() {
  return (
    <div aria-hidden className="border-t border-traco pt-4 pb-1">
      <div className="esqueleto my-[3px] h-3.5 w-40 sm:mx-4" />
      <div className="mt-2 flex items-start gap-4 sm:relative sm:pr-4 sm:pl-20">
        <div className="esqueleto size-12 shrink-0 sm:absolute sm:top-0 sm:left-4" />
        <div className="flex-1 space-y-2 pt-1">
          <div className="esqueleto h-4 w-3/4" />
          <div className="esqueleto h-4 w-1/2 sm:hidden" />
        </div>
      </div>
      <div className="flex items-start justify-between gap-4 pt-3 pb-3 sm:pt-2 sm:pr-4 sm:pb-1 sm:pl-16">
        <div className="space-y-2">
          <div className="esqueleto h-4 w-28" />
          <div className="esqueleto h-3.5 w-40" />
        </div>
        <div className="flex items-start gap-4">
          <div className="flex flex-col items-end gap-2">
            <div className="esqueleto h-6 w-28" />
            <div className="esqueleto h-3.5 w-24" />
          </div>
          <div className="esqueleto hidden h-9 w-40 sm:block" />
        </div>
      </div>
      <div className="flex items-center justify-between gap-4 pb-3 sm:hidden">
        <div className="esqueleto h-4 w-24" />
        <div className="esqueleto h-11 w-1/2" />
      </div>
    </div>
  );
}

export function EsqueletoGrupos() {
  return (
    <div aria-hidden>
      {[0, 1, 2].map((i) => (
        <div key={i} className="border-t border-traco pt-5 pb-1 sm:px-4">
          <div className="flex gap-4">
            <div className="esqueleto size-12" />
            <div className="flex-1 space-y-2 pt-1">
              <div className="esqueleto h-4 w-3/4" />
              <div className="esqueleto h-3.5 w-1/4" />
            </div>
          </div>
          {[0, 1].map((j) => (
            <div key={j} className="flex justify-between gap-4 py-4 sm:pl-16">
              <div className="space-y-2">
                <div className="esqueleto h-4 w-24" />
                <div className="esqueleto h-3.5 w-40" />
              </div>
              <div className="esqueleto h-6 w-28" />
            </div>
          ))}
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

const SITUACAO: Partial<Record<EstadoFonte, string>> = {
  bloqueada: "recusou a consulta",
  tempo_esgotado: "não respondeu a tempo",
  erro: "respondeu com erro",
};

export function Vazio({
  motivo,
  q,
  cep,
  aoTentarDeNovo,
  aoLimparFiltros,
  aoCorrigirBusca,
  hrefSemCep,
  fora = [],
}: {
  motivo: MotivoVazio;
  q: string;
  cep: string | null;
  aoTentarDeNovo: () => void;
  aoLimparFiltros: () => void;
  aoCorrigirBusca: () => void;
  hrefSemCep: string;
  fora?: { id: string; nome: string; situacao: EstadoFonte }[];
}) {
  const [titulo, texto] = TEXTOS_VAZIO[motivo](q, cep);
  return (
    <div className="border-t border-traco py-10">
      <h2 className="text-[1.1875rem] font-semibold">{titulo}</h2>
      <p className="mt-1.5 max-w-[60ch] text-apagado">{texto}</p>
      <div className="mt-6 flex flex-wrap gap-2">
        {motivo === "nenhuma_loja_respondeu" && (
          <button type="button" onClick={aoTentarDeNovo} className="botao botao-ouro">
            <RotateCw className="size-4" aria-hidden />
            Tentar de novo
          </button>
        )}
        {motivo === "nada_correspondente" && (
          <button type="button" onClick={aoCorrigirBusca} className="botao botao-ouro">
            Mudar a busca
          </button>
        )}
        {motivo === "filtros_escondem" && (
          <button type="button" onClick={aoLimparFiltros} className="botao botao-ouro">
            Limpar os filtros
          </button>
        )}
        {motivo === "cep_nao_atendido" && (
          <a href={hrefSemCep} className="botao botao-ouro">
            Ver preços sem o CEP
          </a>
        )}
      </div>
      {motivo === "nenhuma_loja_respondeu" && fora.length > 0 && (
        <details className="gaveta-detalhes mt-6 text-[0.875rem]">
          <summary className="botao-texto cursor-pointer">Ver as lojas que ficaram de fora</summary>
          <ul className="mt-2 grid gap-x-8 gap-y-1 text-apagado sm:grid-cols-2 lg:grid-cols-3">
            {fora.map((f) => (
              <li key={f.id}>
                <span className="text-tinta">{f.nome}</span> {SITUACAO[f.situacao]}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
