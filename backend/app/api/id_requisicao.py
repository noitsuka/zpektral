import re
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CABECALHO = b"x-request-id"
_VALIDO = re.compile(rb"^[A-Za-z0-9-]{8,64}$")


def id_requisicao(escopo: Scope) -> str:
    return escopo.get("request_id", "")


class IdRequisicao:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, escopo: Scope, receive: Receive, send: Send) -> None:
        if escopo["type"] != "http":
            await self.app(escopo, receive, send)
            return
        recebido = dict(escopo["headers"]).get(CABECALHO, b"")
        escopo["request_id"] = recebido.decode() if _VALIDO.match(recebido) else uuid.uuid4().hex

        async def com_id(mensagem: Message) -> None:
            if mensagem["type"] == "http.response.start":
                headers = [(k, v) for k, v in mensagem.get("headers", []) if k != CABECALHO]
                headers.append((CABECALHO, escopo["request_id"].encode()))
                mensagem["headers"] = headers
            await send(mensagem)

        await self.app(escopo, receive, com_id)
