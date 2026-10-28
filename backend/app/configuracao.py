from functools import lru_cache
from typing import Annotated

from pydantic import AliasChoices, Field, PositiveFloat, PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracoes(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    origens_cors: list[str] = ["http://localhost:3000"]
    confiar_proxy: bool = False
    hsts: bool = False

    requisicoes_por_minuto: PositiveInt = 120
    rajada_requisicoes: PositiveInt = 40
    buscas_novas_por_minuto: PositiveInt = 12
    rajada_buscas_novas: PositiveInt = 6
    maximo_buscas_em_andamento: PositiveInt = 24
    transmissoes_por_ip: PositiveInt = 3

    url_banco: str = Field(
        default="", validation_alias=AliasChoices("DATABASE_URL_UNPOOLED", "DATABASE_URL")
    )

    segundos_limite_fonte: PositiveFloat = 12
    segundos_limite_conexao: PositiveFloat = 3
    segundos_limite_leitura: PositiveFloat = 7
    hosts_maximos: PositiveInt = 128
    requisicoes_por_host: PositiveInt = 16

    produtos_por_loja: PositiveInt = 30
    cotacoes_por_loja: PositiveInt = 40
    relevancia_minima_cotacao: Annotated[int, Field(ge=0, le=100)] = 65

    segundos_cache_busca: PositiveInt = 300
    segundos_cache_cotacao: PositiveInt = 300
    entradas_cache_cotacao: PositiveInt = 50_000
    taxa_auditoria_cotacao: Annotated[float, Field(ge=0, le=1)] = 0.05
    aquecimento_auditoria_cotacao: Annotated[int, Field(ge=0)] = 20
    segundos_cache_cep: PositiveInt = 86_400
    entradas_cache_busca: PositiveInt = 128
    entradas_cache_cep: PositiveInt = 4096

    ml_id_cliente: str = ""
    ml_segredo_cliente: SecretStr = SecretStr("")
    ml_token_renovacao: SecretStr = SecretStr("")
    ml_arquivo_token: str = ".ml-token.json"

    url_webhook_alerta: SecretStr = SecretStr("")

    ebay_id_cliente: str = ""
    ebay_segredo: SecretStr = SecretStr("")
    aliquota_imposto_importacao: Annotated[float, Field(ge=0, le=1)] = 0.6
    aliquota_icms_importacao: Annotated[float, Field(ge=0, lt=1)] = 0.2

    shopee_id_app: str = ""
    shopee_segredo: SecretStr = SecretStr("")
    amazon_busca_publica: bool = True
    dias_historico: Annotated[int, Field(ge=7, le=3650)] = 180
    arquivo_historico_local: str = "zpektral.db"
    shopee_paginas: Annotated[int, Field(ge=1, le=5)] = 2
    amazon_frete_navegador: bool = False
    shopee_frete_navegador: bool = False
    navegador_cotacoes: Annotated[int, Field(ge=1, le=10)] = 4
    navegador_intervalo_segundos: Annotated[float, Field(ge=2, le=30)] = 2.0
    navegador_tempo_limite_ms: Annotated[int, Field(ge=2000, le=60000)] = 15000

    agente_usuario: str = "zpektral/0.1 (+https://github.com/noitsuka/zpektral)"


@lru_cache
def obter_configuracoes() -> Configuracoes:
    return Configuracoes()
