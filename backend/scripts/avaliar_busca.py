import argparse
import asyncio
import json
import math
import re
import sqlite3
import statistics
import time
import unicodedata
import zlib
from pathlib import Path
from typing import Any

import httpx

import app
from app.busca import ServicoBusca
from app.cliente_http import ClienteHttp, DestinoProibido
from app.configuracao import Configuracoes
from app.fontes import criar_fontes
from app.ordenacao import Filtros, aplicar

CONSULTAS = Path(__file__).resolve().parents[1] / "testes" / "dados" / "consultas_avaliacao.json"
CONJUNTOS = ("desenvolvimento", "teste", "todas")
# saíram do cadastro em 076f8e1 porque o robots.txt proíbe /api/; versões antigas ainda as chamam
FORA_POR_ROBOTS = frozenset(
    {"casaevideo", "philco", "britania", "polishop", "pbkids", "lebiscuit", "zonasul"}
)
_LETRA_DIGITO = re.compile(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])")
_NAO_ALFANUMERICO = re.compile(r"[^a-z0-9]+")


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " " + " ".join(_NAO_ALFANUMERICO.sub(" ", _LETRA_DIGITO.sub(" ", texto)).split()) + " "


def casa(texto: str, termo: str) -> bool:
    if termo.startswith("re:"):
        return re.search(termo[3:], texto) is not None
    base = normalizar(termo.strip("^*")).rstrip()
    alvo = base if termo.endswith("*") else base + " "
    return texto.startswith(alvo) if termo.startswith("^") else alvo in texto


def _algum(texto: str, termos: list[str]) -> bool:
    return any(casa(texto, t) for t in termos)


def julgar(
    criterio: dict[str, Any], titulo: str, marca: str | None, ean: str | None
) -> tuple[bool, bool]:
    if ean and criterio.get("ean") and ean.zfill(13) == criterio["ean"]:
        return True, False
    texto = normalizar(f"{titulo} {marca or ''}")
    atributos = criterio.get("atributos", [])
    aceitos = [_algum(texto, a["aceita"]) for a in atributos]
    errada = any(
        _algum(texto, a.get("exclui", [])) or (not aceito and _algum(texto, a.get("rivais", [])))
        for a, aceito in zip(atributos, aceitos, strict=True)
    )
    relevante = (
        all(_algum(texto, grupo) for grupo in criterio.get("exige", []))
        and all(aceitos)
        and not errada
        and not _algum(texto, criterio.get("proibe", []))
    )
    return relevante, errada


def carregar_consultas(caminho: Path) -> list[dict[str, Any]]:
    bruto = json.loads(caminho.read_text("utf-8"))
    grupos = bruto["grupos"]
    for consulta in bruto["consultas"]:
        for atributo in consulta.get("atributos", []):
            rivais = [r for t in atributo["rivais"] for r in grupos.get(t, [t])]
            atributo["rivais"] = [r for r in dict.fromkeys(rivais) if r not in atributo["aceita"]]
    return bruto["consultas"]


class ClienteGravado(ClienteHttp):
    def __init__(self, config: Configuracoes, banco: Path, somente_cache: bool):
        super().__init__(config)
        self._banco = sqlite3.connect(banco)
        self._banco.execute(
            "create table if not exists respostas"
            " (chave text primary key, status integer, tipo text, corpo blob)"
        )
        self._somente_cache = somente_cache
        self.requisicoes = 0

    async def _buscar(self, metodo: str, url: str, host: str, **argumentos: Any) -> httpx.Response:
        requisicao = httpx.Request(metodo, url)
        # sem CEP a cotação só mexe em preço; a avaliação mede a recuperação
        if "/orderForms/simulation" in url:
            raise DestinoProibido("a avaliação não cota frete", request=requisicao)
        self.requisicoes += 1
        chave = f"{metodo} {url} {argumentos.get('content', b'').decode()}"
        linha = self._banco.execute(
            "select status, tipo, corpo from respostas where chave = ?", (chave,)
        ).fetchone()
        if linha is None:
            if self._somente_cache:
                raise httpx.ConnectError("fora do cache", request=requisicao)
            try:
                resposta = await super()._buscar(metodo, url, host, **argumentos)
            except httpx.HTTPError:
                self._guardar(chave, 0, "", b"")
                raise
            tipo = resposta.headers.get("content-type", "")
            self._guardar(chave, resposta.status_code, tipo, resposta.content)
            return resposta
        status, tipo, corpo = linha
        if status == 0:
            raise httpx.ConnectError("falha gravada", request=requisicao)
        return httpx.Response(
            status,
            headers={"content-type": tipo},
            content=zlib.decompress(corpo),
            request=requisicao,
        )

    def _guardar(self, chave: str, status: int, tipo: str, corpo: bytes) -> None:
        self._banco.execute(
            "insert or replace into respostas values (?, ?, ?, ?)",
            (chave, status, tipo, zlib.compress(corpo)),
        )

    async def fechar(self) -> None:
        await super().fechar()
        self._banco.commit()
        self._banco.close()


