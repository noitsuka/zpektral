from datetime import UTC, datetime, timedelta, timezone

from app.modelos import (
    Alerta,
    Frete,
    Loja,
    Oferta,
    StatusFrete,
    nomes_de_promocao,
    validade_informada,
)

AGORA = datetime(2026, 11, 17, 22, 0, tzinfo=UTC)


def teste_nomes_de_promocao_saneados_curtos_e_sem_repeticao():
    nomes = nomes_de_promocao(
        [
            "  SUPEROFERTA\n",
            "<b>Black</b>\x00 Friday &amp; Cia",
            "superoferta",
            None,
            {"name": "x"},
            "",
            "A" * 200,
            "Quarta",
        ]
    )
    assert nomes == ["SUPEROFERTA", "Black Friday & Cia", "A" * 80]


def teste_validade_so_vale_nos_proximos_30_dias():
    perto = AGORA + timedelta(days=5)
    assert validade_informada(perto, AGORA) == "2026-11-22T22:00:00+00:00"
    assert validade_informada(AGORA + timedelta(days=30), AGORA) is not None
    assert validade_informada(AGORA + timedelta(days=30, seconds=1), AGORA) is None
    assert validade_informada(datetime(2100, 1, 1, 2, 59, 59, tzinfo=UTC), AGORA) is None
    assert validade_informada(AGORA - timedelta(minutes=1), AGORA) is None
    assert validade_informada(perto.replace(tzinfo=None), AGORA) is None


def teste_validade_sai_em_utc():
    brasilia = timezone(timedelta(hours=-3))
    data = datetime(2026, 11, 20, 23, 59, tzinfo=brasilia)
    assert validade_informada(data, AGORA) == "2026-11-21T02:59:00+00:00"


def teste_oferta_nasce_com_o_instante_da_leitura_em_utc():
    antes = datetime.now(UTC).replace(microsecond=0)
    oferta = Oferta(id="a:1", titulo="TV", link="https://a.example/1", loja=Loja("a", "A"), preco=1)
    lido = datetime.fromisoformat(oferta.consultado_em)
    assert lido.utcoffset() == timedelta(0)
    assert antes <= lido <= datetime.now(UTC)
    assert oferta.promocoes == [] and oferta.preco_valido_ate is None


def teste_nome_interno_de_regra_nao_vira_promocao():
    nomes = nomes_de_promocao(
        [
            "Plan Vendas > Frete Grátis - FG BR - NAL 29434",
            "regra_interna_pix",
            "Cupom | parceiro",
            "Black Friday 2026",
            "SUPEROFERTA",
        ]
    )
    assert nomes == ["Black Friday 2026", "SUPEROFERTA"]


def teste_preco_da_versao_mais_barata_nao_e_total_exato():
    frete = Frete(StatusFrete.CALCULADO, valor=1000)
    exata = Oferta("s:1", "Fone", "https://s.example/1", Loja("s", "S"), 9000, frete=frete)
    assert exata.consolidar().total_exato
    exata.alertar(Alerta.PRECO_VARIA_POR_VERSAO)
    assert not exata.consolidar().total_exato
