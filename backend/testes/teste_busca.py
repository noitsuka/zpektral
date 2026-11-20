import asyncio

from app.busca import ServicoBusca, chave_cache
from app.cliente_http import ErroExterno
from app.modelos import Endereco, Frete, StatusFonte, StatusFrete
from app.saude import EstadoSaude
from testes.falsos import FonteFalsa

BH = Endereco("30130010", None, None, "Belo Horizonte", "MG")


def servico(config, *fontes):
    return ServicoBusca(list(fontes), config)


def status(trabalho):
    return {r.id: r.status for r in trabalho.relatorios}


class ComparadorFalso(FonteFalsa):
    """Guarda as ofertas das lojas que têm fonte direta, como o Buscapé."""

    def __init__(self, id: str, guardadas: dict[str, list[tuple]], **kw):
        super().__init__(id, [("Smart TV 55 do comparador", 900)], **kw)
        self._guardadas = guardadas

    async def buscar(self, ctx, previa=None):
        for loja, itens in self._guardadas.items():
            sem_cotacao = Frete(StatusFrete.NAO_INFORMADO)
            for oferta in FonteFalsa(f"{self.id}-{loja}", itens)._montar(ctx, sem_cotacao):
                ctx.reservar(self.id, loja, oferta)
        return await super().buscar(ctx, previa)


async def teste_loja_direta_que_falha_volta_pelo_comparador(config):
    svc = servico(
        config,
        FonteFalsa("lojax", erro=ErroExterno("loja: HTTP 403", status=403)),
        FonteFalsa("lojay", [("Smart TV 55 da Y", 1000)]),
        ComparadorFalso(
            "comparador",
            {"lojax": [("Smart TV 55 da X", 800)], "lojay": [("Smart TV 55 da Y", 990)]},
            atraso=0.05,
        ),
    )
    trabalho, _ = svc.iniciar("smart tv 55", BH)
    await asyncio.wait_for(trabalho.aguardar(), 1)
    ids = {o.id for o in trabalho.ofertas}
    # a X falhou: a oferta dela pelo comparador entra; a Y respondeu: a do comparador fica de fora
    assert "comparador-lojax:0" in ids
    assert "comparador-lojay:0" not in ids
    assert {"comparador:0", "lojay:0"} <= ids
    lote = trabalho.definitivo["comparador"]
    assert lote.relatorio.status is StatusFonte.OK
    assert lote.relatorio.ofertas == len(lote.ofertas) == 2


async def teste_comparador_que_termina_antes_manda_o_lote_de_novo_quando_a_loja_falha(config):
    svc = servico(
        config,
        FonteFalsa("lojax", erro=ErroExterno("loja: HTTP 503", status=503), atraso=0.05),
        ComparadorFalso("comparador", {"lojax": [("Smart TV 55 da X", 800)]}),
    )
    trabalho, _ = svc.iniciar("smart tv 55", BH)
    vistos = [
        (lote.relatorio.id, [o.id for o in lote.ofertas]) async for lote in trabalho.acompanhar()
    ]
    assert vistos[0] == ("comparador", ["comparador:0"])
    assert vistos[-1] == ("comparador", ["comparador:0", "comparador-lojax:0"])


async def teste_comparador_que_falha_nao_solta_o_que_guardou(config):
    svc = servico(
        config,
        FonteFalsa("lojax", erro=ErroExterno("loja: HTTP 403", status=403)),
        ComparadorFalso(
            "comparador", {"lojax": [("Smart TV 55 da X", 800)]}, erro=ErroExterno("fora")
        ),
    )
    trabalho, _ = svc.iniciar("smart tv 55", BH)
    await asyncio.wait_for(trabalho.aguardar(), 1)
    assert trabalho.ofertas == []


async def teste_executa_toda_fonte_e_relata_cada_uma(config):
    config.segundos_limite_fonte = 0.2
    svc = servico(
        config,
        FonteFalsa("ok", [("Smart TV 55", 100)]),
        FonteFalsa("broken", erro=ErroExterno("x")),
        FonteFalsa("crash", erro=KeyError("price")),
        FonteFalsa("slow", [("Smart TV 55", 1)], atraso=5),
        FonteFalsa("off", ativa=False),
    )
    trabalho, em_cache = svc.iniciar("smart tv 55", BH)
    assert em_cache is False
    await asyncio.wait_for(trabalho.aguardar(), 1)

    assert status(trabalho) == {
        "ok": StatusFonte.OK,
        "broken": StatusFonte.ERRO,
        "crash": StatusFonte.ERRO,
        "slow": StatusFonte.TEMPO_ESGOTADO,
        "off": StatusFonte.DESATIVADA,
    }
    assert [o.id for o in trabalho.ofertas] == ["ok:0"]
    mensagens = {r.id: r.mensagem for r in trabalho.relatorios}
    assert "price" not in (mensagens["crash"] or "")


