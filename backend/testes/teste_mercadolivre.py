import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text

from app.banco import Base, criar_motor, criar_sessoes, criar_tabelas_locais
from app.cliente_http import ErroExterno
from app.credenciais import Cifra, GuardaCredenciais, nova_chave
from app.fontes.mercadolivre import AutorizacaoRecusada, CofreTokens, FonteMercadoLivre
from app.modelos import Condicao, StatusFrete
from testes.conftest import contexto, resposta_json

URL_TOKEN = "https://api.mercadolibre.com/oauth/token"
CATALOGO = re.compile(r"https://api\.mercadolibre\.com/products/search\?.*")
ITENS = re.compile(r"https://api\.mercadolibre\.com/products/(MLB\d+)/items.*")
USUARIOS = re.compile(r"https://api\.mercadolibre\.com/users\?ids=.*")
FRETE_ML = re.compile(r"https://api\.mercadolibre\.com/items/(MLB\d+)/shipping_options.*")
URL_PG = os.environ.get("URL_BANCO_TESTE")

# formato de /products/search e /products/{id}/items na documentação do Mercado Livre
PRODUTOS = {
    "keywords": "rtx 4060",
    "paging": {"total": 2, "limit": 10, "offset": 0},
    "results": [
        {
            "id": "MLB100",
            "status": "active",
            "domain_id": "MLB-GRAPHICS_CARDS",
            "name": "Placa de Vídeo RTX 4060 8GB Gigabyte",
            "attributes": [
                {"id": "BRAND", "name": "Marca", "value_name": "Gigabyte"},
                {"id": "GTIN", "name": "Código universal", "value_name": "123,7891234567895"},
            ],
            "pictures": [{"id": "1", "url": "http://http2.mlstatic.com/D_1.jpg"}],
        },
        {"id": "MLB200", "status": "active", "name": "Capa de Chuva para Moto", "attributes": []},
    ],
}
ITENS_100 = {
    "paging": {"total": 4, "offset": 0, "limit": 100},
    "results": [
        {
            "item_id": "MLB1",
            "seller_id": 11,
            "price": 1899.9,
            "original_price": 2199,
            "currency_id": "BRL",
            "condition": "new",
            "official_store_id": None,
            "shipping": {"free_shipping": False, "mode": "me2"},
        },
        {
            "item_id": "MLB2",
            "seller_id": 22,
            "price": 1500,
            "original_price": None,
            "currency_id": "BRL",
            "condition": "used",
            "shipping": {"free_shipping": True, "mode": "me2"},
        },
        {"item_id": "MLB3", "seller_id": 33, "price": 2500, "condition": "new"},
        {"item_id": "MLB5", "seller_id": 55, "price": None, "condition": "new"},
    ],
}
USUARIOS_RESPOSTA = [
    {"code": 200, "body": {"id": 11, "nickname": "LOJA_X"}},
    {"code": 200, "body": {"id": 22, "nickname": "OUTRA"}},
    {"code": 404, "body": {"message": "not found"}},
]


def catalogo(simulador, itens=ITENS_100, usuarios=USUARIOS_RESPOSTA):
    simulador.get(CATALOGO).mock(resposta_json(PRODUTOS))
    rota_itens = simulador.get(ITENS).mock(resposta_json(itens))
    simulador.get(USUARIOS).mock(resposta_json(usuarios))
    return rota_itens


def _opcoes(*custos):
    return resposta_json(
        {"options": [{"name": f"Op{c}", "cost": c, "estimated_delivery_time": {}} for c in custos]}
    )


def configurado(config):
    config.ml_id_cliente = "id"
    config.ml_segredo_cliente = SecretStr("segredo-do-cliente")
    config.ml_token_renovacao = SecretStr("r1")
    return config


@pytest.fixture
async def guarda(tmp_path):
    motor = criar_motor(f"sqlite+aiosqlite:///{tmp_path / 'credenciais.db'}")
    async with motor.begin() as conexao:
        await conexao.run_sync(Base.metadata.create_all)
    yield GuardaCredenciais(criar_sessoes(motor), Cifra(nova_chave()))
    await motor.dispose()


