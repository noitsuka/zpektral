"use client";

import { ArrowUpRight, ChevronDown } from "lucide-react";
import { useId, useState, type CSSProperties, type ReactNode } from "react";

import { GraficoPreco } from "@/componentes/grafico-preco";
import { linkDaOferta, totalPara } from "@/nucleo/filtros";
import {
  dataEntrega,
  haQuanto,
  horaCotacao,
  mascararCep,
  porcentagem,
  reais,
} from "@/nucleo/formato";
import { custoDoParcelamento } from "@/nucleo/juros";
import type { Promocao, Selo } from "@/nucleo/promocao";
import type { Alerta, Importacao, Oferta, Pagamento, PontoHistorico } from "@/nucleo/tipos";
import { estadoDoTotal, type EstadoTotal } from "@/nucleo/vitrine";

export type Contexto = {
  pagamento: Pagamento;
  cep: string | null;
  hoje: string;
  agora: Date;
  historico: Record<string, PontoHistorico[]>;
  promocoes: (o: Oferta) => Promocao;
  // Diferença para a mediana das lojas que vendem o mesmo produto, ou null.
  tipico: (o: Oferta) => number | null;
};

// Sem frete no total, o texto do frete ao lado já diz o porquê (ou o aviso da página, sem CEP);
// "Sem frete" embaixo do preço repetia isso e ainda soava como frete grátis.
function rotuloDoTotal(estado: EstadoTotal, oferta: Oferta): string | null {
  switch (estado) {
    case "confirmado":
      return "Com frete";
    case "estimado":
      return oferta.importacao ? "Total estimado com impostos" : "Total estimado";
    case "nao_entrega":
    case "indisponivel":
      return "Preço do produto";
    default:
      return null;
  }
}

function legendaDoTotal(rotulo: string | null, forma: string | null): string {
  if (!rotulo) return forma ? forma[0].toUpperCase() + forma.slice(1) : "";
  return forma ? `${rotulo}, ${forma}` : rotulo;
}

function textoDoFrete(oferta: Oferta, estado: EstadoTotal, cep: string | null): string {
  const f = oferta.frete;
  switch (estado) {
    case "confirmado":
      return f.valor ? `Frete ${reais(f.valor)}` : "Frete grátis";
    case "estimado":
      if (f.status === "gratis_anunciado")
        return "Frete grátis anunciado, não confirmado no carrinho";
      if (f.status === "estimado") return `Frete internacional ${reais(f.valor ?? 0)}`;
      return f.valor !== null
        ? `Frete ${reais(f.valor)}, mas a loja mudou o valor entre consultas`
        : "Frete não confirmado";
    case "desconhecido":
      return oferta.origem === "comparador" ? "Frete no site da loja" : "Frete não informado";
    case "sem_cep":
      return "Informe o CEP para incluir o frete";
    case "nao_entrega":
      return cep ? `Não entrega no CEP ${mascararCep(cep)}` : "Não entrega no seu CEP";
    case "indisponivel":
      return "Sem estoque nesta loja";
    case "calculando":
      return "Calculando o frete";
  }
}

function prazo(oferta: Oferta): string | null {
  const f = oferta.frete;
  if (f.status !== "calculado") return null;
  if (f.entrega_ate) return `chega até ${dataEntrega(f.entrega_ate)}`;
  return f.prazo ? `entrega ${f.prazo}` : null;
}

// O prazo longo e o frete maior que o produto já se leem no prazo e no valor do frete da linha.
const ALERTAS: Partial<Record<Alerta, string>> = {
  preco_mudou_no_checkout: "O preço mudou no carrinho",
  preco_fora_da_curva: "Bem abaixo das outras lojas, confira o anúncio",
  preco_instavel: "A loja muda o valor entre consultas",
};

function alertasVisiveis(oferta: Oferta): string[] {
  return oferta.alertas.flatMap((a) => ALERTAS[a] ?? []);
}

const TOM: Record<Selo["tom"], string> = {
  economia: "text-exato",
  alerta: "text-alerta",
  neutro: "text-apagado",
};

const CONDICAO: Record<string, string> = { usado: "Usado", recondicionado: "Recondicionado" };

