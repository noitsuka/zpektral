import asyncio
import json
import re

import httpx
import pytest

from app.fontes.vtex import FonteVtex, LojaVtex, aplicar_simulacao, carregar_lojas
from app.modelos import Frete, Loja, Oferta, StatusFrete
from testes.conftest import contexto, gravacao_json, resposta_json

CARREFOUR = LojaVtex("carrefour", "Carrefour", "www.carrefour.com.br", "is")
AMERICANAS = LojaVtex("americanas", "Americanas", "www.americanas.com.br", "auto")
URL_IS = re.compile(r"https://www\.carrefour\.com\.br/api/io/_v/api/intelligent-search/.*")
URL_SIMULACAO = "https://www.carrefour.com.br/api/checkout/pub/orderForms/simulation"


def oferta_vazia() -> Oferta:
    return Oferta(id="x", titulo="TV", link="", loja=Loja("s", "S"), preco=1)


def teste_cadastro_de_lojas_e_valido():
    lojas = carregar_lojas()
    assert len(lojas) >= 34
    assert len({s.id for s in lojas}) == len(lojas)
    assert all(s.busca in {"is", "legacy", "auto"} for s in lojas)
    assert all("/" not in s.dominio and not s.dominio.startswith("http") for s in lojas)


class TesteSimulacao:
    def teste_frete_cotado_usa_a_entrega_mais_barata(self):
        oferta = oferta_vazia()
        aplicar_simulacao(oferta, gravacao_json("vtex_simulacao_bh.json"), tem_cep=True)
        oferta.consolidar()

        assert oferta.preco == 299900
        assert oferta.preco_pix == 284905
        assert oferta.frete.status is StatusFrete.CALCULADO
        assert oferta.frete.valor == 1799
        assert oferta.frete.prazo == "até 2 dias úteis"
        assert oferta.frete.prazo_dias == 2
        assert oferta.total == 284905 + 1799
        assert oferta.total_exato is True

    def teste_todas_as_opcoes_listadas_com_retiradas_no_fim(self):
        oferta = oferta_vazia()
        aplicar_simulacao(oferta, gravacao_json("vtex_simulacao_bh.json"), tem_cep=True)
        tipos = [o.tipo for o in oferta.frete.opcoes]
        assert tipos[:2] == ["entrega", "entrega"]
        assert set(tipos[2:]) == {"retirada"}
        assert [o.valor for o in oferta.frete.opcoes[:2]] == [1799, 3599]
        assert all("(" not in o.nome for o in oferta.frete.opcoes)

    def teste_parcelamento_ignora_cartao_da_loja(self):
        oferta = oferta_vazia()
        aplicar_simulacao(oferta, gravacao_json("vtex_simulacao_bh.json"), tem_cep=True)
        assert oferta.parcelamento is not None
        assert oferta.parcelamento.parcelas == 10
        assert oferta.parcelamento.juros is False
        assert oferta.parcelamento.total == 299900

    def teste_loja_que_nao_entrega_no_cep(self):
        oferta = oferta_vazia()
        aplicar_simulacao(oferta, gravacao_json("vtex_simulacao_acre.json"), tem_cep=True)
        oferta.consolidar()
        assert oferta.frete.status is StatusFrete.NAO_ENTREGA
        assert oferta.disponivel is True
        assert oferta.total_exato is False

    def teste_sem_cep_preco_exato_e_frete_nao_cotado(self):
        oferta = oferta_vazia()
        aplicar_simulacao(oferta, gravacao_json("vtex_simulacao_sem_cep.json"), tem_cep=False)
        oferta.consolidar()
        assert oferta.preco == 319900
        assert oferta.frete.status is StatusFrete.SEM_CEP
        assert oferta.total == oferta.melhor_preco

    def teste_sem_estoque(self):
        dados = gravacao_json("vtex_simulacao_bh.json")
        dados["items"][0]["availability"] = "withoutStock"
        oferta = oferta_vazia()
        aplicar_simulacao(oferta, dados, tem_cep=True)
        assert oferta.disponivel is False
        assert oferta.frete.status is StatusFrete.NAO_INFORMADO

    def teste_simulacao_vazia_significa_indisponivel(self):
        oferta = oferta_vazia()
        aplicar_simulacao(oferta, {"items": []}, tem_cep=True)
        assert oferta.disponivel is False

    def teste_so_retirada_significa_sem_entrega(self):
        dados = gravacao_json("vtex_simulacao_bh.json")
        slas = dados["logisticsInfo"][0]["slas"]
        dados["logisticsInfo"][0]["slas"] = [s for s in slas if s["deliveryChannel"] != "delivery"]
        oferta = oferta_vazia()
        aplicar_simulacao(oferta, dados, tem_cep=True)
        assert oferta.frete.status is StatusFrete.NAO_ENTREGA
        assert oferta.frete.opcoes and all(o.tipo == "retirada" for o in oferta.frete.opcoes)

    def teste_imposto_do_sla_entra_no_frete(self):
        dados = gravacao_json("vtex_simulacao_bh.json")
        for sla in dados["logisticsInfo"][0]["slas"]:
            sla["tax"] = 100
        oferta = oferta_vazia()
        aplicar_simulacao(oferta, dados, tem_cep=True)
        assert oferta.frete.valor == 1899

    def teste_pix_ausente_no_checkout_apaga_pix_do_catalogo(self):
        dados = gravacao_json("vtex_simulacao_bh.json")
        opcoes = dados["paymentData"]["installmentOptions"]
        dados["paymentData"]["installmentOptions"] = [
            o for o in opcoes if o["paymentName"] != "Pix"
        ]
        oferta = oferta_vazia()
        oferta.preco_pix = 1
        aplicar_simulacao(oferta, dados, tem_cep=True)
        assert oferta.preco_pix is None

    def teste_sem_juros_vence_mais_parcelas_com_juros(self):
        dados = gravacao_json("vtex_simulacao_bh.json")
        visa = next(
            o for o in dados["paymentData"]["installmentOptions"] if o["paymentName"] == "Visa"
        )
        visa["installments"].append(
            {"count": 18, "value": 19000, "total": 342000, "interestRate": 199}
        )
        oferta = oferta_vazia()
        aplicar_simulacao(oferta, dados, tem_cep=True)
        assert oferta.parcelamento.parcelas == 10
        assert oferta.parcelamento.juros is False