def rota_token(simulador, tokens_renovacao: list[str]):
    chamadas = iter(range(100))

    def responder(requisicao: httpx.Request):
        formulario = parse_qs(requisicao.content.decode())
        tokens_renovacao.append(formulario["refresh_token"][0])
        n = next(chamadas)
        return resposta_json(
            {"access_token": f"a{n}", "refresh_token": f"r{n + 2}", "expires_in": 21600}
        )

    return simulador.post(URL_TOKEN).mock(side_effect=responder)


async def teste_desativada_sem_credenciais(http, config):
    assert FonteMercadoLivre(http, config).ativa is False


async def teste_renovacao_guarda_o_token_novo_para_a_proxima_instancia(
    simulador, http, config, guarda
):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    agora = [1000.0]
    cofre = CofreTokens(http, config, guarda, relogio=lambda: agora[0])

    assert await cofre.obter_token() == "a0"
    assert await cofre.obter_token() == "a0"
    assert (await guarda.ler(cofre.chave))["refresh_token"] == "r2"

    agora[0] += 21600
    assert await cofre.obter_token() == "a1"
    assert usados == ["r1", "r2"]

    reiniciada = CofreTokens(http, config, guarda, relogio=lambda: agora[0] + 30000)
    assert await reiniciada.obter_token() == "a2"
    assert usados == ["r1", "r2", "r3"]


async def teste_outra_instancia_usa_o_token_valido_sem_renovar(simulador, http, config, guarda):
    configurado(config)
    rota = rota_token(simulador, [])
    assert await CofreTokens(http, config, guarda).obter_token() == "a0"
    assert await CofreTokens(http, config, guarda).obter_token() == "a0"
    assert rota.call_count == 1


async def teste_token_recusado_pela_api_nao_volta_do_banco(simulador, http, config, guarda):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    assert await CofreTokens(http, config, guarda).obter_token() == "a0"
    outra = CofreTokens(http, config, guarda)
    outra.invalidar("a0")
    assert await outra.obter_token() == "a1"
    assert usados == ["r1", "r2"]


async def teste_novo_token_no_ambiente_vale_sobre_o_guardado(simulador, http, config, guarda):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    agora = [1000.0]
    await CofreTokens(http, config, guarda, relogio=lambda: agora[0]).obter_token()

    config.ml_token_renovacao = SecretStr("reautorizado")
    agora[0] += 60
    await CofreTokens(http, config, guarda, relogio=lambda: agora[0]).obter_token()
    assert usados == ["r1", "reautorizado"]


async def teste_autorizacao_revogada_pede_reautorizacao_sem_insistir(
    simulador, http, config, guarda
):
    configurado(config)
    rota = simulador.post(URL_TOKEN).mock(
        resposta_json({"error": "invalid_grant", "message": "invalid_grant"}, status=400)
    )
    cofre = CofreTokens(http, config, guarda)
    for _ in range(2):
        with pytest.raises(ErroExterno, match="autorize de novo") as erro:
            await cofre.obter_token()
        assert erro.value.bloqueio
    assert rota.call_count == 1


async def teste_credenciais_nao_vazam_em_log_nem_em_erro(simulador, http, config, guarda, caplog):
    configurado(config)
    config.ml_token_renovacao = SecretStr("TG-renovacao-secreta")
    simulador.post(URL_TOKEN).mock(httpx.Response(500, text="erro interno"))
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ErroExterno) as erro:
        await CofreTokens(http, config, guarda).obter_token()
    texto = caplog.text + str(erro.value) + repr(config)
    assert "TG-renovacao-secreta" not in texto
    assert "segredo-do-cliente" not in texto


