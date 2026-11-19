import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy.exc import OperationalError

from app.api import erros
from app.api.erros import CapturaErros
from app.api.id_requisicao import IdRequisicao
from app.api.respostas import RespostaJson
from app.api.rotas import busca, informacoes
from app.banco import criar_motor, criar_sessoes, criar_tabelas_locais
from app.busca import ServicoBusca
from app.cep import ServicoCep
from app.cliente_http import ClienteHttp
from app.configuracao import Configuracoes, obter_configuracoes
from app.credenciais import Cifra, GuardaCredenciais
from app.fontes import criar_fontes
from app.historico import RegistroHistorico
from app.limites import CabecalhosSeguranca, Guarda
from app.navegador.playwright import NavegadorPlaywright
from app.saude import PainelSaude

log = logging.getLogger("zpektral")
logging.getLogger("httpx").setLevel(logging.WARNING)


def guarda_de_credenciais(config: Configuracoes, sessoes) -> GuardaCredenciais | None:
    chave = config.chave_credenciais.get_secret_value()
    cifra = None
    try:
        cifra = Cifra(chave) if chave else None
    except ValueError as erro:
        log.error("credenciais OAuth desligadas: %s", erro)
    if sessoes is not None and cifra is not None:
        return GuardaCredenciais(sessoes, cifra)
    if config.ml_token_renovacao.get_secret_value():
        if config.url_banco:
            log.error("mercado livre desativado: falta uma CHAVE_CREDENCIAIS válida")
        else:
            log.warning("sem banco: o token renovado do mercado livre fica só nesta instância")
    return None


def criar_app(config: Configuracoes | None = None) -> FastAPI:
    config = config or obter_configuracoes()

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        # cada loja resolve o nome duas vezes no executor padrão (checagem do destino e conexão);
        # com as poucas threads de uma função da Vercel, a primeira busca de uma instância nova
        # fazia fila e estourava o tempo de conexão em todas as lojas
        asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max_workers=64))
        http = ClienteHttp(config)
        navegador = (
            NavegadorPlaywright(config)
            if config.amazon_frete_navegador or config.shopee_frete_navegador
            else None
        )
        url_banco = config.url_banco or (
            f"sqlite+aiosqlite:///{config.arquivo_historico_local}"
            if config.arquivo_historico_local
            else ""
        )
        motor = criar_motor(url_banco) if url_banco else None
        if motor is not None:
            try:
                await criar_tabelas_locais(motor)
            except OperationalError as erro:
                # num preview da Vercel sem banco, o arquivo local cai numa pasta somente leitura
                log.warning("histórico local desligado: %s", erro.orig)
                await motor.dispose()
                motor = None
        sessoes = criar_sessoes(motor) if motor is not None else None
        historico = (
            RegistroHistorico(sessoes, dias_retencao=config.dias_historico) if sessoes else None
        )
        app.state.ceps = ServicoCep(http, config.segundos_cache_cep, config.entradas_cache_cep)
        app.state.historico = historico
        app.state.guarda = Guarda.das_configuracoes(config)
        buscas = app.state.buscas = ServicoBusca(
            criar_fontes(http, config, navegador, guarda_de_credenciais(config, sessoes)),
            config,
            PainelSaude(http, config.url_webhook_alerta.get_secret_value()),
            ao_concluir=historico.registrar if historico else None,
        )
        yield
        await buscas.encerrar()
        await http.fechar()
        if navegador is not None:
            await navegador.fechar()
        if motor is not None:
            await motor.dispose()

    app = FastAPI(
        title="zpektral API",
        version="0.1.0",
        description="Busca um produto em várias lojas e compara o preço final no seu CEP. "
        "Todos os valores monetários são inteiros em centavos.",
        lifespan=ciclo_de_vida,
        default_response_class=RespostaJson,
    )
    app.add_middleware(CapturaErros)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.origens_cors,
        allow_methods=["GET"],
        allow_headers=["Content-Type"],
        expose_headers=["Retry-After", "X-Request-ID"],
        max_age=600,
    )
    app.add_middleware(CabecalhosSeguranca, hsts=config.hsts)
    app.add_middleware(IdRequisicao)
    erros.registrar_tratadores(app)
    app.include_router(busca.roteador)
    app.include_router(informacoes.roteador)
    return app


app = criar_app()