class TesteBusca:
    async def teste_busca_inteligente_e_uma_cotacao_por_oferta(self, simulador, http, config):
        buscar = simulador.get(URL_IS).mock(
            resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
        )
        corpos = []

        def simular(requisicao: httpx.Request):
            corpo = json.loads(requisicao.content)
            corpos.append(corpo)
            return resposta_json(gravacao_json("vtex_simulacao_bh.json"))

        simulador.post(URL_SIMULACAO).mock(side_effect=simular)
        ofertas = await FonteVtex(CARREFOUR, http, config).buscar(contexto("smart tv 55"))

        assert buscar.call_count == 1
        assert ofertas
        assert all(len(b["items"]) == 1 for b in corpos)
        assert all(b["postalCode"] == "30130010" for b in corpos)
        cotada = [o for o in ofertas if o.frete.status is StatusFrete.CALCULADO]
        assert len(cotada) == len(corpos)
        assert all(o.relevancia >= config.relevancia_minima_cotacao for o in cotada)
        frete_sem_cotacao = [o for o in ofertas if o.relevancia < config.relevancia_minima_cotacao]
        assert all(o.frete.status is StatusFrete.NAO_INFORMADO for o in frete_sem_cotacao)

    async def teste_links_ids_e_imagens(self, simulador, http, config):
        simulador.get(URL_IS).mock(
            resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
        )
        simulador.post(URL_SIMULACAO).mock(resposta_json(gravacao_json("vtex_simulacao_bh.json")))
        ofertas = await FonteVtex(CARREFOUR, http, config).buscar(contexto("smart tv 55"))
        for o in ofertas:
            _, sku, vendedor = o.id.split(":")
            assert o.link.startswith("https://www.carrefour.com.br/")
            assert o.link.endswith(f"/p?skuId={sku}")
            assert o.link_carrinho == (
                "https://www.carrefour.com.br/checkout/cart/add"
                f"?sku={sku}&qty=1&seller={vendedor}&sc=1&redirect=true"
            )
            assert re.fullmatch(r"carrefour:\d+:\w+", o.id)
            assert o.loja.id == "carrefour"
        assert len({o.id for o in ofertas}) == len(ofertas)

    async def teste_auto_recorre_a_busca_legada_quando_a_inteligente_redireciona(
        self, simulador, http, config
    ):
        simulador.get(re.compile(r"https://www\.americanas\.com\.br/api/io/.*")).mock(
            resposta_json(gravacao_json("vtex_busca_inteligente_redirecionada.json"))
        )
        legada = simulador.get(re.compile(r".*/api/catalog_system/pub/products/search.*")).mock(
            httpx.Response(206, json=gravacao_json("vtex_busca_legada_americanas.json"))
        )
        simulador.post(re.compile(r".*/simulation")).mock(
            resposta_json(gravacao_json("vtex_simulacao_bh.json"))
        )
        ofertas = await FonteVtex(AMERICANAS, http, config).buscar(contexto("smart tv 55"))
        assert legada.call_count == 1
        assert ofertas
        assert all(o.preco > 0 for o in ofertas)
        assert all(o.vendedor != "AMERICANAS SA" for o in ofertas)
        assert {o.origem for o in ofertas} == {"marketplace"}

    async def teste_auto_recorre_a_busca_legada_quando_a_inteligente_falha(
        self, simulador, http, config
    ):
        simulador.get(re.compile(r".*/api/io/.*")).mock(httpx.Response(404))
        simulador.get(re.compile(r".*/catalog_system/.*")).mock(
            httpx.Response(206, json=gravacao_json("vtex_busca_legada_americanas.json"))
        )
        simulador.post(re.compile(r".*/simulation")).mock(httpx.Response(500))
        ofertas = await FonteVtex(AMERICANAS, http, config).buscar(contexto("tv 55"))
        assert ofertas

    async def teste_cotacao_falha_mantem_preco_do_catalogo(self, simulador, http, config):
        simulador.get(URL_IS).mock(
            resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
        )
        simulador.post(URL_SIMULACAO).mock(httpx.Response(503))
        ofertas = await FonteVtex(CARREFOUR, http, config).buscar(contexto("smart tv 55"))
        assert ofertas
        for o in ofertas:
            assert o.frete.status is StatusFrete.NAO_INFORMADO
            assert o.total_exato is False
            assert o.preco > 0

    async def teste_cotacoes_lentas_sao_abandonadas_no_prazo_da_loja(self, simulador, http, config):
        config.segundos_limite_fonte = 1.0
        simulador.get(URL_IS).mock(
            resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
        )

        async def lenta(_):
            await asyncio.sleep(5)
            return resposta_json(gravacao_json("vtex_simulacao_bh.json"))

        simulador.post(URL_SIMULACAO).mock(side_effect=lenta)
        laco = asyncio.get_running_loop()
        inicio = laco.time()
        ofertas = await FonteVtex(CARREFOUR, http, config).buscar(contexto("smart tv 55"))
        assert laco.time() - inicio < 1.2
        assert ofertas and all(o.frete.status is StatusFrete.NAO_INFORMADO for o in ofertas)

    async def teste_loja_so_com_busca_inteligente_propaga_erro(self, simulador, http, config):
        from app.cliente_http import ErroExterno

        simulador.get(URL_IS).mock(httpx.Response(403))
        with pytest.raises(ErroExterno):
            await FonteVtex(CARREFOUR, http, config).buscar(contexto("tv"))

    async def teste_sem_cep_toda_oferta_fica_sem_cep(self, simulador, http, config):
        simulador.get(URL_IS).mock(
            resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
        )
        simulador.post(URL_SIMULACAO).mock(
            resposta_json(gravacao_json("vtex_simulacao_sem_cep.json"))
        )
        ofertas = await FonteVtex(CARREFOUR, http, config).buscar(contexto("smart tv 55", None))
        assert ofertas
        assert {o.frete.status for o in ofertas} == {StatusFrete.SEM_CEP}

    async def teste_cotacoes_limitadas_por_loja(self, simulador, http, config):
        config.cotacoes_por_loja = 2
        simulador.get(URL_IS).mock(
            resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
        )
        sim = simulador.post(URL_SIMULACAO).mock(
            resposta_json(gravacao_json("vtex_simulacao_bh.json"))
        )
        await FonteVtex(CARREFOUR, http, config).buscar(contexto("smart tv 55"))
        assert sim.call_count == 2

    async def teste_variantes_de_mesmo_preco_se_juntam(self, simulador, http, config):
        dados = gravacao_json("vtex_busca_inteligente_carrefour.json")
        produto = dados["products"][0]
        variante = json.loads(json.dumps(produto["items"][0]))
        variante["itemId"] = "999"
        variante["nameComplete"] = produto["items"][0]["nameComplete"] + " 220V"
        produto["items"].append(variante)
        dados["products"] = [produto]
        simulador.get(URL_IS).mock(resposta_json(dados))
        simulador.post(URL_SIMULACAO).mock(httpx.Response(500))
        ofertas = await FonteVtex(CARREFOUR, http, config).buscar(contexto("tv"))
        assert len(ofertas) == 1