def _resumo(oferta: Any) -> dict[str, Any]:
    return {
        "id": oferta.id,
        "loja": oferta.loja.id,
        "titulo": oferta.titulo,
        "marca": oferta.marca,
        "ean": oferta.ean,
        "nota": oferta.relevancia,
    }


async def rodar(consultas: list[dict[str, Any]], banco: Path, somente_cache: bool) -> list[dict]:
    # prazo folgado: a primeira passada grava as respostas que as outras versões vão reler
    config = Configuracoes(_env_file=None, segundos_limite_fonte=30)
    saida = []
    async with ClienteGravado(config, banco, somente_cache) as http:
        fontes = [f for f in criar_fontes(http, config) if f.id not in FORA_POR_ROBOTS]
        servico = ServicoBusca(fontes, config)
        for consulta in consultas:
            antes, inicio = http.requisicoes, time.monotonic()
            trabalho, _ = servico.iniciar(consulta["consulta"], None)
            await trabalho.aguardar()
            todas = trabalho.ofertas_agrupadas()
            exibidas, _ = aplicar(todas, Filtros())
            elegiveis, _ = aplicar(todas, Filtros(relevancia_min=0))
            mostradas = {o.id for o in exibidas}
            saida.append(
                {
                    "id": consulta["id"],
                    "requisicoes": http.requisicoes - antes,
                    "segundos": round(time.monotonic() - inicio, 2),
                    "exibidas": [_resumo(o) for o in exibidas],
                    "ocultas": [_resumo(o) for o in elegiveis if o.id not in mostradas],
                }
            )
            print(f"{consulta['id']:40} {len(exibidas):4} exibidas", flush=True)
    return saida


def _media(valores: list[float]) -> float | None:
    return round(statistics.fmean(valores), 4) if valores else None


def medir(
    execucoes: dict[str, list[dict]], criterios: dict[str, dict]
) -> dict[str, dict[str, dict[str, float | None]]]:
    julgados: dict[tuple[str, str], tuple[bool, bool]] = {}

    def julgamento(consulta: str, oferta: dict) -> tuple[bool, bool]:
        chave = (consulta, oferta["id"])
        if chave not in julgados:
            julgados[chave] = julgar(
                criterios[consulta], oferta["titulo"], oferta["marca"], oferta["ean"]
            )
        return julgados[chave]

    piscina: dict[str, set[str]] = {}
    for registros in execucoes.values():
        for r in registros:
            achadas = (o for o in r["exibidas"] + r["ocultas"] if julgamento(r["id"], o)[0])
            piscina.setdefault(r["id"], set()).update(o["id"] for o in achadas)

    resultado: dict[str, dict[str, dict[str, float | None]]] = {}
    for rotulo, registros in execucoes.items():
        por_conjunto: dict[str, dict[str, list[float]]] = {c: {} for c in CONJUNTOS}
        for r in registros:
            lista = r["exibidas"]
            notas = [julgamento(r["id"], o) for o in lista]
            relevantes = [rel for rel, _ in notas]
            total = len(piscina[r["id"]])
            linha: dict[str, float] = {
                "zero_resultados": float(not lista),
                "requisicoes": r["requisicoes"],
                "lojas_com_relevante": len(
                    {o["loja"] for o, rel in zip(lista, relevantes, strict=True) if rel}
                ),
            }
            if criterios[r["id"]].get("atributos") and lista:
                linha["variante_errada@10"] = sum(e for _, e in notas[:10]) / len(notas[:10])
            if total:
                primeira = next((i for i, rel in enumerate(relevantes, 1) if rel), None)
                dcg = sum(rel / math.log2(i + 1) for i, rel in enumerate(relevantes[:10], 1))
                ideal = sum(1 / math.log2(i + 1) for i in range(1, min(total, 10) + 1))
                linha |= {
                    "p@5": sum(relevantes[:5]) / 5,
                    "p@10": sum(relevantes[:10]) / 10,
                    "mrr": 1 / primeira if primeira else 0.0,
                    "ndcg@10": dcg / ideal,
                    "recall@10": sum(relevantes[:10]) / total,
                    "recall@20": sum(relevantes[:20]) / total,
                    "cobertura": sum(relevantes) / total,
                }
                if lista:
                    linha["precisao"] = sum(relevantes) / len(lista)
            else:
                linha["exibidas_sem_relevante"] = len(lista)
            for conjunto in (criterios[r["id"]]["conjunto"], "todas"):
                for nome, valor in linha.items():
                    por_conjunto[conjunto].setdefault(nome, []).append(valor)
        resultado[rotulo] = {
            conjunto: {nome: _media(valores) for nome, valores in metricas.items()}
            | {
                "consultas": sum(
                    1 for r in registros if conjunto in ("todas", criterios[r["id"]]["conjunto"])
                )
            }
            for conjunto, metricas in por_conjunto.items()
        }
    return resultado


