import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.id_requisicao import id_requisicao
from app.api.respostas import RespostaJson
from app.cep import CepInvalido, CepNaoEncontrado
from app.limites import Limitado, tentar_depois

log = logging.getLogger("zpektral")


def registrar_tratadores(app: FastAPI) -> None:
    @app.exception_handler(Limitado)
    async def limitado(_: Request, excecao: Limitado) -> RespostaJson:
        return RespostaJson(
            {"detail": excecao.mensagem},
            status_code=excecao.status,
            headers={"retry-after": tentar_depois(excecao.espera)},
        )

    @app.exception_handler(RequestValidationError)
    async def invalida(_: Request, excecao: RequestValidationError) -> RespostaJson:
        campos = sorted({str(e["loc"][-1]) for e in excecao.errors() if e.get("loc")})
        mensagem = f"Parâmetro inválido: {', '.join(campos)}" if campos else "Requisição inválida"
        return RespostaJson({"detail": mensagem}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)

    @app.exception_handler(CepInvalido)
    async def cep_invalido(_: Request, excecao: CepInvalido) -> RespostaJson:
        return RespostaJson(
            {"detail": str(excecao)}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT
        )

    @app.exception_handler(CepNaoEncontrado)
    async def cep_nao_encontrado(_: Request, __: CepNaoEncontrado) -> RespostaJson:
        return RespostaJson({"detail": "CEP não encontrado"}, status_code=status.HTTP_404_NOT_FOUND)


class CapturaErros:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, escopo: Scope, receive: Receive, send: Send) -> None:
        if escopo["type"] != "http":
            await self.app(escopo, receive, send)
            return
        iniciada = False

        async def marcando(mensagem: Message) -> None:
            nonlocal iniciada
            if mensagem["type"] == "http.response.start":
                iniciada = True
            await send(mensagem)

        try:
            await self.app(escopo, receive, marcando)
        except Exception:
            id_req = id_requisicao(escopo)
            log.exception("erro inesperado em %s", escopo.get("path"), extra={"request_id": id_req})
            if iniciada:
                raise
            resposta = RespostaJson(
                {"detail": "Erro interno", "id": id_req},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
            await resposta(escopo, receive, send)