def teste_frete_nao_informado_padrao():
    assert Frete.desconhecido().status is StatusFrete.NAO_INFORMADO


def teste_cotacao_leva_seu_comprovante():
    oferta = oferta_vazia()
    aplicar_simulacao(oferta, gravacao_json("vtex_simulacao_bh.json"), tem_cep=True)
    f = oferta.frete
    assert f.modalidade == "Expressa"
    assert f.transportadora and "Expressa" in f.transportadora
    assert f.entrega_ate == "2026-10-22"
    assert f.cotado_em and f.cotado_em.endswith("+00:00")
    retiradas = [o for o in f.opcoes if o.tipo == "retirada"]
    assert retiradas and all(o.distancia_km is not None for o in retiradas)
    assert all(o.distancia_km is None for o in f.opcoes if o.tipo == "entrega")


def teste_preco_do_checkout_longe_do_catalogo_gera_alerta():
    oferta = oferta_vazia()
    oferta.preco = 100000
    aplicar_simulacao(oferta, gravacao_json("vtex_simulacao_bh.json"), tem_cep=True)
    assert "preco_mudou_no_checkout" in oferta.alertas
    oferta = oferta_vazia()
    oferta.preco = 299000
    aplicar_simulacao(oferta, gravacao_json("vtex_simulacao_bh.json"), tem_cep=True)
    assert oferta.alertas == []