// Na linha cabe um sinal além do frete: o alerta da oferta, se houver, ou a queda verificada.
function sinalDaLinha(oferta: Oferta, promocao: Promocao): { texto: string; tom: string } | null {
  const [alerta] = alertasVisiveis(oferta);
  if (alerta) return { texto: alerta, tom: "text-alerta" };
  const queda = promocao.selos.find(
    (s) => s.tipo === "menor_em_dias" || s.tipo === "abaixo_do_habitual",
  );
  return queda ? { texto: queda.texto, tom: "text-exato" } : null;
}

function seloDoTipico(diferenca: number | null): Selo[] {
  if (diferenca === null) return [];
  const abaixo = diferenca < 0;
  return [
    {
      tipo: abaixo ? "abaixo_do_habitual" : "acima_do_habitual",
      texto: `${porcentagem(Math.abs(diferenca))} ${abaixo ? "abaixo" : "acima"} do preço típico entre as lojas`,
      evidencia: "mediana do total nas lojas que vendem o mesmo produto",
      tom: abaixo ? "economia" : "neutro",
    },
  ];
}

function pagamentoDoTotal(oferta: Oferta, pagamento: Pagamento): string | null {
  const t = oferta.totais;
  if (!t) return null;
  const total = totalPara(oferta, pagamento);
  if (t.pix !== null && total === t.pix && t.pix < t.avista) return "no Pix";
  if (pagamento === "parcelado" && t.parcelado !== null && total === t.parcelado)
    return "parcelado";
  return "no cartão";
}

function Frete({
  oferta,
  estado,
  cep,
}: {
  oferta: Oferta;
  estado: EstadoTotal;
  cep: string | null;
}) {
  // Sem CEP a página inteira já avisa; repetir em cada linha só polui.
  if (estado === "sem_cep") return null;
  if (estado === "confirmado") {
    const gratis = !oferta.frete.valor;
    const quando = prazo(oferta);
    return (
      <p className="numero">
        <span className={gratis ? "text-exato" : "text-tinta"}>
          {textoDoFrete(oferta, estado, cep)}
        </span>
        {quando && <span className="text-apagado"> · {quando}</span>}
      </p>
    );
  }
  const tom =
    estado === "nao_entrega" || estado === "indisponivel"
      ? "text-falha"
      : estado === "estimado"
        ? "text-alerta"
        : "text-apagado";
  return <p className={`numero ${tom}`}>{textoDoFrete(oferta, estado, cep)}</p>;
}

function BotaoLoja({ oferta, principal }: { oferta: Oferta; principal: boolean }) {
  const destino = oferta.origem === "comparador" ? "o Buscapé" : oferta.loja.nome;
  return (
    <a
      href={linkDaOferta(oferta)}
      target="_blank"
      rel="noopener noreferrer nofollow"
      className={`botao w-full px-3 text-[0.875rem] pointer-fine:min-h-9 ${principal ? "botao-ouro" : "botao-linha"}`}
    >
      <span className="truncate">Ir para {destino}</span>
      <ArrowUpRight className="seta size-4 shrink-0" aria-hidden />
      <span className="sr-only">
        {oferta.origem === "comparador" ? `, oferta de ${oferta.loja.nome}` : ""}
        {oferta.vendedor ? `, vendido por ${oferta.vendedor}` : ""} (abre em nova aba)
      </span>
    </a>
  );
}

// Toda linha usa a mesma grade, inclusive a do menor total, para o olho não se reorientar.
const GRADE =
  "grid-cols-[minmax(0,1fr)_auto] [grid-template-areas:'loja_total'_'info_total'_'conta_cta'_'detalhe_detalhe'] sm:grid-cols-[minmax(6rem,9rem)_minmax(0,1fr)_auto_12.5rem] sm:[grid-template-areas:'loja_info_total_cta'_'loja_conta_total_cta'_'detalhe_detalhe_detalhe_detalhe'] lg:grid-cols-[minmax(6.5rem,9rem)_minmax(0,1fr)_8.5rem_9.5rem_12.5rem] lg:[grid-template-areas:'loja_info_conta_total_cta'_'detalhe_detalhe_detalhe_detalhe_detalhe']";

const barra = (largura: string) => (
  <span className={`esqueleto inline-block h-[0.8em] align-middle ${largura}`} />
);