async def teste_sem_banco_renova_e_gira_o_token_na_memoria(simulador, http, config):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    agora = [1000.0]
    cofre = CofreTokens(http, config, relogio=lambda: agora[0])
    await cofre.obter_token()
    agora[0] += 21600
    await cofre.obter_token()
    assert usados == ["r1", "r2"]


async def teste_busca_cancelada_no_meio_da_renovacao_ainda_guarda_o_token(
    simulador, http, config, guarda
):
    configurado(config)
    chamado, liberar = asyncio.Event(), asyncio.Event()

    async def responder(_):
        chamado.set()
        await liberar.wait()
        return resposta_json({"access_token": "a0", "refresh_token": "r2", "expires_in": 21600})

    simulador.post(URL_TOKEN).mock(side_effect=responder)
    cofre = CofreTokens(http, config, guarda)
    busca = asyncio.create_task(cofre.obter_token())
    await chamado.wait()
    busca.cancel()
    liberar.set()
    with pytest.raises(asyncio.CancelledError):
        await busca
    for _ in range(100):
        if await guarda.ler(cofre.chave):
            break
        await asyncio.sleep(0.01)
    assert (await guarda.ler(cofre.chave))["refresh_token"] == "r2"
    assert await cofre.obter_token() == "a0"


async def teste_gravacao_perdida_depois_da_renovacao_e_refeita(simulador, http, config, guarda):
    configurado(config)
    rota = rota_token(simulador, [])
    original = guarda.travar
    falhas = []

    @asynccontextmanager
    async def travar_e_cair_no_commit(chave):
        async with original(chave) as travada:
            yield travada
            if travada.novo is not None and not falhas:
                falhas.append(chave)
                raise OSError("a conexão caiu no commit")

    guarda.travar = travar_e_cair_no_commit
    cofre = CofreTokens(http, config, guarda)
    assert await cofre.obter_token() == "a0"
    assert falhas and rota.call_count == 1
    assert (await guarda.ler(cofre.chave))["refresh_token"] == "r2"


def banco_sem_gravar(guarda, *, depois_do_commit=False):
    """Faz o commit de quem grava falhar enquanto `caido[0]` for verdadeiro."""
    original = guarda.travar
    caido = [True]

    @asynccontextmanager
    async def travar(chave):
        async with original(chave) as travada:
            yield travada
            if travada.novo is not None and caido[0] and not depois_do_commit:
                raise OSError("a conexão caiu no commit")
        if travada.novo is not None and caido[0] and depois_do_commit:
            caido[0] = False
            raise OSError("o commit foi feito, mas a confirmação se perdeu")

    guarda.travar = travar
    return caido


async def teste_token_trocado_sem_gravar_fica_na_memoria_ate_o_banco_voltar(
    simulador, http, config, guarda
):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    agora = [1000.0]
    caido = banco_sem_gravar(guarda)
    cofre = CofreTokens(http, config, guarda, relogio=lambda: agora[0])

    assert await cofre.obter_token() == "a0"
    assert await cofre.obter_token() == "a0"
    assert await guarda.ler(cofre.chave) is None

    caido[0] = False
    assert await cofre.obter_token() == "a0"
    assert (await guarda.ler(cofre.chave))["refresh_token"] == "r2"

    agora[0] += 21600
    assert await cofre.obter_token() == "a1"
    # nunca o r1, que o Mercado Livre já tinha trocado
    assert usados == ["r1", "r2"]


async def teste_token_da_memoria_vale_sobre_o_antigo_do_banco(simulador, http, config, guarda):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    agora = [1000.0]
    caido = banco_sem_gravar(guarda)
    cofre = CofreTokens(http, config, guarda, relogio=lambda: agora[0])
    await cofre.obter_token()

    caido[0] = False
    agora[0] += 21600
    assert await cofre.obter_token() == "a1"
    assert usados == ["r1", "r2"]
    assert (await guarda.ler(cofre.chave))["refresh_token"] == "r3"