async def teste_previa_publicada_antes_das_cotacoes(simulador, http, config):
    simulador.get(URL_IS).mock(
        resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
    )
    simulador.post(URL_SIMULACAO).mock(resposta_json(gravacao_json("vtex_simulacao_bh.json")))
    vistos = []

    def previa(ofertas):
        vistos.append([(o.id, o.frete.status) for o in ofertas])

    ofertas = await FonteVtex(CARREFOUR, http, config).buscar(contexto("smart tv 55"), previa)
    assert len(vistos) == 1
    estados = {s for _, s in vistos[0]}
    assert "calculando" in estados
    assert all(o.frete.status != "calculando" for o in ofertas)


async def teste_cotacoes_divididas_entre_buscas(simulador, http, config):
    from app.cache import CacheComValidade

    simulador.get(URL_IS).mock(
        resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
    )
    cotada: list[str] = []

    def simular(requisicao: httpx.Request):
        cotada.append(json.loads(requisicao.content)["items"][0]["id"])
        return resposta_json(gravacao_json("vtex_simulacao_bh.json"))

    simulador.post(URL_SIMULACAO).mock(side_effect=simular)
    cotacoes = CacheComValidade(600, 1000)
    primeira = await FonteVtex(CARREFOUR, http, config, cotacoes).buscar(contexto("smart tv 55"))
    apos_primeira = list(cotada)
    de_novo = await FonteVtex(CARREFOUR, http, config, cotacoes).buscar(contexto("tv 55"))
    assert not set(cotada[len(apos_primeira) :]) & set(apos_primeira)
    carimbos = {o.id: o.frete.cotado_em for o in primeira if o.frete.cotado_em}
    for o in de_novo:
        if o.id in carimbos:
            assert o.frete.cotado_em == carimbos[o.id]

    antes = len(cotada)
    await FonteVtex(CARREFOUR, http, config, cotacoes).buscar(contexto("smart tv 55", "01310100"))
    assert len(cotada) > antes


