import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

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
from app.fontes import criar_fontes
from app.historico import RegistroHistorico
from app.limites import CabecalhosSeguranca, Guarda
from app.navegador.playwright import NavegadorPlaywright
from app.saude import PainelSaude

log = logging.getLogger("zpektral")


def criar_app(config: Configuracoes | None = None) -> FastAPI:
    config = config or obter_configuracoes()

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
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
            await criar_tabelas_locais(motor)
        historico = (
            RegistroHistorico(criar_sessoes(motor), dias_retencao=config.dias_historico)
            if motor
            else None
        )
        app.state.ceps = ServicoCep(http, config.segundos_cache_cep, config.entradas_cache_cep)
        app.state.historico = historico
        app.state.guarda = Guarda.das_configuracoes(config)
        buscas = app.state.buscas = ServicoBusca(
            criar_fontes(http, config, navegador),
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