async def teste_confirmacao_perdida_do_commit_nao_regrava_por_cima(simulador, http, config, guarda):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    agora = [1000.0]
    banco_sem_gravar(guarda, depois_do_commit=True)
    cofre = CofreTokens(http, config, guarda, relogio=lambda: agora[0])
    assert await cofre.obter_token() == "a0"
    assert (await guarda.ler(cofre.chave))["refresh_token"] == "r2"

    agora[0] += 21600
    assert await cofre.obter_token() == "a1"
    assert usados == ["r1", "r2"]


async def teste_renovacao_espera_a_resposta_mais_que_as_lojas(simulador, http, config, guarda):
    configurado(config)
    prazos = []

    def responder(requisicao: httpx.Request):
        prazos.append(requisicao.extensions["timeout"]["read"])
        return resposta_json({"access_token": "a0", "refresh_token": "r2", "expires_in": 21600})

    simulador.post(URL_TOKEN).mock(side_effect=responder)
    await CofreTokens(http, config, guarda).obter_token()
    # a resposta perdida depois da troca queima o token; a trava do banco cai aos 30 s
    assert config.segundos_limite_leitura < prazos[0] < 30


@pytest.mark.skipif(not URL_PG, reason="a queda da conexão e a trava são do PostgreSQL")
async def teste_conexao_do_banco_derrubada_no_meio_da_renovacao(simulador, http, config):
    configurado(config)
    motores = [criar_motor(URL_PG) for _ in range(3)]
    async with motores[0].begin() as conexao:
        await conexao.run_sync(Base.metadata.drop_all)
        await conexao.run_sync(Base.metadata.create_all)
    chave = nova_chave()
    guarda_a, guarda_b = (GuardaCredenciais(criar_sessoes(m), Cifra(chave)) for m in motores[:2])
    a, b = CofreTokens(http, config, guarda_a), CofreTokens(http, config, guarda_b)
    validos, usados = {"r1"}, []
    trocado, liberar = asyncio.Event(), asyncio.Event()

    async def mercado_livre(requisicao: httpx.Request):
        # como o Mercado Livre: o token vale uma vez e já foi trocado quando a resposta sai
        renovacao = parse_qs(requisicao.content.decode())["refresh_token"][0]
        usados.append(renovacao)
        if renovacao not in validos:
            return resposta_json({"error": "invalid_grant"}, 400)
        validos.discard(renovacao)
        n = len(usados)
        validos.add(f"r{n + 1}")
        if n == 1:
            trocado.set()
            await liberar.wait()
        return resposta_json(
            {"access_token": f"a{n}", "refresh_token": f"r{n + 1}", "expires_in": 21600}
        )

    simulador.post(URL_TOKEN).mock(side_effect=mercado_livre)
    try:
        primeira = asyncio.create_task(a.obter_token())
        await trocado.wait()
        async with motores[2].connect() as conexao:
            derrubadas = await conexao.scalar(
                text(
                    "select count(pg_terminate_backend(pid)) from pg_stat_activity "
                    "where datname = current_database() and state = 'idle in transaction'"
                )
            )
        assert derrubadas == 1
        # sem a trava, outra instância apresenta o token que acabou de ser trocado
        with pytest.raises(AutorizacaoRecusada):
            await b.obter_token()
        liberar.set()
        assert await primeira == "a1"
        assert (await guarda_a.ler(a.chave))["refresh_token"] == "r2"
        # na busca seguinte, a outra instância acha no banco o token que a primeira gravou
        assert await b.obter_token() == "a1"
        assert usados == ["r1", "r1"]
    finally:
        async with motores[0].begin() as conexao:
            await conexao.run_sync(Base.metadata.drop_all)
        for motor in motores:
            await motor.dispose()


async def teste_registro_que_nao_abre_pede_reautorizacao_sem_apresentar_a_semente(
    simulador, http, config, guarda
):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    await CofreTokens(http, config, guarda).obter_token()
    # a CHAVE_CREDENCIAIS trocou: a linha existe, mas não abre
    outra_chave = GuardaCredenciais(guarda._sessoes, Cifra(nova_chave()))
    with pytest.raises(AutorizacaoRecusada):
        await CofreTokens(http, config, outra_chave).obter_token()
    assert usados == ["r1"]