def teste_imposto_do_destino_faz_parte_do_preco():
    dados = gravacao_json("vtex_simulacao_bh.json")
    dados["totals"].append({"id": "Tax", "name": "Total da Taxa", "value": 17994})
    for opcao in dados["paymentData"]["installmentOptions"]:
        for parcela in opcao["installments"]:
            parcela["total"] += 17994 if opcao["paymentName"] != "Pix" else 0
    oferta = oferta_vazia()
    aplicar_simulacao(oferta, dados, tem_cep=True)
    assert oferta.preco == 299900 + 17994

    dados["paymentData"]["installmentOptions"] = []
    oferta = oferta_vazia()
    aplicar_simulacao(oferta, dados, tem_cep=True)
    assert oferta.preco == 299900 + 17994


def _com_imposto(dados, imposto):
    dados = json.loads(json.dumps(dados))
    dados["totals"].append({"id": "Tax", "name": "Total da Taxa", "value": imposto})
    for opcao in dados["paymentData"]["installmentOptions"]:
        for parcela in opcao["installments"]:
            parcela["total"] += imposto
    return dados


async def teste_checkout_instavel_mostra_o_maior_valor(simulador, http, config):
    simples = gravacao_json("vtex_simulacao_bh.json")
    com_imposto = _com_imposto(simples, 20000)
    respostas = iter([simples, com_imposto] * 100)
    simulador.get(URL_IS).mock(
        resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
    )
    simulador.post(URL_SIMULACAO).mock(side_effect=lambda _: resposta_json(next(respostas)))
    loja = LojaVtex("carrefour", "Carrefour", "www.carrefour.com.br", "is", instavel=True)
    ofertas = await FonteVtex(loja, http, config).buscar(contexto("smart tv 55"))
    cotada = [o for o in ofertas if o.frete.status == "calculado"]
    assert cotada
    for o in cotada:
        assert "preco_instavel" in o.alertas
        assert o.total_exato is False
        assert o.preco == 299900 + 20000


async def teste_loja_instavel_nunca_e_exata_mesmo_com_respostas_iguais(simulador, http, config):
    simulador.get(URL_IS).mock(
        resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
    )
    simulador.post(URL_SIMULACAO).mock(resposta_json(gravacao_json("vtex_simulacao_bh.json")))
    loja = LojaVtex("carrefour", "Carrefour", "www.carrefour.com.br", "is", instavel=True)
    ofertas = await FonteVtex(loja, http, config).buscar(contexto("smart tv 55"))
    cotada = [o for o in ofertas if o.frete.status == "calculado"]
    assert cotada and not any(o.total_exato for o in cotada)


async def teste_auditoria_marca_loja_instavel_na_primeira_divergencia(simulador, http, config):
    config.taxa_auditoria_cotacao = 1.0
    simples = gravacao_json("vtex_simulacao_bh.json")
    respostas = iter([simples, _com_imposto(simples, 500)] + [simples] * 500)
    simulador.get(URL_IS).mock(
        resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
    )
    simulador.post(URL_SIMULACAO).mock(side_effect=lambda _: resposta_json(next(respostas)))
    fonte = FonteVtex(CARREFOUR, http, config)
    await fonte.buscar(contexto("smart tv 55"))
    assert len(fonte._vendedores_instaveis) == 1
    assert fonte._instavel is False


