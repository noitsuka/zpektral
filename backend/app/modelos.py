import re
from dataclasses import dataclass, field
from enum import StrEnum

_VOLTAGEM = re.compile(r"(?<![\d.,])(110|127|220)\s*(?:v|volts?)\b", re.I)
_BIVOLT = re.compile(r"\bbivolts?\b|(?<![\d.,])(?:110|127)\s*/\s*220\s*v", re.I)


_USADO = re.compile(
    r"(?<!ser )(?<!pode )(?<!sendo )(?<!foi )\b(?:usad[oa]s?|seminov[oa]s?|semi-nov[oa]s?)\b"
    r"(?!\s+(?:em|no|na|nos|nas|para|pra|com|como|por|pelo|pela|ao|à|de)\b)",
    re.I,
)
_RECONDICIONADO = re.compile(
    r"\b(?:recondicionad[oa]s?|recertificad[oa]s?|refurbished|reembalad[oa]s?|"
    r"(?:de\s+)?vitrine|mostru[aá]rio|open\s?box)\b",
    re.I,
)


class Condicao(StrEnum):
    NOVO = "novo"
    USADO = "usado"
    RECONDICIONADO = "recondicionado"


def condicao_do_titulo(titulo: str) -> "Condicao":
    if _USADO.search(titulo):
        return Condicao.USADO
    if _RECONDICIONADO.search(titulo):
        return Condicao.RECONDICIONADO
    return Condicao.NOVO


def voltagem_do_titulo(titulo: str) -> str | None:
    if _BIVOLT.search(titulo):
        return "bivolt"
    achados = {"127" if v == "110" else v for v in _VOLTAGEM.findall(titulo)}
    if len(achados) > 1:
        return "bivolt"
    if achados:
        return "110V" if achados == {"127"} else f"{achados.pop()}V"
    return None


class StatusFrete(StrEnum):
    CALCULADO = "calculado"
    GRATIS_ANUNCIADO = "gratis_anunciado"
    NAO_ENTREGA = "nao_entrega"
    CALCULANDO = "calculando"
    SEM_CEP = "sem_cep"
    NAO_INFORMADO = "nao_informado"
    ESTIMADO = "estimado"


class Origem(StrEnum):
    LOJA = "loja"
    MARKETPLACE = "marketplace"
    COMPARADOR = "comparador"
    IMPORTADO = "importado"


@dataclass(slots=True)
class Loja:
    id: str
    nome: str


@dataclass(slots=True)
class OpcaoFrete:
    nome: str
    valor: int
    prazo: str | None
    prazo_dias: float | None
    tipo: str
    transportadora: str | None = None
    entrega_ate: str | None = None
    distancia_km: float | None = None


@dataclass(slots=True)
class Frete:
    status: StatusFrete
    valor: int | None = None
    prazo: str | None = None
    prazo_dias: float | None = None
    opcoes: list[OpcaoFrete] = field(default_factory=list)
    modalidade: str | None = None
    transportadora: str | None = None
    entrega_ate: str | None = None
    cotado_em: str | None = None

    @classmethod
    def desconhecido(cls) -> "Frete":
        return cls(StatusFrete.NAO_INFORMADO)


@dataclass(slots=True)
class Parcelamento:
    parcelas: int
    valor: int
    total: int
    juros: bool


class Pagamento(StrEnum):
    MELHOR = "melhor"
    PIX = "pix"
    AVISTA = "avista"
    PARCELADO = "parcelado"


class Alerta(StrEnum):
    PRAZO_LONGO = "prazo_longo"
    FRETE_MAIOR_QUE_PRODUTO = "frete_maior_que_produto"
    PRECO_MUDOU_NO_CHECKOUT = "preco_mudou_no_checkout"
    PRECO_FORA_DA_CURVA = "preco_fora_da_curva"
    PRECO_INSTAVEL = "preco_instavel"


DIAS_PRAZO_LONGO = 60


@dataclass(frozen=True, slots=True)
class Importacao:
    produto_usd: int
    frete_usd: int | None
    cotacao_dolar: float
    imposto_importacao: int
    icms: int

    @property
    def impostos(self) -> int:
        return self.imposto_importacao + self.icms


@dataclass(slots=True)
class Totais:
    pix: int | None
    avista: int
    parcelado: int | None


@dataclass(slots=True)
class Oferta:
    id: str
    titulo: str
    link: str
    loja: Loja
    preco: int
    origem: Origem = Origem.LOJA
    vendedor: str | None = None
    imagem: str | None = None
    marca: str | None = None
    ean: str | None = None
    voltagem: str | None = None
    condicao: Condicao | None = None
    preco_original: int | None = None
    preco_pix: int | None = None
    parcelamento: Parcelamento | None = None
    frete: Frete = field(default_factory=Frete.desconhecido)
    disponivel: bool = True
    relevancia: int = 0
    posicao: int = 0
    melhor_preco: int = 0
    total: int = 0
    total_exato: bool = False
    totais: Totais | None = None
    alertas: list[Alerta] = field(default_factory=list)
    grupo: str | None = None
    link_carrinho: str | None = None
    importacao: Importacao | None = None

    def consolidar(self) -> "Oferta":
        if self.preco_pix is not None and not 0 < self.preco_pix <= self.preco:
            self.preco_pix = None
        melhor = min(self.preco, self.preco_pix or self.preco)
        frete = (self.frete.valor or 0) + (self.importacao.impostos if self.importacao else 0)
        self.melhor_preco = melhor
        self.total = melhor + frete
        self.total_exato = (
            self.frete.status is StatusFrete.CALCULADO and Alerta.PRECO_INSTAVEL not in self.alertas
        )
        self.totais = Totais(
            pix=self.preco_pix + frete if self.preco_pix else None,
            avista=self.preco + frete,
            parcelado=self.parcelamento.total + frete if self.parcelamento else None,
        )
        if self.preco_original is not None and self.preco_original <= self.preco:
            self.preco_original = None
        if self.voltagem is None:
            self.voltagem = voltagem_do_titulo(self.titulo)
        if self.condicao is None:
            self.condicao = condicao_do_titulo(self.titulo)

        dias = self.frete.prazo_dias
        if dias is not None and dias > DIAS_PRAZO_LONGO:
            self.alertar(Alerta.PRAZO_LONGO)
        if self.total_exato and frete > melhor:
            self.alertar(Alerta.FRETE_MAIOR_QUE_PRODUTO)
        return self

    def alertar(self, alerta: Alerta) -> None:
        if alerta not in self.alertas:
            self.alertas.append(alerta)

    def total_para(self, pagamento: Pagamento) -> int:
        t = self.totais
        if t is None or pagamento is Pagamento.MELHOR:
            return self.total
        if pagamento is Pagamento.PIX:
            return t.pix if t.pix is not None else t.avista
        if pagamento is Pagamento.PARCELADO:
            return t.parcelado if t.parcelado is not None else t.avista
        return t.avista

    @property
    def desconto(self) -> float:
        if not self.preco_original:
            return 0.0
        return 1 - self.melhor_preco / self.preco_original


class StatusFonte(StrEnum):
    OK = "ok"
    ERRO = "erro"
    TEMPO_ESGOTADO = "tempo_esgotado"
    DESATIVADA = "desativada"


@dataclass(slots=True)
class RelatorioFonte:
    id: str
    nome: str
    status: StatusFonte
    tempo_ms: int = 0
    ofertas: int = 0
    mensagem: str | None = None


@dataclass(slots=True)
class Endereco:
    cep: str
    logradouro: str | None
    bairro: str | None
    cidade: str | None
    uf: str | None
