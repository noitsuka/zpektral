import { expect, type Page, test } from "@playwright/test";

import { cls, maioresDeslocamentos, registrarDeslocamentos } from "../e2e/cls";

const CEP = "01310100";

function reais(texto: string): number {
  const valor = texto.match(/R\$\s*([\d.]+,\d{2})/);
  if (!valor) throw new Error(`sem valor em reais: ${texto}`);
  return Number(valor[1].replaceAll(".", "").replace(",", "."));
}

async function buscar(page: Page, q: string, cep = CEP) {
  const erros: string[] = [];
  page.on("pageerror", (e) => erros.push(String(e)));
  await page.goto(`/busca?${new URLSearchParams({ q, cep })}`);
  await expect(page.getByText(/lojas? (consultadas?|responderam)/).first()).toBeVisible({
    timeout: 60_000,
  });
  return erros;
}

test("o total do destaque é o produto mais o frete, e o link vai para a loja", async ({ page }) => {
  const erros = await buscar(page, "geladeira frost free");
  const destaque = page.getByRole("region", { name: /Menor total no seu CEP/ });
  await expect(destaque).toBeVisible();
  // a linha se anuncia como "Loja, R$ total"
  const total = reais((await destaque.getByRole("article").getAttribute("aria-label")) ?? "");
  await destaque.getByRole("button", { name: /Ver a conta/ }).click();
  const conta = destaque.getByRole("region", { name: /^Conta de / });
  const valor = (rotulo: RegExp) =>
    conta.locator("dt", { hasText: rotulo }).locator("xpath=following-sibling::dd[1]");
  await expect(valor(/^Produto$/)).toBeVisible();
  const produto = reais(await valor(/^Produto$/).innerText());
  const frete = await valor(/^Frete/).innerText();
  const valorFrete = /grátis/i.test(frete) ? 0 : reais(frete);
  const totalPix = (await valor(/^No Pix$/).count())
    ? reais(await valor(/^No Pix$/).innerText())
    : null;
  // o total exibido é o do cartão (produto + frete) ou o do Pix, nunca outro número
  expect([produto + valorFrete, totalPix].map((v) => v && Math.round(v * 100))).toContain(
    Math.round(total * 100),
  );
  const link = destaque.getByRole("link", { name: /^Ir para / });
  const destino = new URL((await link.getAttribute("href"))!);
  expect(destino.protocol).toBe("https:");
  expect(destino.hostname).not.toContain("zpektral");
  expect(erros).toEqual([]);
});

test("estante PNR e estante Artely aparecem como produtos distintos", async ({ page }) => {
  await buscar(page, "estante para livros multy 4 prateleiras menta");
  // pelos títulos dos grupos: a linha do menor total também cita o produto
  const titulo = (nome: RegExp) => page.getByRole("heading", { level: 3, name: nome }).first();
  const pnr = titulo(/Multy 4 Prateleiras Menta - Pnr/i);
  const artely = titulo(/Multy.*Artely|Artely.*Multy/i);
  await expect(pnr).toBeVisible();
  await expect(artely).toBeVisible();
  const grupo = (alvo: typeof pnr) =>
    alvo.locator('xpath=ancestor::section[starts-with(@id, "produto-")][1]').getAttribute("id");
  const grupoPnr = await grupo(pnr);
  expect(grupoPnr).toBeTruthy();
  expect(grupoPnr).not.toBe(await grupo(artely));
});

test("o histórico de preço responde para as ofertas da busca", async ({ page }) => {
  const historico = page.waitForResponse((r) => r.url().includes("/historico/ofertas"), {
    timeout: 60_000,
  });
  await buscar(page, "air fryer");
  expect((await historico).status()).toBe(200);
});

// Medida manual para comparar mudanças: as lojas respondem em ritmos diferentes, e a lista
// não pode sacudir enquanto isso (CLS de sessão, como o Chrome mede). Um CEP por projeto e
// diferente dos outros testes: com o mesmo, a busca sairia do cache e chegaria toda de uma vez.
test("a lista não sacode enquanto as lojas respondem", async ({ page }) => {
  await registrarDeslocamentos(page);
  const cep = test.info().project.name === "celular" ? "04538132" : "30130010";
  const erros = await buscar(page, "geladeira frost free", cep);
  await page.waitForTimeout(1000);
  const medido = await cls(page);
  const maiores = await maioresDeslocamentos(page);
  test.info().annotations.push({ type: "cls", description: `${medido.toFixed(3)}: ${maiores}` });
  expect(medido, maiores).toBeLessThan(0.1);
  expect(erros).toEqual([]);
});
