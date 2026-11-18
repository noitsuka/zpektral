from datetime import UTC, datetime, timedelta, timezone

from app.modelos import Loja, Oferta, nomes_de_promocao, validade_informada

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
