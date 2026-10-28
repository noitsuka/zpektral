import type {
  Condicao,
  Facetas,
  Filtros,
  Oferta,
  Ordem,
  Pagamento,
  FiltroFrete,
} from "@/nucleo/tipos";

export const FILTROS_PADRAO: Filtros = {
  ordem: "relevancia",
  pagamento: "melhor",
  relevancia_min: 70,
  condicao: ["novo"],
  preco_min: null,
  preco_max: null,
  lojas: [],
  voltagem: [],
  voltagem_estrita: false,
  frete: "todos",
};

export const ORDENS: { valor: Ordem; rotulo: string }[] = [
  { valor: "relevancia", rotulo: "Relevância" },
  { valor: "menor_total", rotulo: "Menor total" },
  { valor: "custo_beneficio", rotulo: "Custo-benefício" },
  { valor: "entrega_rapida", rotulo: "Entrega mais rápida" },
  { valor: "maior_desconto", rotulo: "Maior desconto" },
  { valor: "menor_preco", rotulo: "Menor preço do produto" },
  { valor: "maior_preco", rotulo: "Maior preço do produto" },
];

export const PAGAMENTOS: { valor: Pagamento; rotulo: string; dica: string }[] = [
  { valor: "melhor", rotulo: "Melhor forma", dica: "o menor entre Pix e cartão" },
  { valor: "pix", rotulo: "Pix", dica: "com o desconto do Pix" },
  { valor: "avista", rotulo: "Cartão à vista", dica: "uma parcela" },
  { valor: "parcelado", rotulo: "Parcelado", dica: "no maior parcelamento da loja" },
];

export const FRETES: { valor: FiltroFrete; rotulo: string }[] = [
  { valor: "todos", rotulo: "Todos" },
  { valor: "calculado", rotulo: "Só total exato" },
  { valor: "gratis", rotulo: "Frete grátis" },
];

export const CONDICOES: { valor: Condicao; rotulo: string }[] = [
  { valor: "novo", rotulo: "Novo" },
  { valor: "recondicionado", rotulo: "Recondicionado" },
  { valor: "usado", rotulo: "Usado" },
];

const VOLTAGENS = ["110V", "220V", "bivolt"] as const;

const VALORES_ORDEM = new Set(ORDENS.map((o) => o.valor));
const VALORES_PAGAMENTO = new Set(PAGAMENTOS.map((p) => p.valor));
const VALORES_FRETE = new Set(FRETES.map((s) => s.valor));
const VALORES_CONDICAO = new Set(CONDICOES.map((c) => c.valor));

function lista(bruto: string | null): string[] {
  return bruto ? bruto.split(",").filter(Boolean) : [];
}

function centavos(bruto: string | null): number | null {
  if (!bruto) return null;
  const n = Number(bruto);
  return Number.isInteger(n) && n >= 0 ? n : null;
}

export function filtrosDosParametros(params: URLSearchParams): Filtros {
  const ordem = params.get("ordem") as Ordem;
  const pagamento = params.get("pagamento") as Pagamento;
  const frete = params.get("frete") as FiltroFrete;
  const condicao = lista(params.get("condicao")).filter((c): c is Condicao =>
    VALORES_CONDICAO.has(c as Condicao),
  );
  return {
    ordem: VALORES_ORDEM.has(ordem) ? ordem : FILTROS_PADRAO.ordem,
    pagamento: VALORES_PAGAMENTO.has(pagamento) ? pagamento : FILTROS_PADRAO.pagamento,
    relevancia_min: FILTROS_PADRAO.relevancia_min,
    condicao: condicao.length ? condicao : FILTROS_PADRAO.condicao,
    preco_min: centavos(params.get("preco_min")),
    preco_max: centavos(params.get("preco_max")),
    lojas: lista(params.get("lojas")),
    voltagem: lista(params.get("voltagem")).filter((v) =>
      (VOLTAGENS as readonly string[]).includes(v),
    ),
    voltagem_estrita: params.get("voltagem_estrita") === "true",
    frete: VALORES_FRETE.has(frete) ? frete : FILTROS_PADRAO.frete,
  };
}

