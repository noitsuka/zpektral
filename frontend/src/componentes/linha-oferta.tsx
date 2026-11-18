"use client";

import {
  ArrowUpRight,
  BadgeCheck,
  ChevronDown,
  CircleAlert,
  CircleHelp,
  Clock,
  History,
  MapPinOff,
  PackageX,
  Tag,
  TrendingDown,
  TrendingUp,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { useId, useState } from "react";

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

const CARIMBOS: Record<EstadoTotal, { texto: string; cor: string; Icone: LucideIcon }> = {
  confirmado: { texto: "Confirmado", cor: "text-confirmado", Icone: BadgeCheck },
  estimado: { texto: "Estimado", cor: "text-alerta", Icone: CircleHelp },
  desconhecido: { texto: "Sem cotação", cor: "text-tinta-2", Icone: CircleHelp },
  sem_cep: { texto: "Sem CEP", cor: "text-tinta-2", Icone: MapPinOff },
  nao_entrega: { texto: "Não entrega", cor: "text-falha", Icone: MapPinOff },
  indisponivel: { texto: "Esgotado", cor: "text-falha", Icone: PackageX },
  calculando: { texto: "Calculando", cor: "text-tinta-2", Icone: Clock },
};

export function CarimboTotal({ estado }: { estado: EstadoTotal }) {
  const { texto, cor, Icone } = CARIMBOS[estado];
  return (
    <span className={`carimbo ${cor}`}>
      <Icone className="size-3" strokeWidth={2.5} aria-hidden />
      {texto}
    </span>
  );
}

export function rotuloDoTotal(estado: EstadoTotal, oferta: Oferta): string {
  switch (estado) {
    case "confirmado":
      return "Total no seu CEP";
    case "estimado":
      return oferta.importacao ? "Total estimado com impostos" : "Total estimado";
    case "nao_entrega":
    case "indisponivel":
      return "Preço do produto";
    default:
      return "Preço sem frete";
  }
}

export function textoDoFrete(oferta: Oferta, estado: EstadoTotal, cep: string | null): string {
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
      return oferta.origem === "comparador"
        ? "Frete calculado no site da loja"
        : "A loja não informou o frete";
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
  if (f.entrega_ate) return `Chega até ${dataEntrega(f.entrega_ate)}`;
  return f.prazo ? `Entrega ${f.prazo}` : null;
}

const ALERTAS: Record<Alerta, string> = {
  prazo_longo: "Prazo acima de 60 dias",
  frete_maior_que_produto: "Frete maior que o produto",
  preco_mudou_no_checkout: "O preço mudou no carrinho",
  preco_fora_da_curva: "Bem abaixo das outras lojas, confira o anúncio",
  preco_instavel: "A loja muda o valor entre consultas",
};

const ICONE_SELO: Record<Selo["tipo"], LucideIcon> = {
  menor_em_dias: History,
  abaixo_do_habitual: TrendingDown,
  acima_do_habitual: TrendingUp,
  anunciado: Tag,
  sem_respaldo: CircleAlert,
  historico_insuficiente: CircleHelp,
  pix: Wallet,
  promocao_da_loja: Tag,
  validade: Clock,
};

const TOM_SELO: Record<Selo["tom"], string> = {
  economia: "bg-economia-suave text-economia",
  alerta: "bg-alerta-suave text-alerta",
  neutro: "bg-etiqueta-2 text-tinta-2",
};

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

export function ListaSelos({ selos, alertas = [] }: { selos: Selo[]; alertas?: Alerta[] }) {
  if (!selos.length && !alertas.length) return null;
  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Sobre o preço">
      {alertas.map((a) => (
        <li key={a} className={`selo ${TOM_SELO.alerta}`}>
          <CircleAlert className="size-3.5 shrink-0" aria-hidden />
          {ALERTAS[a]}
        </li>
      ))}
      {selos.map((s) => {
        const Icone = ICONE_SELO[s.tipo];
        return (
          <li key={`${s.tipo}-${s.texto}`} className={`selo ${TOM_SELO[s.tom]}`}>
            <Icone className="size-3.5 shrink-0" aria-hidden />
            {s.texto}
          </li>
        );
      })}
    </ul>
  );
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

function valorDoFrete(oferta: Oferta, estado: EstadoTotal): string {
  const f = oferta.frete;
  switch (estado) {
    case "confirmado":
      return f.valor ? reais(f.valor) : "grátis";
    case "estimado":
      return f.status === "gratis_anunciado" ? "grátis anunciado" : reais(f.valor ?? 0);
    case "nao_entrega":
      return "não entrega";
    case "indisponivel":
      return "sem estoque";
    case "calculando":
      return "calculando";
    default:
      return "não incluído";
  }
}

function CamposDaLinha({
  oferta,
  estado,
  cep,
}: {
  oferta: Oferta;
  estado: EstadoTotal;
  cep: string | null;
}) {
  const t = oferta.totais;
  const p = oferta.parcelamento;
  const custo = p ? custoDoParcelamento(oferta.preco, p) : null;
  return (
    <dl className="grid grid-cols-3 divide-x divide-tinta border-y border-tinta py-1.5 text-[0.875rem]">
      <div className="min-w-0 pr-2">
        <dt className="rotulo-campo truncate">{cep ? `Frete ${mascararCep(cep)}` : "Frete"}</dt>
        <dd className="mt-0.5 space-y-0.5">
          <CarimboTotal estado={estado} />
          <span className="numero block font-semibold">{valorDoFrete(oferta, estado)}</span>
        </dd>
      </div>
      <div className="min-w-0 px-2">
        <dt className="rotulo-campo">No Pix</dt>
        <dd className="numero mt-0.5 font-semibold">
          {t?.pix != null && t.pix < t.avista ? (
            reais(t.pix)
          ) : (
            <span className="font-normal text-tinta-2">sem desconto</span>
          )}
        </dd>
      </div>
      <div className="min-w-0 pl-2">
        <dt className="rotulo-campo">Parcelas</dt>
        <dd className="numero mt-0.5 font-semibold">
          {p && p.parcelas > 1 ? (
            <>
              {p.parcelas}x{" "}
              {custo && custo.mensal > 0 ? (
                <span className="text-alerta">{porcentagem(custo.mensal)} a.m.</span>
              ) : (
                <span className="font-normal text-tinta-2">sem juros</span>
              )}
            </>
          ) : (
            <span className="font-normal text-tinta-2">não informadas</span>
          )}
        </dd>
      </div>
    </dl>
  );
}

export function LinhaOferta({
  oferta,
  contexto,
  destaque = false,
}: {
  oferta: Oferta;
  contexto: Contexto;
  destaque?: boolean;
}) {
  const [aberta, setAberta] = useState(false);
  const [montada, setMontada] = useState(false);
  const idDetalhes = useId();
  const estado = estadoDoTotal(oferta, contexto.cep !== null);
  const total = totalPara(oferta, contexto.pagamento);
  const promocao = contexto.promocoes(oferta);
  const quando = oferta.consultado_em ? haQuanto(oferta.consultado_em, contexto.agora) : null;
  const entrega = prazo(oferta);
  const forma = pagamentoDoTotal(oferta, contexto.pagamento);
  const noCarrinho = oferta.origem === "marketplace" && oferta.link_carrinho;
  const apagada = estado === "nao_entrega" || estado === "indisponivel";

  return (
    <article
      aria-label={`${oferta.loja.nome}, ${reais(total)}`}
      className={`grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-2.5 px-4 py-3.5 [grid-template-areas:'loja_total'_'frete_frete'_'acoes_acoes'] sm:grid-cols-[minmax(7.5rem,10rem)_minmax(0,1fr)_auto] sm:gap-x-5 sm:[grid-template-areas:'loja_frete_total'_'loja_frete_acoes'] ${
        destaque ? "bg-acao-suave/60" : ""
      } ${apagada ? "text-tinta-2" : ""}`}
    >
      <div className="min-w-0 [grid-area:loja]">
        <p className="font-semibold">{oferta.loja.nome}</p>
        <p className="mt-0.5 text-[0.8125rem] leading-snug text-tinta-2">
          {oferta.origem === "marketplace" && oferta.vendedor && <>vendido por {oferta.vendedor}</>}
          {oferta.origem === "comparador" && "pelo Buscapé"}
          {oferta.origem === "importado" && "importado"}
        </p>
        {destaque && (
          <p className="mt-1 text-[0.8125rem] font-semibold text-acao">Menor total deste produto</p>
        )}
      </div>

      <div className="min-w-0 space-y-2 [grid-area:frete]">
        <CamposDaLinha oferta={oferta} estado={estado} cep={contexto.cep} />
        <p className="text-[0.8125rem] text-tinta-2">
          {estado === "confirmado" ? entrega : textoDoFrete(oferta, estado, contexto.cep)}
          {quando && (
            <span className="text-tinta-3">
              {estado === "confirmado" && !entrega ? "" : " · "}Preço consultado {quando}
            </span>
          )}
        </p>
        <ListaSelos
          selos={[...seloDoTipico(contexto.tipico(oferta)), ...promocao.selos]}
          alertas={oferta.alertas}
        />
      </div>

      <div className="text-right [grid-area:total]">
        <p className="text-[0.75rem] text-tinta-3">{rotuloDoTotal(estado, oferta)}</p>
        <p className="numero text-[1.3125rem] leading-tight font-bold whitespace-nowrap">
          {reais(total)}
        </p>
        {forma && estado !== "nao_entrega" && (
          <p className="text-[0.75rem] text-tinta-2">{forma}</p>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 [grid-area:acoes] sm:justify-end">
        <button
          type="button"
          onClick={() => {
            setMontada(true);
            setAberta(!aberta);
          }}
          aria-expanded={aberta}
          aria-controls={idDetalhes}
          className="inline-flex min-h-11 items-center gap-1 rounded-controle px-2 text-[0.875rem] font-medium text-tinta-2 hover:text-tinta sm:-mr-1"
        >
          {aberta ? "Esconder a conta" : "Ver a conta"}
          <ChevronDown
            className={`size-4 transition-transform ${aberta ? "rotate-180" : ""}`}
            aria-hidden
          />
        </button>
        <a
          href={linkDaOferta(oferta)}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="botao botao-secundario min-h-10 text-[0.875rem]"
        >
          {noCarrinho
            ? "Abrir no carrinho"
            : oferta.origem === "comparador"
              ? "Ver no Buscapé"
              : "Ver na loja"}
          <ArrowUpRight className="size-4" aria-hidden />
          <span className="sr-only">
            {` ${oferta.loja.nome}${oferta.vendedor ? `, vendido por ${oferta.vendedor}` : ""} (abre em nova aba)`}
          </span>
        </a>
      </div>

      <div
        id={idDetalhes}
        role="region"
        aria-label={`Conta de ${oferta.loja.nome}`}
        className="gaveta col-span-full"
        data-aberta={aberta}
      >
        <div className="min-h-0">
          {montada && <Detalhes oferta={oferta} contexto={contexto} promocao={promocao} />}
        </div>
      </div>
    </article>
  );
}

function Linha({ rotulo, valor, tom = "" }: { rotulo: string; valor: string; tom?: string }) {
  return (
    <div className="flex justify-between gap-4 py-1">
      <dt className="text-tinta-2">{rotulo}</dt>
      <dd className={`numero text-right ${tom}`}>{valor}</dd>
    </div>
  );
}

function Detalhes({
  oferta,
  contexto,
  promocao,
}: {
  oferta: Oferta;
  contexto: Contexto;
  promocao: Promocao;
}) {
  const t = oferta.totais;
  const frete = oferta.frete;
  const custo = oferta.parcelamento ? custoDoParcelamento(oferta.preco, oferta.parcelamento) : null;
  const serie = contexto.historico[oferta.id];
  const linhas: { rotulo: string; valor: string; tom?: string }[] = [
    { rotulo: "Produto", valor: reais(oferta.preco) },
  ];
  if (oferta.preco_pix !== null && oferta.preco_pix < oferta.preco)
    linhas.push({
      rotulo: "Desconto no Pix",
      valor: `menos ${reais(oferta.preco - oferta.preco_pix)}`,
      tom: "text-economia",
    });
  if (frete.status === "calculado" || frete.status === "estimado")
    linhas.push({
      rotulo: contexto.cep ? `Frete para ${mascararCep(contexto.cep)}` : "Frete",
      valor: frete.valor ? reais(frete.valor) : "grátis",
    });
  else linhas.push({ rotulo: "Frete", valor: "não incluído", tom: "text-tinta-3" });
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

  return (
    <div className="mt-2 grid gap-x-8 gap-y-5 border-t border-fio pt-4 md:grid-cols-2">
      <section aria-label="A conta" className="text-[0.875rem]">
        <h4 className="rotulo-campo">A conta</h4>
        <dl className="mt-1.5">
          {linhas.map((l) => (
            <Linha key={l.rotulo} {...l} />
          ))}
        </dl>
        {totais.length > 0 && (
          <dl className="mt-1.5 border-t border-dashed border-borda pt-1.5 font-semibold">
            {totais.map((l) => (
              <Linha key={l.rotulo} {...l} />
            ))}
          </dl>
        )}
        {custo && custo.juros > 0 && (
          <p className="mt-2 text-alerta">
            O parcelamento custa {reais(custo.juros)} a mais: {porcentagem(custo.mensal)} ao mês,{" "}
            {porcentagem(custo.anual)} ao ano.
          </p>
        )}
        {oferta.importacao && <Importado importacao={oferta.importacao} />}
        {frete.status === "calculado" && frete.opcoes.length > 1 && (
          <>
            <h4 className="rotulo-campo mt-4">
              Entrega
              {frete.cotado_em ? `, cotada às ${horaCotacao(frete.cotado_em)}` : ""}
            </h4>
            <ul className="mt-1.5">
              {frete.opcoes.map((o, i) => (
                <li key={`${o.nome}-${i}`} className="flex justify-between gap-4 py-1">
                  <span className="min-w-0 text-tinta-2">
                    {o.tipo === "retirada" ? "Retirada: " : ""}
                    {o.nome}
                    {o.entrega_ate
                      ? `, até ${dataEntrega(o.entrega_ate)}`
                      : o.prazo
                        ? `, ${o.prazo}`
                        : ""}
                  </span>
                  <span className="numero shrink-0">{o.valor ? reais(o.valor) : "grátis"}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section aria-label="Sobre o preço" className="min-w-0 text-[0.875rem]">
        {promocao.selos.length > 0 && (
          <>
            <h4 className="rotulo-campo">De onde vem cada selo</h4>
            <ul className="mt-1.5 space-y-1.5">
              {promocao.selos.map((s) => (
                <li key={`${s.tipo}-${s.texto}`}>
                  <span className="font-medium">{s.texto}</span>
                  <span className="text-tinta-2">: {s.evidencia}.</span>
                </li>
              ))}
            </ul>
          </>
        )}
        {serie?.some((p) => p.dia < contexto.hoje) ? (
          <div className={promocao.selos.length ? "mt-4" : ""}>
            <GraficoPreco pontos={serie} atual={oferta.preco} hoje={contexto.hoje} />
          </div>
        ) : (
          <p className={`text-tinta-2 ${promocao.selos.length ? "mt-4" : ""}`}>
            Ainda não há histórico de preço desta oferta. Ele se forma com as buscas feitas no
            Zpektral.
          </p>
        )}
      </section>
    </div>
  );
}

function dolares(centavos: number): string {
  return (centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "USD" });
}

function Importado({ importacao }: { importacao: Importacao }) {
  return (
    <div className="mt-3 border-t border-fio pt-2">
      <dl>
        <Linha rotulo="Produto em dólar" valor={dolares(importacao.produto_usd)} />
        <Linha rotulo="Dólar (PTAX)" valor={reais(Math.round(importacao.cotacao_dolar * 100))} />
        <Linha rotulo="Imposto de importação" valor={reais(importacao.imposto_importacao)} />
        <Linha rotulo="ICMS" valor={reais(importacao.icms)} />
      </dl>
      <p className="mt-2 text-tinta-2">
        Estimativa fora do Remessa Conforme. A Receita define o valor final na chegada.
      </p>
    </div>
  );
}
