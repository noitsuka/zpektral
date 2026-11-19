import subprocess

import pytest

from scripts import autorizar_mercadolivre as script


def teste_envio_para_vercel_so_em_producao_e_sem_segredo_na_linha_de_comando(monkeypatch):
    chamadas = []

    def rodar(comando, **opcoes):
        chamadas.append((comando, opcoes))
        return subprocess.CompletedProcess(comando, 0, "", "")

    monkeypatch.setattr(script.shutil, "which", lambda _: "npx")
    monkeypatch.setattr(script.subprocess, "run", rodar)
    script.enviar_para_vercel({"ML_TOKEN_RENOVACAO": "TG-segredo", "CHAVE_CREDENCIAIS": "k"})

    assert [c[0][5] for c in chamadas] == ["ML_TOKEN_RENOVACAO", "CHAVE_CREDENCIAIS"]
    for comando, _ in chamadas:
        assert comando[comando.index("--environment") + 1] == "production"
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
        script.enviar_para_vercel({"ML_TOKEN_RENOVACAO": "TG-segredo"})
    assert "TG-segredo" not in str(saida.value) + capsys.readouterr().out


def teste_gravacao_que_falha_nao_deixa_temporario_com_segredo(tmp_path, monkeypatch):
    destino = tmp_path / ".env"

    def falhar(*_):
        raise PermissionError("arquivo aberto em outro programa")

    monkeypatch.setattr(script.os, "replace", falhar)
    with pytest.raises(PermissionError):
        script.gravar_privado(destino, "ML_SEGREDO_CLIENTE=segredo\n")
    assert list(tmp_path.iterdir()) == []
