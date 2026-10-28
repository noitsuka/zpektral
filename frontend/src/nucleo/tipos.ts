type StatusFrete =
  | "calculado"
  | "gratis_anunciado"
  | "nao_entrega"
  | "sem_cep"
  | "nao_informado"
  | "calculando"
  | "estimado";

type Origem = "loja" | "marketplace" | "comparador" | "importado";

export type Importacao = {
  produto_usd: number;
  frete_usd: number | null;
  cotacao_dolar: number;
  imposto_importacao: number;
  icms: number;
};
export type Condicao = "novo" | "usado" | "recondicionado";
export type Pagamento = "melhor" | "pix" | "avista" | "parcelado";
export type Ordem =
  | "relevancia"
  | "menor_total"
  | "custo_beneficio"
  | "menor_preco"
  | "maior_preco"
  | "entrega_rapida"
  | "maior_desconto";
export type FiltroFrete = "todos" | "gratis" | "calculado";
export type Alerta =
  | "prazo_longo"
  | "frete_maior_que_produto"
  | "preco_mudou_no_checkout"
  | "preco_fora_da_curva"
  | "preco_instavel";

type Loja = { id: string; nome: string };

type OpcaoFrete = {
  nome: string;
  valor: number;
  prazo: string | null;
  prazo_dias: number | null;
  tipo: "entrega" | "retirada";
  transportadora: string | null;
  entrega_ate: string | null;
  distancia_km: number | null;
};

export type Frete = {
  status: StatusFrete;
  valor: number | null;
  prazo: string | null;
  prazo_dias: number | null;
  opcoes: OpcaoFrete[];
  modalidade: string | null;
  transportadora: string | null;
  entrega_ate: string | null;
  cotado_em: string | null;
};

export type PontoHistorico = { dia: string; preco: number };
export type HistoricoOfertas = Record<string, PontoHistorico[]>;
export type Parcelamento = { parcelas: number; valor: number; total: number; juros: boolean };
type Totais = { pix: number | null; avista: number; parcelado: number | null };

export type Oferta = {
  id: string;
  titulo: string;
  link: string;
  loja: Loja;
  preco: number;
  origem: Origem;
  vendedor: string | null;
  imagem: string | null;
  marca: string | null;
  ean: string | null;
  voltagem: string | null;
  condicao: Condicao | null;
  preco_original: number | null;
  preco_pix: number | null;
  parcelamento: Parcelamento | null;
  frete: Frete;
  disponivel: boolean;
  relevancia: number;
  posicao: number;
  melhor_preco: number;
  total: number;
  total_exato: boolean;
  totais: Totais | null;
  alertas: Alerta[];
  grupo: string | null;
  link_carrinho: string | null;
  importacao: Importacao | null;
};

type StatusFonte = "ok" | "erro" | "tempo_esgotado" | "desativada";

export type RelatorioFonte = {
  id: string;
  nome: string;
  status: StatusFonte;
  tempo_ms: number;
  ofertas: number;
  mensagem: string | null;
};

type SaudeFonte = {
  estado: "saudavel" | "degradada" | "desativada" | "sem_dados";
  taxa_sucesso: number | null;
  tempo_medio_ms: number | null;
};

export type InfoFonte = { id: string; nome: string; ativa: boolean; saude: SaudeFonte | null };

type Endereco = {
  cep: string;
  logradouro: string | null;
  bairro: string | null;
  cidade: string | null;
  uf: string | null;
};

export type Facetas = {
  lojas: { id: string; nome: string; quantidade: number }[];
  voltagens: Record<string, number>;
  condicoes: Record<string, number>;
  preco_min: number | null;
  preco_max: number | null;
  com_total_exato: number;
  frete_gratis: number;
  origens: Record<string, number>;
};

export type PaginaResultados = {
  consulta: string;
  endereco: Endereco | null;
  pronto: boolean;
  pendentes: string[];
  total: number;
  pagina: number;
  por_pagina: number;
  paginas: number;
  ofertas: Oferta[];
  facetas: Facetas;
  fontes: RelatorioFonte[];
  tempo_ms: number;
  cache: boolean;
};

export type Filtros = {
  ordem: Ordem;
  pagamento: Pagamento;
  relevancia_min: number;
  condicao: Condicao[];
  preco_min: number | null;
  preco_max: number | null;
  lojas: string[];
  voltagem: string[];
  voltagem_estrita: boolean;
  frete: FiltroFrete;
};

export type EventoInicio = {
  consulta: string;
  endereco: Endereco | null;
  fontes: InfoFonte[];
  pagamento: Pagamento;
  ordem: Ordem;
};
export type EventoLote = {
  fonte: RelatorioFonte;
  fase: "catalogo" | "final";
  ofertas: Oferta[];
  melhor_total: number | null;
};
export type EventoFalhaFonte = { fonte: RelatorioFonte };
export type EventoFim = {
  tempo_ms: number;
  total: number;
  grupos_por_oferta: Record<string, string>;
  facetas: Facetas;
  fontes: RelatorioFonte[];
};
