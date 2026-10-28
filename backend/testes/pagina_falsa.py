import html as html_lib
import re
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager

from app.navegador.base import Estrategia, Pagina, Seletor

_TAGS = re.compile(r"<[^>]+>")
_ABERTURA = re.compile(r"<(button|a|input|div|span)\b([^>]*)>", re.I)


def _elementos(html: str) -> list[tuple[str, str, str]]:
    saida = []
    for m in _ABERTURA.finditer(html):
        tag = m.group(1)
        fim = html.find(f"</{tag}>", m.end())
        saida.append((tag, m.group(2), html[m.end() : fim] if fim >= 0 else ""))
    return saida


def _texto(trecho: str) -> str:
    return " ".join(html_lib.unescape(_TAGS.sub(" ", trecho)).split())


def _atributo(atributos: str, nome: str) -> str:
    achado = re.search(rf'{nome}="([^"]*)"', atributos, re.I)
    return html_lib.unescape(achado.group(1)) if achado else ""


def encontra(s: Seletor, html: str) -> bool:
    if s.estrategia is Estrategia.CSS:
        for parte in s.valor.split(","):
            parte = parte.strip()
            if parte.startswith("#"):
                ident = re.match(r"#([\w-]+)", parte)
                if ident and f'id="{ident.group(1)}"' in html:
                    return True
            for nome, valor in re.findall(r"\[([\w-]+)\*?='([^']+)'", parte):
                if re.search(rf'{nome}="[^"]*{re.escape(valor)}', html, re.I):
                    return True
        return False
    elementos = _elementos(html)
    if s.estrategia is Estrategia.PAPEL:
        nome = re.compile(s.nome or ".*", re.I)
        for tag, atributos, conteudo in elementos:
            papel_real = _atributo(atributos, "role") or {
                "button": "button",
                "a": "link",
                "input": "textbox",
            }.get(tag.lower(), "")
            if papel_real != s.valor:
                continue
            acessivel = _atributo(atributos, "aria-label") or _texto(conteudo)
            acessivel = acessivel or _atributo(atributos, "placeholder")
            if nome.search(acessivel):
                return True
        return False
    padrao = re.compile(s.valor, re.I)
    if s.estrategia is Estrategia.ROTULO:
        return any(padrao.search(v) for v in re.findall(r'aria-label="([^"]*)"', html))
    if s.estrategia is Estrategia.PLACEHOLDER:
        return any(padrao.search(v) for v in re.findall(r'placeholder="([^"]*)"', html))
    trechos = [_texto(t) for t in re.split(r"<[^>]+>", html)]
    return any(padrao.search(t) for t in trechos if t)


class PaginaFalsa:
    def __init__(
        self,
        paginas: dict[str, str],
        ao_clicar: Callable[["PaginaFalsa", Seletor], None] | None = None,
        url_final: Callable[[str], str] | None = None,
    ):
        self.paginas = paginas
        self.atual = ""
        self.endereco = ""
        self.ao_clicar = ao_clicar
        self.url_final = url_final
        self.abertas: list[str] = []
        self.cliques: list[Seletor] = []
        self.preenchidos: list[tuple[Seletor, str]] = []

    def _primeiro(self, seletores: Sequence[Seletor]) -> Seletor | None:
        return next((s for s in seletores if encontra(s, self.atual)), None)

    async def abrir(self, url: str) -> None:
        self.abertas.append(url)
        self.endereco = self.url_final(url) if self.url_final else url
        self.atual = self.paginas.get(url, self.paginas.get("*", ""))

    async def html(self) -> str:
        return self.atual

    async def texto(self) -> str:
        return "\n".join(
            t for t in (_texto(x) for x in re.split(r"</?(?:div|p|li|br)[^>]*>", self.atual)) if t
        )

    async def url(self) -> str:
        return self.endereco

    async def clicar(self, seletores: Sequence[Seletor]) -> bool:
        escolhido = self._primeiro(seletores)
        if escolhido is None:
            return False
        self.cliques.append(escolhido)
        if self.ao_clicar:
            self.ao_clicar(self, escolhido)
        return True

    async def preencher(self, seletores: Sequence[Seletor], valor: str) -> bool:
        escolhido = self._primeiro(seletores)
        if escolhido is None:
            return False
        self.preenchidos.append((escolhido, valor))
        return True

    async def esperar(self, seletores: Sequence[Seletor], tempo_ms: int) -> bool:
        return self._primeiro(seletores) is not None

    async def aguardar(self, condicao: Callable[[str], bool], tempo_ms: int) -> bool:
        return condicao(self.atual)


class NavegadorFalso:
    def __init__(self, pagina: PaginaFalsa):
        self.pagina_falsa = pagina
        self.sessoes = 0

    @asynccontextmanager
    async def pagina(self) -> AsyncIterator[Pagina]:
        self.sessoes += 1
        yield self.pagina_falsa


class IntervaloImediato:
    async def aguardar(self) -> None:
        return None