// A mesma grade e as mesmas alturas de texto e de botão da linha real, em todas as larguras,
// para a oferta que chega ocupar o lugar exato do esqueleto.
export function EsqueletoLinha() {
  return (
    <div className={`grid items-center gap-x-4 py-3 sm:gap-x-5 sm:px-4 lg:py-2.5 ${GRADE}`}>
      <p className="self-start font-medium [grid-area:loja] lg:self-center">{barra("w-24")}</p>
      <p className="numero self-start text-[0.875rem] [grid-area:info] lg:self-center">
        {barra("w-40")}
        {/* na coluna estreita o frete com o prazo costuma ocupar duas linhas */}
        <span className="block lg:hidden">{barra("w-24")}</span>
      </p>
      <div className="self-start text-right [grid-area:total] sm:self-center">
        <p className="font-mono text-[1.1875rem] leading-tight">{barra("w-28")}</p>
        <p className="mt-0.5 text-[0.8125rem] leading-snug">{barra("w-24")}</p>
      </div>
      <div className="mt-1 [grid-area:conta] lg:mt-0">
        <span className="botao-texto">{barra("w-20")}</span>
      </div>
      <div className="mt-1 flex justify-end [grid-area:cta] sm:mt-0">
        <span className="botao esqueleto w-full pointer-fine:min-h-9" />
      </div>
    </div>
  );
}

export function LinhaOferta({
  oferta,
  contexto,
  principal = false,
  indice = 0,
  antesDaConta,
}: {
  oferta: Oferta;
  contexto: Contexto;
  principal?: boolean;
  indice?: number;
  antesDaConta?: ReactNode;
}) {
  const [aberta, setAberta] = useState(false);
  const [montada, setMontada] = useState(false);
  const idDetalhes = useId();
  const estado = estadoDoTotal(oferta, contexto.cep !== null);
  const total = totalPara(oferta, contexto.pagamento);
  const promocao = contexto.promocoes(oferta);
  const sinal = sinalDaLinha(oferta, promocao);
  const forma = estado === "nao_entrega" ? null : pagamentoDoTotal(oferta, contexto.pagamento);
  const apagada = estado === "nao_entrega" || estado === "indisponivel";
  // Com CEP, só o total confirmado tem cara de valor final.
  const final = estado === "confirmado" || contexto.cep === null;

  return (
    <article
      aria-label={`${oferta.loja.nome}, ${reais(total)}`}
      data-realce=""
      style={{ "--i": indice } as CSSProperties}
      className={`linha-oferta grid items-center gap-x-4 rounded-quadro py-3 sm:gap-x-5 sm:px-4 lg:py-2.5 ${GRADE} ${
        apagada ? "opacity-60" : ""
      }`}
    >
      <p className="min-w-0 self-start font-medium [grid-area:loja] lg:self-center">
        {oferta.loja.nome}
      </p>

      <div className="min-w-0 space-y-0.5 self-start text-[0.875rem] [grid-area:info] lg:self-center">
        <Frete oferta={oferta} estado={estado} cep={contexto.cep} />
        {sinal && <p className={sinal.tom}>{sinal.texto}</p>}
      </div>

      <div className="self-start text-right [grid-area:total] sm:self-center">
        <p
          className={`font-mono text-[1.1875rem] leading-tight font-medium whitespace-nowrap tabular-nums ${
            final ? "text-tinta" : "text-apagado"
          }`}
        >
          {reais(total)}
        </p>
        <p className="mt-0.5 text-[0.8125rem] leading-snug text-apagado">
          {legendaDoTotal(rotuloDoTotal(estado, oferta), forma)}
        </p>
      </div>

      <div className="mt-1 [grid-area:conta] lg:mt-0">
        <button
          type="button"
          onClick={() => {
            setMontada(true);
            setAberta(!aberta);
          }}
          aria-expanded={aberta}
          aria-controls={idDetalhes}
          className="botao-texto whitespace-nowrap"
        >
          {aberta ? "Fechar a conta" : "Ver a conta"}
          <ChevronDown className="chevron size-4" aria-hidden />
        </button>
      </div>

      <div className="mt-1 flex min-w-0 justify-end [grid-area:cta] sm:mt-0">
        <BotaoLoja oferta={oferta} principal={principal} />
      </div>

      <div
        id={idDetalhes}
        role="region"
        aria-label={`Conta de ${oferta.loja.nome}`}
        className="gaveta [grid-area:detalhe]"
        data-aberta={aberta}
      >
        <div className="min-h-0">
          {montada && (
            <Detalhes
              oferta={oferta}
              contexto={contexto}
              promocao={promocao}
              antes={antesDaConta}
            />
          )}
        </div>
      </div>
    </article>
  );
}

