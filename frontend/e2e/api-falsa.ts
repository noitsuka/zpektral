import { readFileSync } from "node:fs";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import path from "node:path";

import type { Page } from "@playwright/test";

import { API_FALSA } from "../playwright.config";

const CORS = { "access-control-allow-origin": "*" };
const DIA_MS = 86_400_000;

// Gerados por backend/scripts/dados_e2e.py com o mesmo código que a API usa para transmitir.
function transmissao(nome: string): string {
  const agora = new Date();
  const validade = new Date(agora.getTime() + 2 * DIA_MS).toISOString();
  return readFileSync(path.join(__dirname, "dados", `${nome}.sse`), "utf-8")
    .replaceAll(/"consultado_em":"[^"]+"/g, `"consultado_em":"${agora.toISOString()}"`)
    .replaceAll(/"preco_valido_ate":"[^"]+"/g, `"preco_valido_ate":"${validade}"`);
}

export type Evento = { nome: string; dados: Record<string, unknown> };

export function eventos(nome: string): Evento[] {
  return transmissao(nome)
    .split("\n\n")
    .filter(Boolean)
    .map((bloco) => {
      const [evento, dados] = bloco.split("\ndata: ");
      return { nome: evento.replace("event: ", ""), dados: JSON.parse(dados) };
    });
}

export type Trecho = Evento & { espera: number; depoisDe?: Promise<unknown> };

// O route.fulfill entrega o SSE inteiro de uma vez. Para ver a lista mudando lote a lote, como
// com as lojas reais, a transmissão vem de um servidor local que solta cada evento no seu tempo.
export async function transmitirAosPoucos(page: Page, trechos: Trecho[]) {
  const servidor = createServer(async (_, resposta) => {
    resposta.writeHead(200, { ...CORS, "content-type": "text/event-stream" });
    for (const { nome, dados, espera, depoisDe } of trechos) {
      await depoisDe;
      await new Promise((r) => setTimeout(r, espera));
      if (resposta.destroyed) return;
      resposta.write(`event: ${nome}\ndata: ${JSON.stringify(dados)}\n\n`);
    }
    resposta.end();
  });
  await new Promise<void>((pronto) => servidor.listen(0, "127.0.0.1", pronto));
  const { port } = servidor.address() as AddressInfo;
  await page.route(
    (url) => url.pathname === "/busca/transmissao",
    (rota) => rota.continue({ url: `http://127.0.0.1:${port}/` }),
  );
  page.once("close", () => {
    servidor.closeAllConnections();
    servidor.close();
  });
}

function cenario(q: string | null, cep: string | null): string | null {
  if (q === "xyzzy quasar") return "busca-sem-resultado";
  if (q === "lojas fora") return "busca-lojas-fora";
  if (cep === "69900000") return "busca-nao-entrega";
  if (cep === "99999999") return null;
  return "busca-geladeira";
}

const OFERTA_EM_PROMOCAO = "beta:0:1";

function serieDeDias(preco: number, dias: number) {
  return Array.from({ length: dias }, (_, i) => ({
    dia: new Date(Date.now() - (dias - i) * DIA_MS).toISOString().slice(0, 10),
    preco,
  }));
}

export async function simularApi(page: Page, opcoes: { comHistorico?: boolean } = {}) {
  await page.route(`${API_FALSA}/**`, async (rota) => {
    const url = new URL(rota.request().url());
    const q = url.searchParams.get("q");
    const cep = url.searchParams.get("cep");
    if (url.pathname === "/busca/transmissao" || url.pathname === "/busca") {
      const nome = cenario(q, cep);
      if (nome === null)
        return rota.fulfill({
          status: 404,
          headers: CORS,
          json: { detail: "CEP não encontrado." },
        });
      if (url.pathname === "/busca")
        return rota.fulfill({ status: 503, headers: CORS, json: { detail: "indisponível" } });
      return rota.fulfill({
        status: 200,
        headers: { ...CORS, "content-type": "text/event-stream" },
        body: transmissao(nome),
      });
    }
    if (url.pathname.startsWith("/cep/")) {
      const cep = url.pathname.slice("/cep/".length);
      if (cep === "99999999")
        return rota.fulfill({ status: 404, headers: CORS, json: { detail: "CEP não encontrado" } });
      return rota.fulfill({
        headers: CORS,
        json: {
          cep,
          logradouro: "Avenida Afonso Pena",
          bairro: "Centro",
          cidade: "Belo Horizonte",
          uf: "MG",
        },
      });
    }
    if (url.pathname === "/historico/ofertas") {
      const ids = (url.searchParams.get("ids") ?? "").split(",");
      const corpo =
        opcoes.comHistorico && ids.includes(OFERTA_EM_PROMOCAO)
          ? { [OFERTA_EM_PROMOCAO]: serieDeDias(259_900, 10) }
          : {};
      return rota.fulfill({ headers: CORS, json: corpo });
    }
    return rota.fulfill({ status: 404, headers: CORS, json: { detail: "não simulado" } });
  });
  await page
    .context()
    .route("https://*.example/**", (rota) =>
      rota.fulfill({ body: "<title>loja</title>", contentType: "text/html" }),
    );
}
