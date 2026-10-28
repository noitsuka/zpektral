"use client";

import {
  ArrowUpRight,
  CircleAlert,
  History,
  PackageX,
  ReceiptText,
  TrendingDown,
  Truck,
} from "lucide-react";
import { type CSSProperties, useId, useState } from "react";

import { linkDaOferta, totalPara } from "@/nucleo/filtros";
import { dataEntrega, horaCotacao, mascararCep, porcentagem, reais } from "@/nucleo/formato";
import { GraficoPreco } from "@/componentes/grafico-preco";
import { custoDoParcelamento } from "@/nucleo/juros";
import { avaliarHistorico, type AvaliacaoHistorico } from "@/nucleo/tendencia";
import type { Alerta, Frete, Importacao, Oferta, Pagamento, PontoHistorico } from "@/nucleo/tipos";

const ALERTAS: Record<Alerta, string> = {
  prazo_longo: "Prazo acima de 60 dias",
  frete_maior_que_produto: "Frete maior que o produto",
  preco_mudou_no_checkout: "Preço mudou no checkout",
  preco_fora_da_curva: "Bem abaixo das outras lojas, confira o anúncio",
  preco_instavel: "A loja muda o valor entre consultas",
};

const CONDICAO: Record<string, string> = { usado: "Usado", recondicionado: "Recondicionado" };

function linhaFrete(f: Frete, comparador: boolean): { texto: string; tom: string } {
  if (comparador && (f.status === "nao_informado" || f.status === "sem_cep")) {
    return { texto: "Frete calculado no site da loja", tom: "text-tenue" };
  }
  switch (f.status) {
    case "calculado":
      return {
        texto: f.valor ? `Frete ${reais(f.valor)}` : "Frete grátis",
        tom: f.valor ? "text-apagado" : "text-exato",
      };
    case "gratis_anunciado":
      return { texto: "Frete grátis anunciado", tom: "text-apagado" };
    case "nao_entrega":
      return { texto: "Não entrega no seu CEP", tom: "text-falha" };
    case "sem_cep":
      return { texto: "Informe o CEP para ver o frete", tom: "text-tenue" };
    case "calculando":
      return { texto: "Calculando o frete", tom: "text-ouro" };
    case "estimado":
      return { texto: `Frete internacional ${reais(f.valor ?? 0)}`, tom: "text-apagado" };
    default:
      return { texto: "Frete não informado pela loja", tom: "text-tenue" };
  }
}

function rotuloDoTotal(oferta: Oferta): string {
  if (oferta.total_exato) return "Total no seu CEP";
  if (oferta.importacao) return "Total estimado";
  if (oferta.origem === "comparador") return "Preço no Buscapé";
  return "Preço sem o frete";
}

function dolares(centavos: number): string {
  return (centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "USD" });
}

function Linha({
  rotulo,
  valor,
  tom = "",
  ordem,
}: {
  rotulo: string;
  valor: string;
  tom?: string;
  ordem: number;
}) {
  return (
    <div
      className="conta-linha flex justify-between gap-4"
      style={{ "--i": ordem } as CSSProperties}
    >
      <dt className="text-apagado">{rotulo}</dt>
      <dd className={`text-right tabular-nums ${tom}`}>{valor}</dd>
    </div>
  );
}

function PrecoNestaLoja({
  oferta,
  historico,
  avaliacao,
  hoje,
}: {
  oferta: Oferta;
  historico: PontoHistorico[];
  avaliacao: AvaliacaoHistorico;
  hoje: string;
}) {
  const pontos = [...historico.filter((p) => p.dia < hoje), { dia: hoje, preco: oferta.preco }];
  return (
    <div className="mt-3 border-t border-traco pt-2.5 font-sans">
      <p className="flex flex-wrap justify-between gap-x-4 text-[12px] text-tenue">
        <span>Preço nesta loja nos últimos {avaliacao.dias} dias</span>
        <span className="font-mono tabular-nums">
          menor {reais(avaliacao.menor)} · habitual {reais(Math.round(avaliacao.mediana))}
        </span>
      </p>
      <GraficoPreco pontos={pontos} mediana={avaliacao.mediana} />
    </div>
  );
}

