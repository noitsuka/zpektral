import hashlib
import json

import httpx
import pytest
from pydantic import SecretStr

from app.cliente_http import ErroExterno
from app.fontes.shopee import API, FonteShopee, assinatura
from app.modelos import Origem, StatusFrete
from testes.conftest import contexto, resposta_json

NOS = {
    "data": {
        "productOfferV2": {
            "nodes": [
                {
                    "itemId": 1,
                    "productName": "Fone Bluetooth JBL Tune 520BT",
                    "priceMin": "199.90",
                    "imageUrl": "https://cf.shopee.com.br/file/x",
                    "shopName": "JBL Oficial",
                    "offerLink": "https://s.shopee.com.br/abc",
                },
                {"itemId": 2, "productName": "Sem preço", "priceMin": None},
            ]
        }
    }
}


def habilitar(config):
    config.shopee_id_app = "123"
    config.shopee_segredo = SecretStr("s3cr3t")


def teste_assinatura_segue_a_formula_documentada():
    esperadas = hashlib.sha256(b"1231700000000{}s3cr3t").hexdigest()
    assert assinatura("123", 1700000000, "{}", "s3cr3t") == esperadas


async def teste_desativada_sem_credenciais(http, config):
    assert FonteShopee(http, config).ativa is False


async def teste_corpo_assinado_e_o_corpo_enviado(simulador, http, config):
    habilitar(config)

    def conferir(requisicao: httpx.Request):
        corpo = requisicao.content.decode()
        autenticacao = requisicao.headers["authorization"]
        assert autenticacao.startswith("SHA256 Credential=123, Timestamp=1700000000, Signature=")
        assert autenticacao.endswith(assinatura("123", 1700000000, corpo, "s3cr3t"))
        assert json.loads(corpo)["query"].startswith('{productOfferV2(keyword: "fone jbl \\"x\\""')
        return resposta_json(NOS)

    simulador.post(API).mock(side_effect=conferir)
    fonte = FonteShopee(http, config, relogio=lambda: 1700000000)
    ofertas = await fonte.buscar(contexto('fone jbl "x"'))
    assert len(ofertas) == 1
    [o] = ofertas
    assert o.preco == 19990
    assert o.origem is Origem.MARKETPLACE
    assert o.link == "https://s.shopee.com.br/abc"


async def teste_erros_do_graphql_sao_levantados(simulador, http, config):
    habilitar(config)
    simulador.post(API).mock(
        resposta_json({"errors": [{"message": "error [10020]: Invalid Signature"}]})
    )
    with pytest.raises(ErroExterno, match="Invalid Signature"):
        await FonteShopee(http, config).buscar(contexto("fone"))


def _pagina(nos, continua):
    return {
        "data": {
            "productOfferV2": {
                "nodes": nos,
                "pageInfo": {"page": 1, "limit": 50, "hasNextPage": continua},
            }
        }
    }


def _no(item, preco="99.90", **extra):
    return {
        "itemId": item,
        "productName": f"Fone Bluetooth JBL {item}",
        "priceMin": preco,
        "priceMax": preco,
        "shopId": 77,
        "shopName": "JBL Oficial",
        "productLink": f"https://shopee.com.br/product/77/{item}",
        "offerLink": f"https://s.shopee.com.br/{item}",
        "imageUrl": f"https://cf.shopee.com.br/file/{item}",
        **extra,
    }


async def teste_pagina_ate_o_limite_configurado_e_para_sem_proxima(simulador, http, config):
    habilitar(config)
    config.shopee_paginas = 3
    paginas_pedidas = []

    def responder(requisicao: httpx.Request):
        consulta = json.loads(requisicao.content)["query"]
        pagina = int(consulta.split("page: ")[1].split(")")[0])
        paginas_pedidas.append(pagina)
        assert "pageInfo{page limit hasNextPage}" in consulta
        assert "shopId" in consulta and "productLink" in consulta
        return resposta_json(_pagina([_no(pagina * 10)], continua=pagina < 2))

    simulador.post(API).mock(side_effect=responder)
    ofertas = await FonteShopee(http, config).buscar(contexto("fone jbl"))
    assert paginas_pedidas == [1, 2]
    assert [o.id for o in ofertas] == ["shopee:10", "shopee:20"]
    assert [o.posicao for o in ofertas] == [0, 1]


async def teste_campos_do_produto_e_desconto(simulador, http, config):
    habilitar(config)
    simulador.post(API).mock(
        resposta_json(_pagina([_no(5, preco="80.00", priceDiscountRate=20)], continua=False))
    )
    [o] = await FonteShopee(http, config).buscar(contexto("fone jbl"))
    assert o.preco == 8000 and o.preco_original == 10000
    assert o.vendedor == "JBL Oficial"
    assert o.imagem == "https://cf.shopee.com.br/file/5"
    assert o.link == "https://s.shopee.com.br/5"


class FreteFalso:
    def __init__(self, resultados=None, erro=None):
        self.resultados = resultados or {}
        self.erro = erro
        self.pedidos = []

    async def cotar(self, produtos, cep, destino):
        self.pedidos.append((list(produtos), cep))
        if self.erro:
            raise self.erro
        destino.update(self.resultados)


async def teste_frete_por_navegador_entra_na_oferta(simulador, http, config):
    from app.navegador.base import CotacaoNavegador, StatusCotacao

    habilitar(config)
    simulador.post(API).mock(resposta_json(_pagina([_no(1), _no(2)], continua=False)))
    frete = FreteFalso(
        {
            "shopee:1": CotacaoNavegador(StatusCotacao.COTADO, valor=1290, prazo_dias=8),
            "shopee:2": CotacaoNavegador(StatusCotacao.DESAFIO),
        }
    )
    previas = []
    ofertas = await FonteShopee(http, config, frete=frete).buscar(
        contexto("fone bluetooth jbl"), lambda lote: previas.append([o.frete.status for o in lote])
    )
    assert frete.pedidos == [([("shopee:1", 77, "1"), ("shopee:2", 77, "2")], "30130010")]
    por_id = {o.id: o for o in ofertas}
    assert por_id["shopee:1"].frete.status is StatusFrete.CALCULADO
    assert por_id["shopee:1"].frete.valor == 1290 and por_id["shopee:1"].total_exato
    assert por_id["shopee:2"].frete.status is StatusFrete.NAO_INFORMADO
    assert previas == [[StatusFrete.CALCULANDO, StatusFrete.CALCULANDO]]


async def teste_navegador_ausente_nao_derruba_a_busca(simulador, http, config):
    from app.navegador.base import NavegadorIndisponivel

    habilitar(config)
    simulador.post(API).mock(resposta_json(_pagina([_no(1)], continua=False)))
    frete = FreteFalso(erro=NavegadorIndisponivel("pacote playwright não instalado"))
    [o] = await FonteShopee(http, config, frete=frete).buscar(contexto("fone bluetooth jbl"))
    assert o.frete.status is StatusFrete.NAO_INFORMADO


async def teste_sem_cep_nao_abre_navegador(simulador, http, config):
    habilitar(config)
    simulador.post(API).mock(resposta_json(_pagina([_no(1)], continua=False)))
    frete = FreteFalso()
    await FonteShopee(http, config, frete=frete).buscar(contexto("fone bluetooth jbl", cep=None))
    assert frete.pedidos == []


@pytest.mark.skip(reason="credentials missing: SHOPEE_ID_APP e SHOPEE_SEGREDO")
async def teste_ao_vivo_api_de_afiliados(http, config):
    ofertas = await FonteShopee(http, config).buscar(contexto("fone bluetooth jbl"))
    assert ofertas
