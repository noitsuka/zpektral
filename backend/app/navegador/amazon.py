import html as html_lib
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

log = logging.getLogger("zpektral.navegador.amazon")

SITE = "https://www.amazon.com.br"
ESPERA_AVISO_MS = 1500


@dataclass(frozen=True)
class SeletoresAmazon:
    abrir_local: tuple[Seletor, ...]
    cep_parte_1: tuple[Seletor, ...]
    cep_parte_2: tuple[Seletor, ...]
    cep_inteiro: tuple[Seletor, ...]
    confirmar: tuple[Seletor, ...]
    fechar_aviso: tuple[Seletor, ...]


SELETORES = SeletoresAmazon(
    abrir_local=(
        css("#contextualIngressPtLink"),
        css("#nav-global-location-popover-link"),
        rotulo(r"atualizar (local|cep)"),
        papel("button", r"(atualizar|alterar|selecione).{0,20}(local|cep|endere)"),
        texto(r"^\s*atualizar cep\s*$"),
    ),
    cep_parte_1=(css("#GLUXZipUpdateInput_0"),),
    cep_parte_2=(css("#GLUXZipUpdateInput_1"),),
    cep_inteiro=(
        css("#GLUXZipUpdateInput"),
        placeholder(r"cep"),
        rotulo(r"\bcep\b"),
        papel("textbox", r"\bcep\b"),
    ),
    confirmar=(
        css("#GLUXZipUpdate input[type='submit']"),
        css("#GLUXZipUpdate"),
        papel("button", r"^\s*(confirmar|aplicar)\s*$"),
        texto(r"^\s*confirmar\s*$"),
    ),
    fechar_aviso=(
        css("#GLUXConfirmClose"),
        papel("button", r"^\s*(continuar|conclu[ií]do|fechar)\s*$"),
    ),
)

_VERIFICACAO = ("/errors/validatecaptcha", "api-services-support@amazon.com", "captchacharacters")
_LOGIN = ("/ap/signin", "/ap/cvf/")
_ID_TEXTO = r'id="{}"[^>]*>(.*?)</'
_LINHAS_DE_LOCAL = ("contextualIngressPtLabel_deliveryShortLine", "glow-ingress-line1")
_ROTULO_LOCAL = re.compile(r'id="contextualIngressPtLink"[^>]*aria-label="([^"]*)"')
_ENTREGA_PRINCIPAL = re.compile(
    r'<span\b(?=[^>]*data-csa-c-mir-type="DELIVERY")(?=[^>]*data-csa-c-delivery-price)[^>]*>'
)
_ATRIBUTO = re.compile(r'(data-csa-c-[a-z-]+)="([^"]*)"')
_DISPONIBILIDADE = re.compile(r'id="availability"[^>]*>(.*?)</div>', re.S)
_ERRO_CEP = re.compile(r'id="GLUXZipError"(?![^>]*a-hidden)[^>]*>(.*?)</div>', re.S)
_BLOCO_ENTREGA = re.compile(r'id="deliveryBlockMessage"[^>]*>(.*?)id="contextualIngressPt', re.S)
_TAGS = re.compile(r"<[^>]+>")
_REAIS = re.compile(r"R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}")


def url_do_produto(asin: str) -> str:
    return f"{SITE}/dp/{asin}"


def _limpo(trecho: str) -> str:
    return " ".join(html_lib.unescape(_TAGS.sub(" ", trecho)).split())


def detectar_bloqueio(html: str, url: str) -> CotacaoNavegador | None:
    pagina = html.lower()
    if any(m in url.lower() for m in _LOGIN):
        return CotacaoNavegador(StatusCotacao.LOGIN, detalhe="a amazon pediu login")
    if any(m in pagina for m in _VERIFICACAO):
        return CotacaoNavegador(StatusCotacao.DESAFIO, detalhe="verificação de robô na página")
    return None


def local_atual(html: str) -> str:
    partes = [
        _limpo(achado.group(1))
        for ident in _LINHAS_DE_LOCAL
        if (achado := re.search(_ID_TEXTO.format(ident), html, re.S))
    ]
    if rotulo_local := _ROTULO_LOCAL.search(html):
        partes.append(html_lib.unescape(rotulo_local.group(1)))
    return " ".join(partes)


def cep_aplicado(html: str, cep: str) -> bool:
    return digitos(cep) in digitos(local_atual(html))


def cep_rejeitado(html: str) -> bool:
    erro = _ERRO_CEP.search(html)
    return bool(erro and _limpo(erro.group(1)))