async def teste_renovacao_nao_segue_redirecionamento(simulador, http, config, guarda):
    configurado(config)
    simulador.post(URL_TOKEN).mock(
        httpx.Response(307, headers={"location": "https://coletor.example/t"})
    )
    coletor = simulador.post("https://coletor.example/t").mock(resposta_json({}))
    with pytest.raises(ErroExterno):
        await CofreTokens(http, config, guarda).obter_token()
    assert not coletor.called


async def teste_na_vercel_so_ativa_com_o_cofre_no_postgres(http, config, tmp_path):
    from app.main import guarda_de_credenciais

    configurado(config)
    config.vercel = True
    config.chave_credenciais = SecretStr(nova_chave())
    assert FonteMercadoLivre(http, config).ativa is False
    # o SQLite de /tmp é de cada instância: a segunda apresentaria a semente já trocada
    motor = criar_motor(f"sqlite+aiosqlite:///{tmp_path / 'local.db'}")
    try:
        assert guarda_de_credenciais(config, criar_sessoes(motor)) is None
    finally:
        await motor.dispose()


async def teste_falha_passageira_nao_reapresenta_token_antigo(simulador, http, config, guarda):
    configurado(config)
    agora = [1000.0]
    usados: list[str] = []

    def responder(requisicao: httpx.Request):
        renovacao = parse_qs(requisicao.content.decode())["refresh_token"][0]
        usados.append(renovacao)
        if renovacao == "r3":
            raise httpx.ReadTimeout("devagar")
        n = len(usados)
        return resposta_json(
            {"access_token": f"a{n}", "refresh_token": f"r{n + 1}", "expires_in": 21600}
        )

    simulador.post(URL_TOKEN).mock(side_effect=responder)
    a = CofreTokens(http, config, guarda, relogio=lambda: agora[0])
    b = CofreTokens(http, config, guarda, relogio=lambda: agora[0])
    await a.obter_token()
    await b.obter_token()
    agora[0] += 21600
    await a.obter_token()
    agora[0] += 21600
    with pytest.raises(ErroExterno) as erro:
        await b.obter_token()
    assert "autorize de novo" not in str(erro.value)
    assert usados == ["r1", "r2", "r3"]


async def teste_cada_autorizacao_tem_a_propria_linha(simulador, http, config, guarda):
    configurado(config)
    rota_token(simulador, [])
    antiga = CofreTokens(http, config, guarda)
    await antiga.obter_token()
    config.ml_token_renovacao = SecretStr("reautorizado")
    nova = CofreTokens(http, config, guarda)
    await nova.obter_token()
    assert nova.chave != antiga.chave
    assert (await guarda.ler(antiga.chave))["refresh_token"] == "r2"
    assert (await guarda.ler(nova.chave))["refresh_token"] == "r3"


async def teste_com_banco_e_sem_cofre_a_fonte_fica_desativada(http, config):
    configurado(config)
    config.url_banco = "postgresql://usuario@banco/zpektral"
    assert FonteMercadoLivre(http, config).ativa is False


async def teste_requisicoes_simultaneas_renovam_uma_vez(simulador, http, config, guarda):
    configurado(config)
    rota = rota_token(simulador, [])
    loja = CofreTokens(http, config, guarda)
    emitidos = await asyncio.gather(*(loja.obter_token() for _ in range(10)))
    assert set(emitidos) == {"a0"}
    assert rota.call_count == 1


