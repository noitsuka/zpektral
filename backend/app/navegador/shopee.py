import logging
import re
from collections.abc import Callable, MutableMapping, Sequence
from dataclasses import dataclass
from datetime import date

from app.configuracao import Configuracoes
from app.dinheiro import ler_reais
from app.navegador.base import (
    BLOQUEIOS,
    CotacaoNavegador,
    Intervalo,
    Navegador,
    Pagina,
    Seletor,
    StatusCotacao,
    css,
    digitos,
    ler_data_de_entrega,
    papel,
    placeholder,
    prazo_ate,
    rotulo,
    sem_acentos,
    texto,
)

log = logging.getLogger("zpektral.navegador.shopee")

SITE = "https://shopee.com.br"


@dataclass(frozen=True)
class SeletoresShopee:
    abrir_local: tuple[Seletor, ...]
    campo_cep: tuple[Seletor, ...]
    confirmar: tuple[Seletor, ...]


SELETORES = SeletoresShopee(
    abrir_local=(
        css("[aria-label*='CEP' i]"),
        papel("button", r"(enviar para|envio para|alterar (cep|endere)|calcular frete)"),
        texto(r"^\s*(enviar para|envio para|calcular frete)"),
    ),
    campo_cep=(
        placeholder(r"\bcep\b"),
        rotulo(r"\bcep\b"),
        papel("textbox", r"\bcep\b"),
        css("input[name*='zip' i], input[name*='cep' i]"),
    ),
    confirmar=(
        papel("button", r"^\s*(confirmar|calcular|aplicar|ok)\s*$"),
        texto(r"^\s*(confirmar|calcular)\s*$"),
    ),
)

_DESAFIO_URL = ("/verify/", "captcha")
_LOGIN_URL = ("/buyer/login", "/buyer/signup")
_REAIS = r"R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}"
_CUSTO = re.compile(r"(?:custo de envio|frete|envio)\s*:?\s*(" + _REAIS + ")", re.I)
_GRATIS_CONDICIONAL = re.compile(
    r"frete gratis\s*(?:em|para|nas|nos)?\s*(?:pedidos|compras)?\s*"
    r"(?:acima|a partir|minim|com cupom)"
)
_PRAZO = re.compile(
    r"(?:receba|chega|chegara|entrega prevista|entrega)\s*(?:ate|entre|em|dia|:)\s*([^\n]{3,60})"
)


def url_do_produto(id_loja: int | str, id_item: int | str) -> str:
    return f"{SITE}/product/{id_loja}/{id_item}"


def detectar_bloqueio(conteudo: str, url: str) -> CotacaoNavegador | None:
    endereco = url.lower()
    if any(m in endereco for m in _LOGIN_URL):
        return CotacaoNavegador(StatusCotacao.LOGIN, detalhe="a shopee pediu login")
    normal = sem_acentos(conteudo).lower()
    if any(m in endereco for m in _DESAFIO_URL) or "captcha" in normal:
        return CotacaoNavegador(StatusCotacao.DESAFIO, detalhe="verificação de tráfego da shopee")
    if re.search(r"(entre|faca login) (na sua conta |)para (continuar|ver)", normal):
        return CotacaoNavegador(StatusCotacao.LOGIN, detalhe="a shopee pediu login")
    return None


def cep_aplicado(conteudo: str, cep: str) -> bool:
    alvo = digitos(cep)
    return alvo in digitos(conteudo.replace("\n", " "))