def ler_entrega(html: str, hoje: date) -> CotacaoNavegador:
    disponibilidade = _DISPONIBILIDADE.search(html)
    situacao = sem_acentos(_limpo(disponibilidade.group(1))).lower() if disponibilidade else ""
    if "indisponivel" in situacao or "nao disponivel" in situacao:
        return CotacaoNavegador(StatusCotacao.INDISPONIVEL, detalhe=situacao)

    bloco = _BLOCO_ENTREGA.search(html)
    texto_bloco = sem_acentos(_limpo(bloco.group(1))).lower() if bloco else ""
    if re.search(r"nao (pode ser enviado|e possivel entregar|entrega)", texto_bloco):
        return CotacaoNavegador(StatusCotacao.NAO_ENTREGA, detalhe=texto_bloco[:160])

    principal = _ENTREGA_PRINCIPAL.search(html)
    if principal is None:
        return CotacaoNavegador(StatusCotacao.SEM_INFORMACAO, detalhe="bloco de entrega ausente")
    atributos = {k: html_lib.unescape(v).strip() for k, v in _ATRIBUTO.findall(principal.group(0))}
    preco = atributos.get("data-csa-c-delivery-price", "")
    condicao = atributos.get("data-csa-c-delivery-condition", "")
    subtipo = atributos.get("data-csa-c-mir-sub-type", "").upper()
    quando = atributos.get("data-csa-c-delivery-time")
    prazo, dias, ate = prazo_ate(ler_data_de_entrega(quando, hoje), hoje)

    if "GRATIS" in sem_acentos(preco).upper():
        if condicao or subtipo == "CONDITIONALLY_FREE":
            return CotacaoNavegador(
                StatusCotacao.SEM_INFORMACAO,
                prazo=prazo,
                prazo_dias=dias,
                entrega_ate=ate,
                detalhe=f"grátis só com condição: {condicao or subtipo.lower()}",
            )
        valor = 0
    elif achado := _REAIS.search(preco) or _REAIS.search(texto_bloco):
        valor = ler_reais(achado.group(0))
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
        modalidade=atributos.get("data-csa-c-delivery-type") or "Entrega",
    )


class FreteAmazonNavegador:
    def __init__(
        self,
        navegador: Navegador,
        config: Configuracoes,
        seletores: SeletoresAmazon = SELETORES,
        hoje: Callable[[], date] = date.today,
        intervalo: Intervalo | None = None,
    ):
        self._navegador = navegador
        self._tempo_ms = config.navegador_tempo_limite_ms
        self._s = seletores
        self._hoje = hoje
        self._intervalo = intervalo or Intervalo(config.navegador_intervalo_segundos)

    async def cotar(
        self, asins: Sequence[str], cep: str, destino: MutableMapping[str, CotacaoNavegador]
    ) -> None:
        async with self._navegador.pagina() as pagina:
            for posicao, asin in enumerate(asins):
                resultado = await self._cotar_um(pagina, asin, cep)
                destino[asin] = resultado
                if resultado.status in BLOQUEIOS:
                    log.warning("amazon: %s; cotação encerrada", resultado.detalhe)
                    for restante in asins[posicao + 1 :]:
                        destino[restante] = CotacaoNavegador(
                            StatusCotacao.INTERROMPIDO, detalhe=resultado.status.value
                        )
                    return
                if resultado.status in (
                    StatusCotacao.CEP_REJEITADO,
                    StatusCotacao.CEP_NAO_APLICADO,
                    StatusCotacao.SEM_SELETOR,
                ):
                    for restante in asins[posicao + 1 :]:
                        destino[restante] = resultado
                    return

    async def _abrir(self, pagina: Pagina, url: str) -> tuple[str, CotacaoNavegador | None]:
        await self._intervalo.aguardar()
        await pagina.abrir(url)
        html = await pagina.html()
        return html, detectar_bloqueio(html, await pagina.url())

    async def _cotar_um(self, pagina: Pagina, asin: str, cep: str) -> CotacaoNavegador:
        url = url_do_produto(asin)
        html, bloqueio = await self._abrir(pagina, url)
        if bloqueio:
            return bloqueio
        if not cep_aplicado(html, cep):
            falha = await self._aplicar_cep(pagina, cep)
            if falha:
                return falha
            html = await pagina.html()
            if not cep_aplicado(html, cep):
                html, bloqueio = await self._abrir(pagina, url)
                if bloqueio:
                    return bloqueio
                if not cep_aplicado(html, cep):
                    return CotacaoNavegador(
                        StatusCotacao.CEP_NAO_APLICADO, detalhe=local_atual(html)[:120]
                    )
        return ler_entrega(html, self._hoje())

    async def _aplicar_cep(self, pagina: Pagina, cep: str) -> CotacaoNavegador | None:
        s = self._s
        cep = digitos(cep)
        if not await pagina.clicar(s.abrir_local):
            return CotacaoNavegador(StatusCotacao.SEM_SELETOR, detalhe="seletor de local")
        if not await pagina.esperar((*s.cep_parte_1, *s.cep_inteiro), self._tempo_ms):
            bloqueio = detectar_bloqueio(await pagina.html(), await pagina.url())
            return bloqueio or CotacaoNavegador(StatusCotacao.SEM_SELETOR, detalhe="campo de CEP")
        if await pagina.preencher(s.cep_parte_1, cep[:5]):
            if not await pagina.preencher(s.cep_parte_2, cep[5:]):
                return CotacaoNavegador(StatusCotacao.SEM_SELETOR, detalhe="segunda parte do CEP")
        elif not await pagina.preencher(s.cep_inteiro, f"{cep[:5]}-{cep[5:]}"):
            return CotacaoNavegador(StatusCotacao.SEM_SELETOR, detalhe="campo de CEP")
        if not await pagina.clicar(s.confirmar):
            return CotacaoNavegador(StatusCotacao.SEM_SELETOR, detalhe="botão de confirmar")
        await pagina.aguardar(
            lambda h: cep_aplicado(h, cep) or cep_rejeitado(h) or bool(detectar_bloqueio(h, "")),
            self._tempo_ms,
        )
        html = await pagina.html()
        if bloqueio := detectar_bloqueio(html, await pagina.url()):
            return bloqueio
        if cep_rejeitado(html):
            return CotacaoNavegador(StatusCotacao.CEP_REJEITADO, detalhe=f"CEP {cep} recusado")
        if await pagina.esperar(s.fechar_aviso, ESPERA_AVISO_MS):
            await pagina.clicar(s.fechar_aviso)
        return None