COLUNAS = (
    "p@5",
    "p@10",
    "mrr",
    "ndcg@10",
    "recall@10",
    "recall@20",
    "cobertura",
    "precisao",
    "zero_resultados",
    "variante_errada@10",
    "lojas_com_relevante",
    "requisicoes",
)


def tabela(resultado: dict[str, dict[str, dict[str, float | None]]]) -> str:
    linhas = ["| versão | conjunto | " + " | ".join(COLUNAS) + " |"]
    linhas.append("|" + " --- |" * (len(COLUNAS) + 2))
    for conjunto in CONJUNTOS:
        for rotulo, por_conjunto in resultado.items():
            valores = por_conjunto[conjunto]
            celulas = ["" if valores.get(c) is None else f"{valores[c]:.3f}" for c in COLUNAS]
            linhas.append(f"| {rotulo} | {conjunto} | " + " | ".join(celulas) + " |")
    return "\n".join(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mede a busca com consultas julgadas por regra.")
    comandos = parser.add_subparsers(dest="comando", required=True)
    rodar_cmd = comandos.add_parser("rodar", help="roda as consultas e grava as ofertas exibidas")
    rodar_cmd.add_argument("--saida", type=Path, required=True)
    rodar_cmd.add_argument("--cache", type=Path, required=True, help="banco SQLite das respostas")
    rodar_cmd.add_argument("--somente-cache", action="store_true", help="não chama as lojas")
    rodar_cmd.add_argument("--apenas", nargs="*", help="ids das consultas")
    medir_cmd = comandos.add_parser("medir", help="calcula as métricas de uma ou mais execuções")
    medir_cmd.add_argument("execucoes", type=Path, nargs="+")
    medir_cmd.add_argument("--saida", type=Path)
    args = parser.parse_args()

    consultas = carregar_consultas(CONSULTAS)
    if args.comando == "rodar":
        escolhidas = [c for c in consultas if not args.apenas or c["id"] in args.apenas]
        registros = asyncio.run(rodar(escolhidas, args.cache, args.somente_cache))
        corpo = {"origem": app.__file__, "consultas": registros}
        args.saida.write_text(json.dumps(corpo, ensure_ascii=False), "utf-8", newline="\n")
        return
    execucoes = {e.stem: json.loads(e.read_text("utf-8"))["consultas"] for e in args.execucoes}
    resultado = medir(execucoes, {c["id"]: c for c in consultas})
    print(tabela(resultado))
    if args.saida:
        texto = json.dumps(resultado, ensure_ascii=False, indent=2)
        args.saida.write_text(texto, "utf-8", newline="\n")


if __name__ == "__main__":
    main()