function Linha({
  rotulo,
  valor,
  tom = "",
  antes,
}: {
  rotulo: string;
  valor: string;
  tom?: string;
  antes?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1">
      <dt className="text-apagado">{rotulo}</dt>
      <dd className={`text-right ${tom}`}>
        {antes && `${antes} `}
        <span className={/\d/.test(valor) ? "font-mono tabular-nums" : ""}>{valor}</span>
      </dd>
    </div>
  );
}

function Evidencia({ selo, oferta }: { selo: Selo; oferta: Oferta }) {
  return (
    <li>
      <span className={TOM[selo.tom]}>{selo.texto}</span>
      {selo.tipo === "anunciado" && oferta.preco_original ? (
        <span className="text-apagado">
          : de <s className="text-tenue">{reais(oferta.preco_original)}</s> por{" "}
          {reais(oferta.preco)}.
        </span>
      ) : (
        <span className="text-apagado">: {selo.evidencia}.</span>
      )}
    </li>
  );
}

function Detalhes({
  oferta,
  contexto,
  promocao,
  antes,
}: {
  oferta: Oferta;
  contexto: Contexto;
  promocao: Promocao;
  antes?: ReactNode;
}) {
  const t = oferta.totais;
  const frete = oferta.frete;
  const custo = oferta.parcelamento ? custoDoParcelamento(oferta.preco, oferta.parcelamento) : null;
  const serie = contexto.historico[oferta.id];
  const quando = oferta.consultado_em ? haQuanto(oferta.consultado_em, contexto.agora) : null;
  // O desconto do Pix já aparece na conta. O histórico curto fala do Zpektral, não do preço:
  // sem histórico, o desconto anunciado só não ganha o selo de economia confirmada.
  const selos = [...seloDoTipico(contexto.tipico(oferta)), ...promocao.selos].filter(
    (s) => s.tipo !== "pix" && s.tipo !== "historico_insuficiente",
  );
  const alertas = alertasVisiveis(oferta);
  // na página do anúncio, a loja costuma mostrar primeiro o próprio vendedor
  const parceiro = oferta.origem === "marketplace" ? oferta.vendedor : null;

  const linhas: { rotulo: string; valor: string; tom?: string; antes?: string }[] = [
    { rotulo: "Produto", valor: reais(oferta.preco) },
  ];
  if (oferta.preco_pix !== null && oferta.preco_pix < oferta.preco)
    linhas.push({
      rotulo: "Desconto no Pix",
      valor: reais(oferta.preco - oferta.preco_pix),
      antes: "menos",
      tom: "text-exato",
    });
  if (frete.status === "calculado" || frete.status === "estimado")
    linhas.push({
      rotulo: contexto.cep ? `Frete para ${mascararCep(contexto.cep)}` : "Frete",
      valor: frete.valor ? reais(frete.valor) : "grátis",
    });
  else linhas.push({ rotulo: "Frete", valor: "não incluído", tom: "text-tenue" });
  if (oferta.importacao)
    linhas.push({
      rotulo: "Impostos estimados",
      valor: reais(oferta.importacao.imposto_importacao + oferta.importacao.icms),
    });

  const totais: { rotulo: string; valor: string }[] = [];
  if (t?.pix != null && t.pix < t.avista) totais.push({ rotulo: "No Pix", valor: reais(t.pix) });
  if (t) totais.push({ rotulo: "No cartão, à vista", valor: reais(t.avista) });
  if (oferta.parcelamento && oferta.parcelamento.parcelas > 1 && t?.parcelado != null)
    totais.push({
      rotulo: `Em ${oferta.parcelamento.parcelas}x de ${reais(oferta.parcelamento.valor)}`,
      valor: reais(t.parcelado),
    });

  // o vendedor parceiro já tem a frase própria, que diz também onde achá-lo no anúncio
  const fatos: [string, string][] = [];
  if (oferta.voltagem) fatos.push(["Voltagem", oferta.voltagem]);
  if (oferta.condicao && CONDICAO[oferta.condicao])
    fatos.push(["Condição", CONDICAO[oferta.condicao]]);
  if (quando) fatos.push(["Preço consultado", quando]);
  const grafico = serie?.some((p) => p.dia < contexto.hoje) ?? false;
  const sobre =
    !!antes || alertas.length + selos.length + fatos.length > 0 || grafico || !!parceiro;

  return (
    <div className="mt-4 grid gap-x-12 gap-y-7 border-t border-traco pt-5 pb-2 text-[0.875rem] md:grid-cols-2">
      <section aria-label="A conta">
        <h4 className="font-medium">A conta</h4>
        <dl className="mt-2">
          {linhas.map((l) => (
            <Linha key={l.rotulo} {...l} />
          ))}
        </dl>
        {totais.length > 0 && (
          <dl className="mt-1.5 border-t border-dashed border-traco-forte pt-1.5">
            {totais.map((l) => (
              <Linha key={l.rotulo} {...l} tom="text-tinta" />
            ))}
          </dl>
        )}
        {custo && custo.juros > 0 && (
          <p className="mt-2.5 text-alerta">
            O parcelamento custa {reais(custo.juros)} a mais: {porcentagem(custo.mensal)} ao mês,{" "}
            {porcentagem(custo.anual)} ao ano.
          </p>
        )}
        {oferta.importacao && <Importado importacao={oferta.importacao} />}
        {frete.status === "calculado" && frete.opcoes.length > 1 && (
          <>
            <h4 className="mt-5 font-medium">
              Entrega
              {frete.cotado_em && (
                <span className="font-normal text-apagado">
                  , cotada às {horaCotacao(frete.cotado_em)}
                </span>
              )}
            </h4>
            <ul className="mt-1.5">
              {frete.opcoes.map((o, i) => (
                <li key={`${o.nome}-${i}`} className="flex justify-between gap-4 py-1">
                  <span className="min-w-0 text-apagado">
                    {o.tipo === "retirada" ? "Retirada: " : ""}
                    {o.nome}
                    {o.entrega_ate
                      ? `, até ${dataEntrega(o.entrega_ate)}`
                      : o.prazo
                        ? `, ${o.prazo}`
                        : ""}
                  </span>
                  <span className={`shrink-0 ${o.valor ? "font-mono tabular-nums" : ""}`}>
                    {o.valor ? reais(o.valor) : "grátis"}
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      {sobre && (
        <section aria-label="Sobre o preço" className="min-w-0">
          <h4 className="font-medium">Sobre o preço</h4>
          {antes && <div className="mt-2 text-apagado">{antes}</div>}
          {(alertas.length > 0 || selos.length > 0) && (
            <ul className="mt-2 space-y-1.5">
              {alertas.map((a) => (
                <li key={a} className="text-alerta">
                  {a}.
                </li>
              ))}
              {selos.map((s) => (
                <Evidencia key={`${s.tipo}-${s.texto}`} selo={s} oferta={oferta} />
              ))}
            </ul>
          )}
          {grafico && serie && (
            <div className="mt-4">
              <GraficoPreco pontos={serie} atual={oferta.preco} hoje={contexto.hoje} />
            </div>
          )}
          {parceiro && (
            <p className="mt-4 text-apagado">
              Este preço é do vendedor {parceiro}, parceiro da {oferta.loja.nome}. No anúncio, ele
              pode aparecer entre os outros vendedores.
            </p>
          )}
          {fatos.length > 0 && (
            <dl className="mt-4 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1">
              {fatos.map(([rotulo, valor]) => (
                <div key={rotulo} className="contents">
                  <dt className="text-apagado">{rotulo}</dt>
                  <dd className="min-w-0 break-words">{valor}</dd>
                </div>
              ))}
            </dl>
          )}
        </section>
      )}
    </div>
  );
}

function dolares(centavos: number): string {
  return (centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "USD" });
}

function Importado({ importacao }: { importacao: Importacao }) {
  return (
    <div className="mt-3 border-t border-traco pt-2">
      <dl>
        <Linha rotulo="Produto em dólar" valor={dolares(importacao.produto_usd)} />
        <Linha rotulo="Dólar (PTAX)" valor={reais(Math.round(importacao.cotacao_dolar * 100))} />
        <Linha rotulo="Imposto de importação" valor={reais(importacao.imposto_importacao)} />
        <Linha rotulo="ICMS" valor={reais(importacao.icms)} />
      </dl>
      <p className="mt-2 text-apagado">
        Estimativa fora do Remessa Conforme. A Receita define o valor final na chegada.
      </p>
    </div>
  );
}