async def teste_busca_pelo_catalogo_com_frete_cotado(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    rota_itens = catalogo(simulador)

    def frete(requisicao: httpx.Request):
        assert requisicao.headers["authorization"] == "Bearer a0"
        assert "zip_code=30130010" in str(requisicao.url)
        return _opcoes(25.9, 39.9)

    simulador.get(FRETE_ML).mock(side_effect=frete)
    ofertas = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))

    pedido = simulador.calls[1].request
    assert pedido.headers["authorization"] == "Bearer a0"
    assert "site_id=MLB" in str(pedido.url) and "status=active" in str(pedido.url)
    # a capa de chuva não casa com a busca: não gasta a chamada das ofertas
    assert [c.request.url.path for c in rota_itens.calls] == ["/products/MLB100/items"]
    por_id = {o.id: o for o in ofertas}
    assert set(por_id) == {"mercadolivre:MLB1", "mercadolivre:MLB2", "mercadolivre:MLB3"}

    novo = por_id["mercadolivre:MLB1"]
    assert novo.titulo == "Placa de Vídeo RTX 4060 8GB Gigabyte"
    assert novo.preco == 189990 and novo.preco_original == 219900
    assert novo.marca == "Gigabyte" and novo.ean == "7891234567895"
    assert novo.link == "https://produto.mercadolivre.com.br/MLB-1-_JM"
    assert novo.imagem == "https://http2.mlstatic.com/D_1.jpg"
    assert novo.vendedor == "LOJA_X"
    assert novo.frete.status is StatusFrete.CALCULADO and novo.frete.valor == 2590
    assert novo.total == 189990 + 2590 and novo.total_exato

    usado = por_id["mercadolivre:MLB2"]
    assert usado.titulo.endswith("(usado)") and usado.condicao is Condicao.USADO
    assert usado.vendedor == "OUTRA"
    assert por_id["mercadolivre:MLB3"].vendedor is None