async def teste_auditoria_estavel_mantem_o_selo_exato(simulador, http, config):
    config.taxa_auditoria_cotacao = 1.0
    simulador.get(URL_IS).mock(
        resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
    )
    sim = simulador.post(URL_SIMULACAO).mock(resposta_json(gravacao_json("vtex_simulacao_bh.json")))
    fonte = FonteVtex(CARREFOUR, http, config)
    ofertas = await fonte.buscar(contexto("smart tv 55"))
    cotada = [o for o in ofertas if o.frete.status == "calculado"]
    assert cotada and all(o.total_exato for o in cotada)
    assert sim.call_count == 2 * len(cotada)
    assert fonte._instavel is False


async def teste_primeiras_cotacoes_da_loja_sempre_auditadas(simulador, http, config):
    config.aquecimento_auditoria_cotacao = 3
    simulador.get(URL_IS).mock(
        resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
    )
    sim = simulador.post(URL_SIMULACAO).mock(resposta_json(gravacao_json("vtex_simulacao_bh.json")))
    ofertas = await FonteVtex(CARREFOUR, http, config).buscar(contexto("smart tv 55"))
    cotada = sum(o.frete.status == "calculado" for o in ofertas)
    assert cotada > 3
    assert sim.call_count == cotada + 3


def teste_cotacao_compacta_mantem_todos_os_valores_usados():
    from app.fontes.vtex import compactar

    bruto = gravacao_json("vtex_simulacao_bh.json")
    bruto["totals"].append({"id": "Tax", "name": "Total da Taxa", "value": 0})
    completa, pequeno = oferta_vazia(), oferta_vazia()
    aplicar_simulacao(completa, bruto, tem_cep=True, cotada_em=1)
    aplicar_simulacao(pequeno, compactar(bruto), tem_cep=True, cotada_em=1)
    assert completa == pequeno
    assert len(json.dumps(compactar(bruto))) < len(json.dumps(bruto)) / 2


async def teste_resposta_grande_demais_da_loja_e_recusada(simulador, config):
    from app.cliente_http import ClienteHttp, ErroExterno

    simulador.get("https://big.example/x").mock(httpx.Response(200, content=b"x" * 5000))
    async with ClienteHttp(config, bytes_maximo=1000) as http:
        with pytest.raises(ErroExterno, match="grande demais"):
            await http.requisitar("GET", "https://big.example/x")


async def teste_resposta_comprimida_da_loja_e_decodificada_uma_vez(simulador, config):
    import gzip

    from app.cliente_http import ClienteHttp

    corpo = gzip.compress(b'{"ok": true}')
    simulador.get("https://gz.example/x").mock(
        httpx.Response(200, content=corpo, headers={"content-encoding": "gzip"})
    )
    async with ClienteHttp(config) as http:
        assert await http.obter_json("https://gz.example/x") == {"ok": True}


@pytest.mark.parametrize(
    ("produto", "sku", "esperadas"),
    [
        (
            "Air Fryer Extream 4,3L 110V",
            "Air Fryer Extream 4,3L 110V",
            "Air Fryer Extream 4,3L 110V",
        ),
        ("Geladeira Brastemp 375L", "110V", "Geladeira Brastemp 375L 110V"),
        (
            "Geladeira Brastemp 375L",
            "Geladeira Brastemp 375L Inox 220V",
            "Geladeira Brastemp 375L Inox 220V",
        ),
        ("Camiseta Básica", "Branco P", "Camiseta Básica Branco P"),
        ("", "Produto Sem Nome de Produto", "Produto Sem Nome de Produto"),
    ],
)
def teste_nome_do_sku_nao_se_repete(produto, sku, esperadas):
    from app.fontes.vtex import titulo_do_item

    assert titulo_do_item(produto, {"name": sku, "nameComplete": f"{produto} {sku}"}) == esperadas


async def teste_resultados_de_loja_de_brinquedo_ficam_abaixo_do_piso(simulador, http, config):
    loja = LojaVtex("rihappy", "Ri Happy", "www.carrefour.com.br", "is", segmento="brinquedos")
    simulador.get(URL_IS).mock(
        resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
    )
    simulador.post(URL_SIMULACAO).mock(httpx.Response(500))
    brinquedos = await FonteVtex(loja, http, config).buscar(contexto("smart tv 55"))
    comum = await FonteVtex(CARREFOUR, http, config).buscar(contexto("smart tv 55"))
    assert max(o.relevancia for o in brinquedos) <= 60 < max(o.relevancia for o in comum)


