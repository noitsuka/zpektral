import argparse
import getpass
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

from app.credenciais import nova_chave

AUTORIZACAO = "https://auth.mercadolivre.com.br/authorization"
TOKEN = "https://api.mercadolibre.com/oauth/token"
RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_ENV = RAIZ / ".env"
VERCEL = "vercel@66.2.0"


def ler_env() -> dict[str, str]:
    if not ARQUIVO_ENV.exists():
        return {}
    valores = {}
    for linha in ARQUIVO_ENV.read_text("utf-8").splitlines():
        if "=" in linha and not linha.lstrip().startswith("#"):
            chave, valor = linha.split("=", 1)
            valores[chave.strip()] = valor.strip()
    return valores


def gravar_env(novos: dict[str, str]) -> None:
    linhas = ARQUIVO_ENV.read_text("utf-8").splitlines() if ARQUIVO_ENV.exists() else []
    restantes = dict(novos)
    saida = []
    for linha in linhas:
        chave = linha.split("=", 1)[0].strip()
        if chave in restantes:
            saida.append(f"{chave}={restantes.pop(chave)}")
        else:
            saida.append(linha)
    saida.extend(f"{chave}={valor}" for chave, valor in restantes.items())
    gravar_privado(ARQUIVO_ENV, "\n".join(saida) + "\n")


def gravar_privado(caminho: Path, conteudo: str) -> None:
    temporario = caminho.with_name(caminho.name + ".tmp")
    try:
        descritor = os.open(temporario, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
            arquivo.write(conteudo)
        os.replace(temporario, caminho)
    finally:
        temporario.unlink(missing_ok=True)


def enviar_para_vercel(variaveis: dict[str, str]) -> None:
    """Grava cada variável como sensível só em Production; o valor vai pela entrada padrão,
    nunca pela linha de comando nem pela tela."""
    npx = shutil.which("npx")
    if npx is None:
        sys.exit("npx não encontrado: instale o Node.js para enviar as variáveis à Vercel.")
    for nome, valor in variaveis.items():
        comando = [npx, "--yes", VERCEL, "env", "add", nome]
        comando += ["--environment", "production", "--sensitive", "--force"]
        feito = subprocess.run(comando, input=valor, text=True, capture_output=True, cwd=RAIZ)
        if feito.returncode != 0:
            motivo = (feito.stderr or "").replace(valor, "***").strip()[-300:] if valor else ""
            sys.exit(f"A Vercel recusou {nome} (código {feito.returncode}): {motivo}")
        print(f"  {nome}: gravada como sensível em Production")


def codigo_da_resposta(colado: str) -> str:
    colado = colado.strip()
    if "code=" not in colado:
        return colado
    codigos = parse_qs(urlsplit(colado).query).get("code") or []
    if not codigos:
        sys.exit("Não achei o parâmetro code no endereço colado.")
    return codigos[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Autoriza o zpektral na API do Mercado Livre.")
    parser.add_argument(
        "--vercel",
        action="store_true",
        help="manda as credenciais para a produção na Vercel em vez de gravar o backend/.env",
    )
    para_vercel = parser.parse_args().vercel
    # sem o Node, a autorização seria feita e perdida: o token não aparece na tela
    if para_vercel and shutil.which("npx") is None:
        sys.exit("npx não encontrado: instale o Node.js antes de autorizar com --vercel.")
    atual = {} if para_vercel else ler_env()
    print("Autorização do Mercado Livre para o zpektral.")
    print("Crie um app em https://developers.mercadolivre.com.br/devcenter, com um")
    print("endereço de redirecionamento https que você controle (pode ser qualquer página).\n")

    id_cliente = input(f"App ID [{atual.get('ML_ID_CLIENTE') or 'vazio'}]: ").strip()
    id_cliente = id_cliente or atual.get("ML_ID_CLIENTE", "")
    segredo = getpass.getpass("Client Secret (não aparece na tela): ").strip()
    segredo = segredo or atual.get("ML_SEGREDO_CLIENTE", "")
    redirecionamento = input("Endereço de redirecionamento cadastrado no app: ").strip()
    if not (id_cliente and segredo and redirecionamento.startswith("https://")):
        sys.exit("App ID, Client Secret e um redirecionamento https são obrigatórios.")

    estado = secrets.token_urlsafe(16)
    parametros = urlencode(
        {
            "response_type": "code",
            "client_id": id_cliente,
            "redirect_uri": redirecionamento,
            "state": estado,
        }
    )
    print(f"\n1. Abra no navegador e entre na sua conta:\n   {AUTORIZACAO}?{parametros}")
    print("2. Depois de autorizar, copie o endereço completo da página para onde foi levado.")
    colado = input("\nCole aqui o endereço (ou só o code): ")
    if "state=" in colado and parse_qs(urlsplit(colado.strip()).query).get("state") != [estado]:
        sys.exit("O endereço colado não é a resposta deste pedido (state diferente).")
    codigo = codigo_da_resposta(colado)

    resposta = httpx.post(
        TOKEN,
        data={
            "grant_type": "authorization_code",
            "client_id": id_cliente,
            "client_secret": segredo,
            "code": codigo,
            "redirect_uri": redirecionamento,
        },
        headers={"accept": "application/json"},
        timeout=20,
    )
    corpo = (
        resposta.json()
        if resposta.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    if resposta.status_code != 200 or not corpo.get("refresh_token"):
        motivo = corpo.get("message") or corpo.get("error") or f"HTTP {resposta.status_code}"
        sys.exit(f"O Mercado Livre recusou a troca do código: {motivo}")

    # cada autorização é uma cadeia de tokens: o ambiente que renovar primeiro invalida a
    # semente dos outros, e a chave nova impede que outro banco abra o registro deste
    variaveis = {
        "ML_ID_CLIENTE": id_cliente,
        "ML_SEGREDO_CLIENTE": segredo,
        "ML_TOKEN_RENOVACAO": corpo["refresh_token"],
        "CHAVE_CREDENCIAIS": atual.get("CHAVE_CREDENCIAIS") or nova_chave(),
    }
    if para_vercel:
        enviar_para_vercel(variaveis)
        print("\nPronto. A autorização vale a partir do próximo deploy de produção da API.")
        return
    gravar_env(variaveis)
    print("\nPronto. As quatro variáveis estão em backend/.env e o token renovado fica cifrado")
    print("no banco local. Este token é só deste computador: para a produção, rode de novo")
    print("com --vercel, que gera outra autorização e outra chave.")


if __name__ == "__main__":
    main()