async def teste_busca_pelo_ean_acha_o_produto_do_catalogo(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    rota_itens = catalogo(simulador)
    simulador.get(FRETE_ML).mock(_opcoes(25.9))
    ofertas = await FonteMercadoLivre(http, config).buscar(contexto("7891234567895"))
    assert [c.request.url.path for c in rota_itens.calls] == ["/products/MLB100/items"]
    assert ofertas and all(o.relevancia == 100 for o in ofertas)


async def teste_item_repetido_em_dois_produtos_entra_e_e_cotado_uma_vez(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    simulador.get(CATALOGO).mock(
        resposta_json(
            {"results": [PRODUTOS["results"][0], {**PRODUTOS["results"][0], "id": "MLB300"}]}
        )
    )
    simulador.get(ITENS).mock(resposta_json({"results": [ITENS_100["results"][0]]}))
    simulador.get(USUARIOS).mock(resposta_json([]))
    rota_frete = simulador.get(FRETE_ML).mock(_opcoes(25.9))
    ofertas = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert [o.id for o in ofertas] == ["mercadolivre:MLB1"]
    assert rota_frete.call_count == 1


async def teste_item_com_id_fora_do_padrao_ou_condicao_desconhecida_fica_de_fora(
    simulador, http, config
):
    configurado(config)
    rota_token(simulador, [])
    base = {"seller_id": 11, "price": 1000, "currency_id": "BRL"}
    itens = {
        "results": [
            {**base, "item_id": "MLB7", "condition": "refurbished"},
            {**base, "item_id": "1234567", "condition": "new"},
            {**base, "item_id": "MLBU999", "condition": "new"},
            {**base, "item_id": "MLB8", "condition": "not_specified"},
        ]
    }
    catalogo(simulador, itens=itens)
    simulador.get(FRETE_ML).mock(_opcoes(25.9))
    ofertas = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert [(o.id, o.condicao) for o in ofertas] == [("mercadolivre:MLB7", Condicao.RECONDICIONADO)]
    assert ofertas[0].link == "https://produto.mercadolivre.com.br/MLB-7-_JM"


async def teste_cotacao_que_falha_mantem_o_frete_gratis_anunciado(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    catalogo(simulador)
    simulador.get(FRETE_ML).mock(httpx.Response(500))
    ofertas = await FonteMercadoLivre(http, config).buscar(
        contexto("rtx 4060"), previa=lambda _: None
    )
    por_id = {o.id: o for o in ofertas}
    assert por_id["mercadolivre:MLB2"].frete.status is StatusFrete.GRATIS_ANUNCIADO
    assert por_id["mercadolivre:MLB1"].frete.status is StatusFrete.NAO_INFORMADO


async def teste_produto_que_falha_fica_no_log(simulador, http, config, caplog):
    configurado(config)
    rota_token(simulador, [])
    simulador.get(CATALOGO).mock(
        resposta_json(
            {"results": [PRODUTOS["results"][0], {**PRODUTOS["results"][0], "id": "MLB300"}]}
        )
    )
    simulador.get(re.compile(r".*/products/MLB100/items.*")).mock(resposta_json(ITENS_100))
    simulador.get(re.compile(r".*/products/MLB300/items.*")).mock(httpx.Response(500))
    simulador.get(USUARIOS).mock(resposta_json([]))
    simulador.get(FRETE_ML).mock(_opcoes(25.9))
    with caplog.at_level(logging.WARNING, logger="zpektral.mercadolivre"):
        ofertas = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert ofertas
    assert "1 de 2 produtos" in caplog.text


async def teste_cada_produto_traz_as_ofertas_novas_mais_baratas(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    itens = {
        "results": [
            *({"item_id": f"MLB{n}", "price": 100 - n, "condition": "new"} for n in range(9)),
            {"item_id": "MLB99", "price": 1, "condition": "used"},
            {"item_id": "MLB98", "price": True, "condition": "new"},
        ]
    }
    catalogo(simulador, itens=itens)
    ofertas = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060", cep=None))
    assert [o.id for o in ofertas] == [
        "mercadolivre:MLB8",
        "mercadolivre:MLB7",
        "mercadolivre:MLB6",
    ]


async def teste_produto_sem_ofertas_nao_derruba_a_busca(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    outro = {**PRODUTOS["results"][0], "id": "MLB300"}
    simulador.get(CATALOGO).mock(resposta_json({"results": [PRODUTOS["results"][0], outro]}))

    def itens(requisicao: httpx.Request):
        if "MLB300" in requisicao.url.path:
            return httpx.Response(404)
        return resposta_json(ITENS_100)

    simulador.get(ITENS).mock(side_effect=itens)
    simulador.get(USUARIOS).mock(httpx.Response(500))
    ofertas = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060", cep=None))
    assert len(ofertas) == 3
    assert all(o.vendedor is None for o in ofertas)


async def teste_ofertas_todas_recusadas_viram_bloqueio(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    simulador.get(CATALOGO).mock(resposta_json(PRODUTOS))
    simulador.get(ITENS).mock(httpx.Response(429))
    with pytest.raises(ErroExterno) as erro:
        await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060", cep=None))
    assert erro.value.bloqueio


async def teste_sem_opcoes_significa_sem_entrega(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    catalogo(simulador, itens={"results": ITENS_100["results"][:1]})
    simulador.get(FRETE_ML).mock(resposta_json({"options": []}))
    [oferta] = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert oferta.frete.status is StatusFrete.NAO_ENTREGA


async def teste_cotacao_falha_mantem_oferta(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    catalogo(simulador, itens={"results": ITENS_100["results"][:1]})
    simulador.get(FRETE_ML).mock(httpx.Response(500))
    [oferta] = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert oferta.frete.status is StatusFrete.NAO_INFORMADO
    assert oferta.preco == 189990


async def teste_token_revogado_e_renovado_uma_vez(simulador, http, config):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    respostas = iter([httpx.Response(401), resposta_json(PRODUTOS)])
    busca = simulador.get(CATALOGO).mock(side_effect=lambda _: next(respostas))
    simulador.get(ITENS).mock(resposta_json(ITENS_100))
    simulador.get(USUARIOS).mock(resposta_json(USUARIOS_RESPOSTA))
    ofertas = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060", cep=None))
    assert ofertas
    assert busca.call_count == 2
    assert busca.calls[-1].request.headers["authorization"] == "Bearer a1"


async def teste_resposta_de_token_sem_access_token_vira_erro_externo(simulador, http, config):
    configurado(config)
    simulador.post(URL_TOKEN).mock(resposta_json({"error": "invalid_grant"}))
    with pytest.raises(ErroExterno):
        await CofreTokens(http, config).obter_token()


def teste_data_de_entrega_sem_fuso_vira_prazo():
    from app.fontes.mercadolivre import _opcao

    opcao = _opcao({"cost": 10, "estimated_delivery_time": {"date": "2999-01-01T00:00:00"}})
    assert opcao.prazo_dias is not None and opcao.prazo_dias > 0


async def teste_token_expirado_no_meio_da_cotacao_e_renovado(simulador, http, config):
    configurado(config)
    usados: list[str] = []
    rota_token(simulador, usados)
    catalogo(simulador, itens={"results": ITENS_100["results"][:1]})

    def frete(requisicao: httpx.Request):
        if requisicao.headers["authorization"] == "Bearer a0":
            return httpx.Response(401)
        return resposta_json(
            {
                "options": [
                    {
                        "name": "Normal",
                        "cost": 0,
                        "estimated_delivery_time": {"date": "2099-01-05T00:00:00"},
                    }
                ]
            }
        )

    rota_frete = simulador.get(FRETE_ML).mock(side_effect=frete)
    [oferta] = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert rota_frete.call_count == 2
    assert usados == ["r1", "r2"]
    assert oferta.frete.status is StatusFrete.CALCULADO
    assert oferta.frete.valor == 0
    assert oferta.frete.prazo_dias and oferta.frete.prazo_dias > 0
    assert oferta.total_exato


@pytest.mark.parametrize("status", [403, 429])
async def teste_catalogo_recusado_vira_bloqueio_e_explica_o_motivo(simulador, http, config, status):
    configurado(config)
    rota_token(simulador, [])
    simulador.get(CATALOGO).mock(
        resposta_json({"blocked_by": "PolicyAgent", "status": status}, status=status)
    )
    with pytest.raises(ErroExterno) as erro:
        await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060"))
    assert erro.value.bloqueio
    if status == 403:
        assert "Publicação e sincronização" in str(erro.value)


async def teste_frete_gratis_anunciado_sem_cep(simulador, http, config):
    configurado(config)
    rota_token(simulador, [])
    catalogo(simulador, itens={"results": ITENS_100["results"][1:2]})
    frete = simulador.get(FRETE_ML).mock(resposta_json({"options": []}))
    [oferta] = await FonteMercadoLivre(http, config).buscar(contexto("rtx 4060 usada", cep=None))
    assert not frete.called
    assert oferta.frete.status is StatusFrete.GRATIS_ANUNCIADO and oferta.frete.valor == 0


@pytest.mark.live
async def teste_ao_vivo_mercado_livre(http):
    from app.configuracao import Configuracoes
    from app.main import guarda_de_credenciais

    # lê o backend/.env e o banco local, como a API local: sem o cofre, a renovação gastaria
    # a autorização sem guardar o token novo
    config = Configuracoes()
    if not config.ml_token_renovacao.get_secret_value():
        pytest.skip("sem credenciais do Mercado Livre")
    motor = criar_motor(config.url_banco or f"sqlite+aiosqlite:///{config.arquivo_historico_local}")
    try:
        await criar_tabelas_locais(motor)
        guarda = guarda_de_credenciais(config, criar_sessoes(motor))
        if guarda is None:
            pytest.skip("sem CHAVE_CREDENCIAIS")
        fonte = FonteMercadoLivre(http, config, guarda)
        ofertas = await fonte.buscar(contexto("iphone 15", "01310100"))
    finally:
        await motor.dispose()
    assert ofertas