async def teste_recusa_de_acesso_vira_fonte_bloqueada(config):
    svc = servico(
        config,
        FonteFalsa("proibida", erro=ErroExterno("loja: HTTP 403", status=403)),
        FonteFalsa("limitada", erro=ErroExterno("loja: HTTP 429", status=429)),
        FonteFalsa("antirrobo", erro=ErroExterno("verificação de robô", bloqueio=True)),
        FonteFalsa("fora", erro=ErroExterno("loja: HTTP 503", status=503)),
    )
    trabalho, _ = svc.iniciar("tv", BH)
    await asyncio.wait_for(trabalho.aguardar(), 1)
    assert status(trabalho) == {
        "proibida": StatusFonte.BLOQUEADA,
        "limitada": StatusFonte.BLOQUEADA,
        "antirrobo": StatusFonte.BLOQUEADA,
        "fora": StatusFonte.ERRO,
    }
    assert svc.saude.retrato()["proibida"].estado is EstadoSaude.BLOQUEADA


async def teste_fontes_rodam_em_paralelo(config):
    fontes = [FonteFalsa(f"s{i}", [("tv", 1)], atraso=0.2) for i in range(20)]
    trabalho, _ = servico(config, *fontes).iniciar("tv", None)
    laco = asyncio.get_running_loop()
    inicio = laco.time()
    await trabalho.aguardar()
    assert laco.time() - inicio < 0.5
    assert len(trabalho.ofertas) == 20


async def teste_buscas_iguais_simultaneas_dividem_uma_execucao(config):
    fonte = FonteFalsa("a", [("tv", 1)], atraso=0.05)
    svc = servico(config, fonte)
    trabalhos = [svc.iniciar("TV", BH)[0] for _ in range(10)]
    trabalhos += [svc.iniciar("  tv  ", BH)[0], svc.iniciar("tv", BH)[0]]
    await asyncio.gather(*(j.aguardar() for j in trabalhos))
    assert fonte.chamadas == 1
    assert len({id(j) for j in trabalhos}) == 1


async def teste_cep_faz_parte_da_chave(config):
    fonte = FonteFalsa("a", [("tv", 1)])
    svc = servico(config, fonte)
    a, _ = svc.iniciar("tv", BH)
    b, _ = svc.iniciar("tv", Endereco("69900000", None, None, None, None))
    c, _ = svc.iniciar("tv", None)
    await asyncio.gather(a.aguardar(), b.aguardar(), c.aguardar())
    assert fonte.chamadas == 3


def teste_chave_de_cache_ignora_acentos_caixa_e_espacos():
    assert chave_cache("  Fogão   5 Bocas ", None) == chave_cache("fogao 5 bocas", None)


async def teste_trabalho_em_cache_e_reaproveitado(config):
    fonte = FonteFalsa("a", [("tv", 1)])
    svc = servico(config, fonte)
    trabalho, _ = svc.iniciar("tv", None)
    await trabalho.aguardar()
    de_novo, em_cache = svc.iniciar("tv", None)
    assert em_cache is True and de_novo is trabalho and fonte.chamadas == 1


async def teste_trabalho_que_falhou_inteiro_expira_rapido(config):
    fonte = FonteFalsa("a", erro=ErroExterno("down"))
    svc = servico(config, fonte)
    trabalho, _ = svc.iniciar("tv", None)
    await trabalho.aguardar()
    chave = chave_cache("tv", None)
    expira, _ = svc._trabalhos._dados[chave]
    assert expira - asyncio.get_running_loop().time() < 20


def _validade(svc, consulta):
    expira, _ = svc._trabalhos._dados[chave_cache(consulta, None)]
    return expira - asyncio.get_running_loop().time()


async def teste_trabalho_com_metade_das_lojas_fora_expira_rapido(config):
    svc = servico(
        config,
        FonteFalsa("a", [("tv", 1)]),
        FonteFalsa("b", erro=ErroExterno("down")),
        FonteFalsa("c", erro=ErroExterno("down")),
        FonteFalsa("off", ativa=False),
    )
    trabalho, _ = svc.iniciar("tv", None)
    await trabalho.aguardar()
    assert _validade(svc, "tv") < 20


async def teste_trabalho_com_poucas_falhas_fica_no_cache(config):
    svc = servico(
        config,
        FonteFalsa("a", [("tv", 1)]),
        FonteFalsa("b", [("tv", 2)]),
        FonteFalsa("c", erro=ErroExterno("down")),
    )
    trabalho, _ = svc.iniciar("tv", None)
    await trabalho.aguardar()
    assert _validade(svc, "tv") > 200


