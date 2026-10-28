import getpass
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

AUTORIZACAO = "https://auth.mercadolivre.com.br/authorization"
TOKEN = "https://api.mercadolibre.com/oauth/token"
RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_ENV = RAIZ / ".env"


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
    descritor = os.open(temporario, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)
    os.replace(temporario, caminho)


def codigo_da_resposta(colado: str) -> str:
    colado = colado.strip()
    if "code=" not in colado:
        return colado
    codigos = parse_qs(urlsplit(colado).query).get("code") or []
    if not codigos:
        sys.exit("Não achei o parâmetro code no endereço colado.")
    return codigos[0]


def main() -> None:
    atual = ler_env()
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

    parametros = urlencode(
        {"response_type": "code", "client_id": id_cliente, "redirect_uri": redirecionamento}
    )
    print(f"\n1. Abra no navegador e entre na sua conta:\n   {AUTORIZACAO}?{parametros}")
    print("2. Depois de autorizar, copie o endereço completo da página para onde foi levado.")
    codigo = codigo_da_resposta(input("\nCole aqui o endereço (ou só o code): "))

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

    arquivo_token = RAIZ / (atual.get("ML_ARQUIVO_TOKEN") or ".ml-token.json")
    gravar_privado(
        arquivo_token,
        json.dumps(
            {
                "access_token": corpo["access_token"],
                "refresh_token": corpo["refresh_token"],
                "expires_at": time.time() + int(corpo.get("expires_in", 21600)) - 300,
            }
        ),
    )
    gravar_env(
        {
            "ML_ID_CLIENTE": id_cliente,
            "ML_SEGREDO_CLIENTE": segredo,
            "ML_TOKEN_RENOVACAO": corpo["refresh_token"],
        }
    )
    print("\nPronto. Credenciais salvas em backend/.env e o token em", arquivo_token.name)
    print("Reinicie a API: o Mercado Livre passa a aparecer nas buscas, com frete do seu CEP.")


if __name__ == "__main__":
    main()