export function filtrosParaParametros(
  filtros: Filtros,
  destino = new URLSearchParams(),
): URLSearchParams {
  const definir = (chave: string, valor: string | null, padrao: string | null) => {
    if (valor === null || valor === padrao || valor === "") destino.delete(chave);
    else destino.set(chave, valor);
  };
  const d = FILTROS_PADRAO;
  definir("ordem", filtros.ordem, d.ordem);
  definir("pagamento", filtros.pagamento, d.pagamento);
  destino.delete("relevancia_min");
  definir("condicao", filtros.condicao.join(","), d.condicao.join(","));
  definir("preco_min", filtros.preco_min === null ? null : String(filtros.preco_min), null);
  definir("preco_max", filtros.preco_max === null ? null : String(filtros.preco_max), null);
  definir("lojas", filtros.lojas.join(","), "");
  definir("voltagem", filtros.voltagem.join(","), "");
  definir("voltagem_estrita", filtros.voltagem_estrita ? "true" : null, null);
  definir("frete", filtros.frete, d.frete);
  return destino;
}

export function contarFiltrosAtivos(f: Filtros): number {
  return (
    (f.preco_min !== null ? 1 : 0) +
    (f.preco_max !== null ? 1 : 0) +
    (f.frete !== FILTROS_PADRAO.frete ? 1 : 0) +
    f.lojas.length +
    f.voltagem.length +
    (f.condicao.join() !== FILTROS_PADRAO.condicao.join() ? 1 : 0)
  );
}

export function voltagemFazSentido(facetas: Facetas | null): boolean {
  if (!facetas) return false;
  const total = facetas.lojas.reduce((soma, l) => soma + l.quantidade, 0);
  const comVoltagem = Object.values(facetas.voltagens).reduce((soma, n) => soma + n, 0);
  return comVoltagem >= 3 && comVoltagem >= total * 0.25;
}

function contar(valores: Iterable<string>): Record<string, number> {
  const saida: Record<string, number> = {};
  for (const v of valores) saida[v] = (saida[v] ?? 0) + 1;
  return Object.fromEntries(Object.entries(saida).sort((a, b) => b[1] - a[1]));
}

export function facetasDe(ofertas: Oferta[], f: Filtros): Facetas | null {
  const todas = ofertas.filter(
    (o) => o.relevancia >= f.relevancia_min && o.disponivel && o.frete.status !== "nao_entrega",
  );
  if (!todas.length) return null;
  const condicoes = contar(todas.flatMap((o) => (o.condicao ? [o.condicao] : [])));
  const conjunto = todas.filter(
    (o) => !f.condicao.length || (o.condicao !== null && f.condicao.includes(o.condicao)),
  );
  if (!conjunto.length) {
    return {
      lojas: [],
      voltagens: {},
      condicoes,
      preco_min: null,
      preco_max: null,
      com_total_exato: 0,
      frete_gratis: 0,
      origens: {},
    };
  }
  const nomes = new Map(conjunto.map((o) => [o.loja.id, o.loja.nome]));
  const lojas = Object.entries(contar(conjunto.map((o) => o.loja.id))).map(([id, quantidade]) => ({
    id,
    nome: nomes.get(id) ?? id,
    quantidade,
  }));
  const totais = conjunto.map((o) => totalPara(o, f.pagamento));
  return {
    lojas,
    voltagens: contar(conjunto.flatMap((o) => (o.voltagem ? [o.voltagem] : []))),
    condicoes,
    preco_min: Math.min(...totais),
    preco_max: Math.max(...totais),
    com_total_exato: conjunto.filter((o) => o.total_exato).length,
    frete_gratis: conjunto.filter(
      (o) =>
        o.frete.valor === 0 &&
        (o.frete.status === "calculado" || o.frete.status === "gratis_anunciado"),
    ).length,
    origens: contar(conjunto.map((o) => o.origem)),
  };
}

export function ocultasPorCondicao(facetas: Facetas | null, f: Filtros): number {
  if (!facetas) return 0;
  return Object.entries(facetas.condicoes)
    .filter(([condicao]) => !f.condicao.includes(condicao as Condicao))
    .reduce((soma, [, n]) => soma + n, 0);
}

export function linkDaOferta(oferta: Oferta): string {
  return (oferta.origem === "marketplace" && oferta.link_carrinho) || oferta.link;
}

export function totalPara(oferta: Oferta, pagamento: Pagamento): number {
  const t = oferta.totais;
  if (!t || pagamento === "melhor") return oferta.total;
  if (pagamento === "pix") return t.pix ?? t.avista;
  if (pagamento === "parcelado") return t.parcelado ?? t.avista;
  return t.avista;
}