async def teste_busca_termina_antes_do_historico_e_avisa_quando_gravou(config):
    ordem = []

    async def gravar(trabalho):
        await asyncio.sleep(0.05)
        ordem.append("gravou")

    svc = ServicoBusca([FonteFalsa("a", [("tv", 1)])], config, ao_concluir=gravar)
    trabalho, _ = svc.iniciar("tv", None)
    await trabalho.aguardar()
    ordem.append("terminou")
    await trabalho.gravado.wait()
    assert ordem == ["terminou", "gravou"]


async def teste_gravado_e_avisado_mesmo_sem_historico_ou_com_falha(config):
    async def falhar(trabalho):
        raise RuntimeError("banco fora")

    for ao_concluir in (None, falhar):
        svc = ServicoBusca([FonteFalsa("a", [("tv", 1)])], config, ao_concluir=ao_concluir)
        trabalho, _ = svc.iniciar("tv", None)
        await asyncio.wait_for(trabalho.gravado.wait(), 2)


async def teste_historico_lento_nao_segura_a_busca(config):
    async def gravar(trabalho):
        await asyncio.sleep(30)

    svc = ServicoBusca([FonteFalsa("a", [("tv", 1)])], config, ao_concluir=gravar)
    trabalho, _ = svc.iniciar("tv", None)
    assert await trabalho.aguardar(8)


async def teste_banco_acordando_nao_perde_o_historico(config):
    # o Neon dorme depois de 5 min parado; acordar, conectar e gravar passou de 5 s na produção
    gravou = asyncio.Event()

    async def gravar(trabalho):
        await asyncio.sleep(6)
        gravou.set()

    svc = ServicoBusca([FonteFalsa("a", [("tv", 1)])], config, ao_concluir=gravar)
    trabalho, _ = svc.iniciar("tv", None)
    assert await trabalho.aguardar(1)
    await trabalho.gravado.wait()
    assert gravou.is_set()


async def teste_acompanhar_repete_e_depois_transmite_ao_vivo(config):
    rapida = FonteFalsa("fast", [("tv", 1)])
    lenta = FonteFalsa("slow", [("tv", 2)], atraso=0.1)
    svc = servico(config, rapida, lenta)
    trabalho, _ = svc.iniciar("tv", None)
    await asyncio.sleep(0.02)

    cedo = [r.relatorio.id async for r in trabalho.acompanhar()]
    assert cedo == ["fast", "slow"]
    tarde = [r.relatorio.id async for r in trabalho.acompanhar()]
    assert tarde == cedo


async def teste_trabalho_sobrevive_a_requisicao_cancelada(config):
    fonte = FonteFalsa("a", [("tv", 1)], atraso=0.05)
    svc = servico(config, fonte)
    trabalho, _ = svc.iniciar("tv", None)
    esperador = asyncio.create_task(trabalho.aguardar())
    await asyncio.sleep(0)
    esperador.cancel()
    await asyncio.wait_for(trabalho.aguardar(), 1)
    assert len(trabalho.ofertas) == 1


async def teste_tempo_decorrido_e_registrado(config):
    trabalho, _ = servico(config, FonteFalsa("a", [("tv", 1)], atraso=0.05)).iniciar("tv", None)
    await trabalho.aguardar()
    assert trabalho.tempo_decorrido_ms >= 40


async def teste_previa_do_catalogo_vem_antes_do_lote_final(config):
    fonte = FonteFalsa("loja", [("tv", 100)], atraso=0.1, previa_apos=0.01)
    trabalho, _ = servico(config, fonte).iniciar("tv", BH)
    await asyncio.sleep(0.05)
    assert not trabalho.terminou
    assert [o.frete.status for o in trabalho.ofertas] == ["calculando"]
    assert trabalho.pendentes == ["loja"]
    await trabalho.aguardar()
    fases = [b.fase for b in trabalho.lotes]
    assert fases == ["catalogo", "final"]
    assert [o.frete.status for o in trabalho.ofertas] == ["calculado"]
    assert trabalho.pendentes == []


async def teste_aguardar_com_limite_volta_antes(config):
    trabalho, _ = servico(config, FonteFalsa("slow", [("tv", 1)], atraso=0.3)).iniciar("tv", None)
    assert await trabalho.aguardar(0.05) is False
    assert await trabalho.aguardar() is True


async def teste_saude_registrada_para_toda_fonte(config):
    svc = servico(config, FonteFalsa("a", [("tv", 1)]), FonteFalsa("b", erro=ErroExterno("x")))
    trabalho, _ = svc.iniciar("tv", None)
    await trabalho.aguardar()
    saude = svc.saude.retrato()
    assert saude["a"].estado == "saudavel" and saude["b"].falhas_seguidas == 1


