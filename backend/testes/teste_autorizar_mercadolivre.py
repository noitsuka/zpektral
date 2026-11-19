import subprocess
import sys

import pytest

from scripts import autorizar_mercadolivre as script


@pytest.mark.parametrize("ambiente", ["preview", "production"])
def teste_envio_para_vercel_so_no_ambiente_pedido_e_sem_segredo_na_linha_de_comando(
    monkeypatch, ambiente
):
    chamadas = []

    def rodar(comando, **opcoes):
        chamadas.append((comando, opcoes))
        return subprocess.CompletedProcess(comando, 0, "", "")

    monkeypatch.setattr(script.shutil, "which", lambda _: "npx")
    monkeypatch.setattr(script.subprocess, "run", rodar)
    script.enviar_para_vercel(
        {"ML_TOKEN_RENOVACAO": "TG-segredo", "CHAVE_CREDENCIAIS": "k"}, ambiente
    )

    assert [c[0][5] for c in chamadas] == ["ML_TOKEN_RENOVACAO", "CHAVE_CREDENCIAIS"]
    for comando, _ in chamadas:
        assert comando[comando.index("--environment") + 1] == ambiente
        assert comando[comando.index("--project") + 1] == "zpektral-api"
        assert "--sensitive" in comando
        assert "TG-segredo" not in " ".join(comando)
    assert chamadas[0][1]["input"] == "TG-segredo"


def teste_recusa_da_vercel_para_sem_mostrar_o_valor(monkeypatch, capsys):
    monkeypatch.setattr(script.shutil, "which", lambda _: "npx")
    monkeypatch.setattr(
        script.subprocess,
        "run",
        lambda comando, **_: subprocess.CompletedProcess(comando, 1, "", "TG-segredo"),
    )
    with pytest.raises(SystemExit) as saida:
        script.enviar_para_vercel({"ML_TOKEN_RENOVACAO": "TG-segredo"}, "preview")
    assert "TG-segredo" not in str(saida.value) + capsys.readouterr().out


def teste_gravacao_que_falha_nao_deixa_temporario_com_segredo(tmp_path, monkeypatch):
    destino = tmp_path / ".env"

    def falhar(*_):
        raise PermissionError("arquivo aberto em outro programa")

    monkeypatch.setattr(script.os, "replace", falhar)
    with pytest.raises(PermissionError):
        script.gravar_privado(destino, "ML_SEGREDO_CLIENTE=segredo\n")
    assert list(tmp_path.iterdir()) == []


def _sem_rede(monkeypatch):
    def proibido(*_, **__):
        raise AssertionError("nada pode sair do computador")

    monkeypatch.setattr(script.httpx, "post", proibido)
    monkeypatch.setattr(script.subprocess, "run", proibido)
    monkeypatch.setattr(script.shutil, "which", lambda _: "npx")


def teste_vercel_sem_ambiente_nao_roda(monkeypatch):
    _sem_rede(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["autorizar_mercadolivre", "--vercel"])
    with pytest.raises(SystemExit):
        script.main()


@pytest.mark.parametrize("resposta", ["", "sim", "production"])
def teste_producao_sem_confirmacao_nao_pede_nem_envia_nada(monkeypatch, resposta):
    _sem_rede(monkeypatch)
    perguntas = []

    def responder(pergunta=""):
        perguntas.append(pergunta)
        return resposta

    monkeypatch.setattr("builtins.input", responder)
    monkeypatch.setattr(sys, "argv", ["autorizar_mercadolivre", "--vercel", "production"])
    with pytest.raises(SystemExit) as saida:
        script.main()
    assert "Nada foi" in str(saida.value)
    # a confirmação vem antes de pedir o App ID e o Client Secret
    assert len(perguntas) == 1 and "Production" in perguntas[0]


def teste_endereco_colado_sem_state_e_recusado(monkeypatch):
    _sem_rede(monkeypatch)
    respostas = iter(
        ["123", "https://exemplo.com.br/volta", "https://exemplo.com.br/volta?code=TG-x"]
    )
    monkeypatch.setattr("builtins.input", lambda *_: next(respostas))
    monkeypatch.setattr(script.getpass, "getpass", lambda *_: "segredo")
    monkeypatch.setattr(script, "ler_env", lambda: {})
    monkeypatch.setattr(sys, "argv", ["autorizar_mercadolivre"])
    with pytest.raises(SystemExit) as saida:
        script.main()
    assert "state" in str(saida.value)


def teste_token_com_quebra_de_linha_nao_entra_no_env(tmp_path, monkeypatch):
    destino = tmp_path / ".env"
    monkeypatch.setattr(script, "ARQUIVO_ENV", destino)
    with pytest.raises(SystemExit):
        script.gravar_env({"ML_TOKEN_RENOVACAO": "TG-1\nDATABASE_URL=postgresql://outro"})
    assert not destino.exists()
