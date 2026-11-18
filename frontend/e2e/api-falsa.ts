import { readFileSync } from "node:fs";
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