def teste_sanear_descarta_anuncios_impossiveis():
    from app.busca import sanear
    from app.modelos import Frete, Loja, Oferta, StatusFrete

    def montar(id, preco=100, titulo="TV", link="https://x", frete=None):
        return Oferta(
            id=id,
            titulo=titulo,
            link=link,
            loja=Loja("s", "S"),
            preco=preco,
            frete=frete or Frete.desconhecido(),
        ).consolidar()

    ofertas = [
        montar("ok"),
        montar("ok"),
        montar("zero", preco=0),
        montar("negative", preco=-5),
        montar("absurd", preco=10**12),
        montar("untitled", titulo=""),
        montar("nolink", link=""),
        montar("badship", frete=Frete(StatusFrete.CALCULADO, valor=-100)),
    ]
    mantido = sanear(ofertas)
    assert [o.id for o in mantido] == ["ok", "badship"]
    assert mantido[1].frete.status == "nao_informado" and mantido[1].total == 100


def teste_sanear_limpa_o_que_chega_na_pagina():
    from app.busca import sanear
    from app.modelos import Loja, Oferta

    def montar(id, titulo="TV", link="https://loja.com/p", imagem="https://img.com/a.jpg"):
        return Oferta(
            id=id, titulo=titulo, link=link, imagem=imagem, loja=Loja("s", "S"), preco=100
        ).consolidar()

    ofertas = sanear(
        [
            montar("entities", titulo="Notebook 15.6&quot; <b>Promo</b>\u202e  x"),
            montar("js", link="javascript:alert(1)"),
            montar("http", link="http://loja.com/p"),
            montar("data_img", imagem="data:image/svg+xml,<svg onload=alert(1)>"),
            montar("long", titulo="A" * 5000),
        ]
    )
    por = {o.id: o for o in ofertas}
    assert por["entities"].titulo == 'Notebook 15.6" Promo x'
    assert "js" not in por and "http" not in por
    assert por["data_img"].imagem is None
    assert len(por["long"].titulo) == 300


async def teste_lote_final_do_mesmo_tamanho_reagrupa(config, monkeypatch):
    import app.busca as busca

    chamadas = []
    original = busca.atribuir_grupos
    monkeypatch.setattr(busca, "atribuir_grupos", lambda o: (chamadas.append(len(o)), original(o)))
    fonte = FonteFalsa("loja", [("tv", 100)], atraso=0.1, previa_apos=0.01)
    trabalho, _ = servico(config, fonte).iniciar("tv", BH)
    await asyncio.sleep(0.05)
    previa = trabalho.ofertas_agrupadas()
    await trabalho.aguardar()
    final = trabalho.ofertas_agrupadas()
    assert len(previa) == len(final) == 1
    assert final[0] is not previa[0]
    assert chamadas == [1, 1]


async def teste_trabalho_com_metade_das_lojas_bloqueadas_expira_rapido(config):
    svc = servico(
        config,
        FonteFalsa("a", [("tv", 1)]),
        FonteFalsa("b", erro=ErroExterno("recusou", 403)),
        FonteFalsa("c", erro=ErroExterno("recusou", 429)),
    )
    trabalho, _ = svc.iniciar("tv", None)
    await trabalho.aguardar()
    assert _validade(svc, "tv") < 20


async def teste_ofertas_dizem_que_termo_da_busca_faltou(config):
    import orjson

    fonte = FonteFalsa(
        "a", [("Geladeira Inox 220V", 100), ("Geladeira Inox 110V", 90)], previa_apos=0.01
    )
    trabalho, _ = servico(config, fonte).iniciar("geladeira inox 110v", None)
    await trabalho.aguardar()
    previa, final = trabalho.lotes
    assert [o.termos_ausentes for o in previa.ofertas] == [["110v"], []]
    assert [o.termos_ausentes for o in final.ofertas] == [["110v"], []]
    assert orjson.loads(orjson.dumps(final.ofertas[0]))["termos_ausentes"] == ["110v"]


def teste_sanear_tira_marca_que_nao_e_marca():
    from app.busca import sanear
    from app.modelos import Loja, Oferta

    def montar(id, marca):
        return Oferta(
            id=id,
            titulo="Air Fryer 4L",
            link="https://loja.com/p",
            loja=Loja("s", "S"),
            preco=100,
            marca=marca,
        ).consolidar()

    ofertas = sanear(
        [
            montar("a", "Não Disponível"),
            montar("b", "GENÉRICO"),
            montar("c", "Mondial"),
            montar("d", "Não Informado"),
            montar("e", "Diversos"),
        ]
    )
    assert [o.marca for o in ofertas] == [None, None, "Mondial", None, None]