def ler_frete(conteudo: str, hoje: date) -> CotacaoNavegador:
    normal = sem_acentos(conteudo).lower()
    if re.search(r"\besgotado\b|produto indisponivel|nao esta mais disponivel", normal):
        return CotacaoNavegador(StatusCotacao.INDISPONIVEL, detalhe="produto sem estoque")
    if re.search(r"cep (invalido|nao encontrado|incorreto)", normal):
        return CotacaoNavegador(StatusCotacao.CEP_REJEITADO, detalhe="CEP recusado pela página")
    if re.search(
        r"nao (entrega|envia|e possivel enviar|disponivel para (o seu|este) (cep|endereco))", normal
    ):
        return CotacaoNavegador(StatusCotacao.NAO_ENTREGA, detalhe="sem entrega para o CEP")

    prazo_bruto = _PRAZO.search(normal)
    prazo, dias, ate = prazo_ate(
        ler_data_de_entrega(prazo_bruto.group(1) if prazo_bruto else None, hoje), hoje
    )
    if custo := _CUSTO.search(conteudo):
        valor = ler_reais(custo.group(1))
    elif "frete gratis" in normal and not _GRATIS_CONDICIONAL.search(normal):
        valor = 0
    else:
        return CotacaoNavegador(
            StatusCotacao.SEM_INFORMACAO,
            prazo=prazo,
            prazo_dias=dias,
            entrega_ate=ate,
            detalhe="valor do frete não aparece na página",
        )
    return CotacaoNavegador(
        StatusCotacao.COTADO,
        valor=valor,
        gratis=valor == 0,
        prazo=prazo,
        prazo_dias=dias,
        entrega_ate=ate,
        modalidade="Entrega",
    )


class FreteShopeeNavegador:
    def __init__(
        self,
        navegador: Navegador,
        config: Configuracoes,
        seletores: SeletoresShopee = SELETORES,
        hoje: Callable[[], date] = date.today,
        intervalo: Intervalo | None = None,
    ):
        self._navegador = navegador
        self._tempo_ms = config.navegador_tempo_limite_ms
        self._s = seletores
        self._hoje = hoje
        self._intervalo = intervalo or Intervalo(max(1.0, config.navegador_intervalo_segundos))

    async def cotar(
        self,
        produtos: Sequence[tuple[str, int | str, int | str]],
        cep: str,
        destino: MutableMapping[str, CotacaoNavegador],
    ) -> None:
        async with self._navegador.pagina() as pagina:
            for posicao, (chave, id_loja, id_item) in enumerate(produtos):
                resultado = await self._cotar_um(pagina, url_do_produto(id_loja, id_item), cep)
                destino[chave] = resultado
                if resultado.status in BLOQUEIOS or resultado.status in (
                    StatusCotacao.CEP_REJEITADO,
                    StatusCotacao.SEM_SELETOR,
                ):
                    if resultado.status in BLOQUEIOS:
                        log.warning("shopee: %s; cotação encerrada", resultado.detalhe)
                    for restante, _, _ in produtos[posicao + 1 :]:
                        destino[restante] = CotacaoNavegador(
                            StatusCotacao.INTERROMPIDO, detalhe=resultado.status.value
                        )
                    return

    async def _cotar_um(self, pagina: Pagina, url: str, cep: str) -> CotacaoNavegador:
        await self._intervalo.aguardar()
        await pagina.abrir(url)
        conteudo = await pagina.texto()
        if bloqueio := detectar_bloqueio(conteudo, await pagina.url()):
            return bloqueio
        if not cep_aplicado(conteudo, cep):
            if falha := await self._aplicar_cep(pagina, cep):
                return falha
            conteudo = await pagina.texto()
        if bloqueio := detectar_bloqueio(conteudo, await pagina.url()):
            return bloqueio
        return ler_frete(conteudo, self._hoje())

    async def _aplicar_cep(self, pagina: Pagina, cep: str) -> CotacaoNavegador | None:
        s = self._s
        cep = digitos(cep)
        if not await pagina.clicar(s.abrir_local):
            return CotacaoNavegador(StatusCotacao.SEM_SELETOR, detalhe="seletor de CEP")
        if not await pagina.preencher(s.campo_cep, f"{cep[:5]}-{cep[5:]}"):
            return CotacaoNavegador(StatusCotacao.SEM_SELETOR, detalhe="campo de CEP")
        if not await pagina.clicar(s.confirmar):
            return CotacaoNavegador(StatusCotacao.SEM_SELETOR, detalhe="botão de confirmar")
        await pagina.aguardar(
            lambda h: (
                cep_aplicado(h, cep)
                or bool(re.search(r"cep (inv|n.o encontrado)", h, re.I))
                or bool(detectar_bloqueio(h, ""))
            ),
            self._tempo_ms,
        )
        return None