def teste_lojas_de_brinquedo_marcadas_no_cadastro():
    por_id = {s.id: s for s in carregar_lojas()}
    assert por_id["rihappy"].segmento == por_id["pbkids"].segmento == "brinquedos"
    assert por_id["carrefour"].segmento == "geral"


def _sem_entrega(dados):
    dados = json.loads(json.dumps(dados))
    dados["logisticsInfo"] = []
    dados["paymentData"]["installmentOptions"] = []
    return dados


async def teste_resposta_incompleta_da_auditoria_nao_marca_instabilidade(simulador, http, config):
    config.taxa_auditoria_cotacao = 1.0
    completa = gravacao_json("vtex_simulacao_bh.json")
    respostas = iter([_sem_entrega(completa), completa] * 100)
    simulador.get(URL_IS).mock(
        resposta_json(gravacao_json("vtex_busca_inteligente_carrefour.json"))
    )
    simulador.post(URL_SIMULACAO).mock(side_effect=lambda _: resposta_json(next(respostas)))
    fonte = FonteVtex(CARREFOUR, http, config)
    ofertas = await fonte.buscar(contexto("smart tv 55"))
    cotada = [o for o in ofertas if o.frete.status == "calculado"]
    assert cotada and all(o.total_exato for o in cotada)
    assert all("preco_instavel" not in o.alertas for o in cotada)
    assert fonte._instavel is False


async def teste_vendedor_instavel_nao_tira_o_selo_dos_outros_vendedores(simulador, http, config):
    config.taxa_auditoria_cotacao = 1.0
    busca = json.loads(json.dumps(gravacao_json("vtex_busca_inteligente_carrefour.json")))
    busca["products"][0]["items"][0]["sellers"][0]["sellerId"] = "parceiro"
    simples = gravacao_json("vtex_simulacao_bh.json")
    alternadas = iter([simples, _com_imposto(simples, 500)] * 100)

    def simular(requisicao):
        vendedor = json.loads(requisicao.content)["items"][0]["seller"]
        return resposta_json(next(alternadas) if vendedor == "parceiro" else simples)

    simulador.get(URL_IS).mock(resposta_json(busca))
    simulador.post(URL_SIMULACAO).mock(side_effect=simular)
    fonte = FonteVtex(CARREFOUR, http, config)
    ofertas = await fonte.buscar(contexto("smart tv 55"))
    cotadas = [o for o in ofertas if o.frete.status == "calculado"]
    do_parceiro = [o for o in cotadas if o.id.endswith(":parceiro")]
    da_loja = [o for o in cotadas if not o.id.endswith(":parceiro")]
    assert do_parceiro and all("preco_instavel" in o.alertas for o in do_parceiro)
    assert da_loja and all(o.total_exato for o in da_loja)
    assert fonte._vendedores_instaveis == {"parceiro"}


async def teste_oferta_malformada_nao_derruba_a_loja(simulador, http, config):
    original = gravacao_json("vtex_busca_inteligente_carrefour.json")
    busca = json.loads(json.dumps(original))
    busca["products"][0]["items"][0]["sellers"][0]["commertialOffer"]["Price"] = "abc"
    busca["products"][1]["link"] = "http://www.carrefour.com.br/produto-x/p"
    simulador.post(URL_SIMULACAO).mock(resposta_json(gravacao_json("vtex_simulacao_bh.json")))
    rota = simulador.get(URL_IS).mock(resposta_json(original))
    completas = await FonteVtex(CARREFOUR, http, config).buscar(contexto("smart tv 55"))
    rota.mock(resposta_json(busca))
    ofertas = await FonteVtex(CARREFOUR, http, config).buscar(contexto("smart tv 55"))
    assert len(ofertas) == len(completas) - 1
    assert any(
        o.link.startswith("https://www.carrefour.com.br/produto-x/p?skuId=") for o in ofertas
    )
