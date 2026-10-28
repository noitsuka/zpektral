import httpx
import orjson

from app.modelos import RelatorioFonte, StatusFonte
from app.saude import FALHAS_PARA_DEGRADAR, EstadoSaude, PainelSaude


def relatorio(status: StatusFonte, ms: int = 100) -> RelatorioFonte:
    return RelatorioFonte("loja", "Loja", status, ms, 0, None if status == "ok" else "falhou")


def teste_taxa_de_sucesso_e_latencia():
    painel = PainelSaude()
    for status in [StatusFonte.OK, StatusFonte.OK, StatusFonte.ERRO, StatusFonte.OK]:
        painel.registrar(relatorio(status, 200))
    h = painel.retrato()["loja"]
    assert h.estado is EstadoSaude.SAUDAVEL
    assert h.taxa_sucesso == 0.75
    assert h.tempo_medio_ms == 200


def teste_falhas_seguidas_degradam_e_sucesso_recupera():
    painel = PainelSaude()
    for _ in range(FALHAS_PARA_DEGRADAR - 1):
        painel.registrar(relatorio(StatusFonte.TEMPO_ESGOTADO))
    assert painel.retrato()["loja"].estado is not EstadoSaude.DEGRADADA
    painel.registrar(relatorio(StatusFonte.ERRO))
    h = painel.retrato()["loja"]
    assert h.estado is EstadoSaude.DEGRADADA and h.falhas_seguidas == FALHAS_PARA_DEGRADAR
    painel.registrar(relatorio(StatusFonte.OK))
    assert painel.retrato()["loja"].estado is EstadoSaude.SAUDAVEL


def teste_fontes_desativadas_aparecem_como_desativadas():
    painel = PainelSaude()
    painel.registrar(relatorio(StatusFonte.DESATIVADA))
    assert painel.retrato()["loja"].estado is EstadoSaude.DESATIVADA


def teste_retrato_serializa_sem_estado_interno():
    painel = PainelSaude()
    painel.registrar(relatorio(StatusFonte.OK))
    dados = orjson.loads(orjson.dumps(painel.retrato()["loja"]))
    assert set(dados) == {
        "id",
        "nome",
        "estado",
        "falhas_seguidas",
        "taxa_sucesso",
        "tempo_medio_ms",
        "ultimo_erro",
        "ultimo_sucesso",
    }


async def teste_webhook_dispara_na_queda_e_na_volta(simulador, http):
    gancho = simulador.post("https://hooks.example/zpektral").mock(httpx.Response(204))
    painel = PainelSaude(http, "https://hooks.example/zpektral")
    for _ in range(FALHAS_PARA_DEGRADAR + 2):
        painel.registrar(relatorio(StatusFonte.ERRO))
    painel.registrar(relatorio(StatusFonte.OK))
    for tarefa in list(painel._pendentes):
        await tarefa
    corpos = [orjson.loads(c.request.content)["content"] for c in gancho.calls]
    assert len(corpos) == 2
    assert "falhou" in corpos[0] and "voltou" in corpos[1]


async def teste_falha_do_webhook_e_absorvida(simulador, http):
    simulador.post("https://hooks.example/x").mock(httpx.Response(500))
    painel = PainelSaude(http, "https://hooks.example/x")
    for _ in range(FALHAS_PARA_DEGRADAR):
        painel.registrar(relatorio(StatusFonte.ERRO))
    for tarefa in list(painel._pendentes):
        await tarefa