function Conta({
  oferta,
  cep,
  historico,
  avaliacao,
  hoje,
}: {
  oferta: Oferta;
  cep: string | null;
  historico?: PontoHistorico[];
  avaliacao: AvaliacaoHistorico | null;
  hoje: string;
}) {
  const t = oferta.totais;
  const frete = oferta.frete;
  const custo = oferta.parcelamento ? custoDoParcelamento(oferta.preco, oferta.parcelamento) : null;
  const linhas: { rotulo: string; valor: string; tom?: string }[] = [
    { rotulo: "Produto", valor: reais(oferta.preco) },
  ];
  if (oferta.preco_pix !== null && oferta.preco_pix < oferta.preco) {
    linhas.push({
      rotulo: "Desconto no Pix",
      valor: `− ${reais(oferta.preco - oferta.preco_pix)}`,
      tom: "text-exato",
    });
  }
  if (frete.status === "calculado" || frete.status === "estimado") {
    linhas.push({
      rotulo: cep ? `Frete para ${mascararCep(cep)}` : "Frete",
      valor: frete.valor ? reais(frete.valor) : "grátis",
      tom: frete.valor ? "" : "text-exato",
    });
  } else {
    linhas.push({ rotulo: "Frete", valor: "não incluído", tom: "text-tenue" });
  }
  if (oferta.importacao) {
    linhas.push({
      rotulo: "Impostos estimados",
      valor: reais(oferta.importacao.imposto_importacao + oferta.importacao.icms),
    });
  }

  const totais: { rotulo: string; valor: string; tom?: string }[] = [];
  if (t?.pix != null && t.pix < t.avista) totais.push({ rotulo: "No Pix", valor: reais(t.pix) });
  if (t) totais.push({ rotulo: "No cartão, à vista", valor: reais(t.avista) });
  if (oferta.parcelamento && t?.parcelado != null) {
    totais.push({
      rotulo: `Em ${oferta.parcelamento.parcelas}x de ${reais(oferta.parcelamento.valor)}`,
      valor: reais(t.parcelado),
    });
  }

  return (
    <div className="conta mt-3 rounded-peca border border-traco bg-fundo/60 p-3 font-mono text-[12px]">
      <dl className="space-y-1.5">
        {linhas.map((l, i) => (
          <Linha key={l.rotulo} {...l} ordem={i} />
        ))}
      </dl>
      {totais.length > 0 && (
        <dl className="mt-2.5 space-y-1.5 border-t border-dashed border-traco-forte pt-2.5">
          {totais.map((l, i) => (
            <Linha key={l.rotulo} {...l} ordem={linhas.length + i} tom="text-tinta" />
          ))}
        </dl>
      )}
      {custo && custo.juros > 0 && (
        <p
          className="conta-linha mt-2.5 font-sans text-[12.5px] leading-relaxed text-alerta"
          style={{ "--i": linhas.length + totais.length } as CSSProperties}
        >
          O parcelamento custa {reais(custo.juros)} a mais: {porcentagem(custo.mensal)} ao mês,{" "}
          {porcentagem(custo.anual)} ao ano.
        </p>
      )}
      {historico && avaliacao && (
        <PrecoNestaLoja oferta={oferta} historico={historico} avaliacao={avaliacao} hoje={hoje} />
      )}
      {oferta.importacao && <Importado importacao={oferta.importacao} />}
      {frete.status === "calculado" && frete.opcoes.length > 1 && (
        <div className="mt-3 border-t border-traco pt-2.5">
          <p className="font-sans text-[12px] text-tenue">
            Opções de entrega
            {frete.cotado_em ? `, consultadas às ${horaCotacao(frete.cotado_em)}` : ""}
          </p>
          <ul className="mt-1.5 space-y-1">
            {frete.opcoes.map((o, i) => (
              <li key={`${o.nome}-${i}`} className="flex justify-between gap-4">
                <span className="truncate text-apagado">
                  {o.tipo === "retirada" ? "Retirada: " : ""}
                  {o.nome}
                  {o.entrega_ate
                    ? `, até ${dataEntrega(o.entrega_ate)}`
                    : o.prazo
                      ? `, ${o.prazo}`
                      : ""}
                </span>
                <span className="shrink-0 tabular-nums">{o.valor ? reais(o.valor) : "grátis"}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Importado({ importacao }: { importacao: Importacao }) {
  return (
    <div className="mt-3 border-t border-traco pt-2.5">
      <dl className="space-y-1">
        <div className="flex justify-between gap-4">
          <dt className="text-apagado">Produto em dólar</dt>
          <dd>{dolares(importacao.produto_usd)}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-apagado">Dólar (PTAX)</dt>
          <dd>{reais(Math.round(importacao.cotacao_dolar * 100))}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-apagado">Imposto de importação</dt>
          <dd>{reais(importacao.imposto_importacao)}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-apagado">ICMS</dt>
          <dd>{reais(importacao.icms)}</dd>
        </div>
      </dl>
      <p className="mt-2 font-sans text-[12px] leading-relaxed text-tenue">
        Estimativa fora do Remessa Conforme. A Receita define o valor final na chegada.
      </p>
    </div>
  );
}

export function LinhaOferta({
  oferta,
  pagamento,
  cep = null,
  diferencaDoTipico = null,
  historico,
  hoje = "",
  indice = 0,
}: {
  oferta: Oferta;
  pagamento: Pagamento;
  cep?: string | null;
  diferencaDoTipico?: number | null;
  historico?: PontoHistorico[];
  hoje?: string;
  indice?: number;
}) {
  const [aberta, setAberta] = useState(false);
  const [montada, setMontada] = useState(false);
  const [imagemFalhou, setImagemFalhou] = useState(false);
  const idConta = useId();
  const total = totalPara(oferta, pagamento);
  const comparador = oferta.origem === "comparador";
  const frete = linhaFrete(oferta.frete, comparador);
  const noCarrinho = oferta.origem === "marketplace" && oferta.link_carrinho;
  const indisponivel = !oferta.disponivel || oferta.frete.status === "nao_entrega";
  const t = oferta.totais;
  const economiaPix = t?.pix != null && t.pix < t.avista ? t.avista - t.pix : 0;
  const custo = oferta.parcelamento ? custoDoParcelamento(oferta.preco, oferta.parcelamento) : null;
  const avaliacao = historico && hoje ? avaliarHistorico(oferta.preco, historico, hoje) : null;
  const sinalDeHistorico = avaliacao && avaliacao.situacao !== "estavel";

  return (
    <article
      style={{ "--i": indice } as CSSProperties}
      className={`linha-oferta grid grid-cols-[3.5rem_1fr] gap-x-4 gap-y-3 border-b border-traco px-4 py-4 sm:grid-cols-[4rem_1fr_auto] ${
        indisponivel ? "opacity-55" : ""
      }`}
    >
      <div className="row-span-2 size-14 overflow-hidden rounded-peca bg-white sm:row-span-1 sm:size-16">
        {oferta.imagem && !imagemFalhou ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={oferta.imagem}
            alt=""
            loading="lazy"
            decoding="async"
            referrerPolicy="no-referrer"
            onError={() => setImagemFalhou(true)}
            className="foto-oferta size-full object-contain p-1"
          />
        ) : (
          <div className="grid size-full place-items-center bg-relevo">
            <PackageX className="size-6 text-tenue" aria-hidden />
          </div>
        )}
      </div>

      <div className="min-w-0">
        <h3 className="line-clamp-2 text-[15px] leading-snug font-medium text-tinta">
          {oferta.titulo}
        </h3>
        <p className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[13px] text-apagado">
          <span className="font-medium text-tinta/90">{oferta.loja.nome}</span>
          {oferta.origem === "marketplace" && oferta.vendedor && (
            <span className="text-tenue">· vendido por {oferta.vendedor}</span>
          )}
          {comparador && <span className="text-tenue">· pelo Buscapé</span>}
          {oferta.origem === "importado" && <span className="text-alerta">· importado</span>}
          {oferta.voltagem && <span className="etiqueta font-mono">{oferta.voltagem}</span>}
          {oferta.condicao && CONDICAO[oferta.condicao] && (
            <span className="etiqueta text-alerta">{CONDICAO[oferta.condicao]}</span>
          )}
        </p>
        <p
          className={`mt-2 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[13px] ${frete.tom}`}
        >
          <Truck className="size-3.5 shrink-0" aria-hidden />
          <span>{frete.texto}</span>
          {oferta.frete.status === "calculado" && oferta.frete.entrega_ate && (
            <span className="text-tenue">· chega até {dataEntrega(oferta.frete.entrega_ate)}</span>
          )}
          {oferta.frete.status === "calculado" &&
            !oferta.frete.entrega_ate &&
            oferta.frete.prazo && <span className="text-tenue">· {oferta.frete.prazo}</span>}
        </p>
        {(diferencaDoTipico !== null || economiaPix > 0 || sinalDeHistorico) && (
          <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px]">
            {avaliacao?.situacao === "menor" && (
              <span className="inline-flex items-center gap-1 text-exato">
                <History className="size-3.5" aria-hidden />
                Menor preço desta loja em {avaliacao.dias} dias
              </span>
            )}
            {avaliacao?.situacao === "abaixo" && (
              <span className="inline-flex items-center gap-1 text-exato">
                <History className="size-3.5" aria-hidden />
                {porcentagem(-avaliacao.variacao)} abaixo do habitual desta loja
              </span>
            )}
            {avaliacao?.situacao === "acima" && (
              <span className="inline-flex items-center gap-1 text-alerta">
                <History className="size-3.5" aria-hidden />
                {porcentagem(avaliacao.variacao)} acima do habitual desta loja
              </span>
            )}
            {diferencaDoTipico !== null && diferencaDoTipico < 0 && (
              <span className="inline-flex items-center gap-1 text-exato">
                <TrendingDown className="size-3.5" aria-hidden />
                {porcentagem(-diferencaDoTipico)} abaixo do preço típico
              </span>
            )}
            {diferencaDoTipico !== null && diferencaDoTipico > 0 && (
              <span className="text-tenue">
                {porcentagem(diferencaDoTipico)} acima do preço típico
              </span>
            )}
            {economiaPix > 0 && (
              <span className="text-apagado">Pix economiza {reais(economiaPix)}</span>
            )}
          </p>
        )}
        {oferta.alertas.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {oferta.alertas.map((a) => (
              <li
                key={a}
                className="inline-flex items-center gap-1 rounded-peca bg-alerta-suave px-2 py-0.5 text-[12px] text-alerta"
              >
                <CircleAlert className="size-3" aria-hidden />
                {ALERTAS[a]}
              </li>
            ))}
          </ul>
        )}
        <button
          type="button"
          onClick={() => {
            setMontada(true);
            setAberta(!aberta);
          }}
          aria-expanded={aberta}
          aria-controls={idConta}
          className="botao-conta mt-2.5 inline-flex items-center gap-1.5 text-[13px] text-tenue"
        >
          <ReceiptText className="size-3.5" aria-hidden />
          {aberta ? "Fechar a conta" : "Ver a conta"}
        </button>
        <div id={idConta} className="gaveta" data-aberta={aberta}>
          <div className="min-h-0">
            {montada && (
              <Conta
                oferta={oferta}
                cep={cep}
                historico={historico}
                avaliacao={avaliacao}
                hoje={hoje}
              />
            )}
          </div>
        </div>
      </div>

      <div className="col-start-2 flex items-end justify-between gap-4 sm:col-start-3 sm:flex-col sm:items-end sm:justify-start sm:gap-2.5 sm:text-right">
        <div>
          <p className="text-[12px] text-tenue">{rotuloDoTotal(oferta)}</p>
          <p className="preco font-mono text-xl font-semibold tracking-tight whitespace-nowrap text-tinta tabular-nums">
            {reais(total)}
          </p>
          {oferta.parcelamento && (
            <p className="mt-0.5 text-[12px] whitespace-nowrap text-tenue tabular-nums">
              {oferta.parcelamento.parcelas}x {reais(oferta.parcelamento.valor)}
              {custo && custo.mensal > 0 ? (
                <span className="text-alerta"> · {porcentagem(custo.mensal)} a.m.</span>
              ) : (
                <span className="text-apagado"> sem juros</span>
              )}
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <a
            href={linkDaOferta(oferta)}
            target="_blank"
            rel="noopener noreferrer nofollow"
            className="botao-loja inline-flex items-center gap-1 rounded-peca border border-traco-forte px-3 py-1.5 text-[13px] font-medium text-tinta"
          >
            {noCarrinho ? "Abrir oferta" : comparador ? "Ver no Buscapé" : "Ver na loja"}
            <ArrowUpRight className="seta size-3.5" aria-hidden />
            <span className="sr-only">
              {noCarrinho
                ? `${oferta.loja.nome}, vendido por ${oferta.vendedor ?? "parceiro"}, no carrinho da loja`
                : oferta.loja.nome}{" "}
              (abre em nova aba)
            </span>
          </a>
          {noCarrinho && (
            <a
              href={oferta.link}
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="text-[12px] text-tenue underline-offset-2 hover:text-tinta hover:underline"
            >
              página do produto
            </a>
          )}
        </div>
      </div>
    </article>
  );
}
