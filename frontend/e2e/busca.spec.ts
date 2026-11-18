import { expect, test } from "@playwright/test";

import { simularApi } from "./api-falsa";

const BUSCA_BH = "/busca?q=geladeira+frost+free&cep=30130010";
const DESTAQUE = "Menor total no seu CEP";

test("pesquisa, filtra, ordena e abre a loja", async ({ page }) => {
  await simularApi(page);
  await page.goto("/");
  await page.getByLabel(/produto/i).fill("geladeira frost free");
  await page.getByLabel(/cep/i).fill("30130010");
  await page.getByRole("button", { name: /comparar/i }).click();

  await expect(page).toHaveURL(/\/busca\?q=geladeira\+frost\+free&cep=30130010/);
  await expect(page.getByText(DESTAQUE)).toBeVisible();
  // toda linha diz "Ir para {loja}"; o botão do menor total é o da região em destaque
  const irParaLoja = page
    .getByRole("region", { name: DESTAQUE })
    .getByRole("link", { name: /Ir para Loja Beta/ });
  await expect(irParaLoja).toHaveAttribute("href", /^https:\/\/beta\.example\/produto\/0/);
  await expect(irParaLoja).toHaveAttribute("target", "_blank");

  // pelo preço do produto, a oferta sem frete cotado é a primeira; o filtro a tira
  await page.getByLabel(/ordenar/i).selectOption("menor_preco");
  const semCotacao = page.getByText("Geladeira Frost Free Consul 340L Branca 110V");
  await expect(semCotacao.first()).toBeVisible();
  await page.getByRole("button", { name: /^Filtros/ }).click();
  const gaveta = page.getByRole("dialog");
  await gaveta.getByText("Só total confirmado").click();
  await gaveta.getByRole("button", { name: /^Ver / }).click();
  await expect(gaveta).toBeHidden();
  await expect(semCotacao).toHaveCount(0);

  await page.getByLabel(/ordenar/i).selectOption("menor_total");
  // o menor total abre a página e não se repete na lista, que segue com o próximo
  const destaque = page.getByRole("region", { name: DESTAQUE });
  await expect(destaque).toContainText("Loja Beta");
  await expect(destaque).toContainText("R$ 1.899,00");
  const lista = page.getByRole("region", { name: "Ofertas por produto" });
  const primeira = lista.locator("article").first();
  await expect(primeira).toContainText("Loja Gama");
  await expect(primeira).toContainText("R$ 2.426,00");

  const [aba] = await Promise.all([page.waitForEvent("popup"), irParaLoja.click()]);
  await expect(aba).toHaveURL(/beta\.example\/produto\/0/);
});

test("o CEP digitado mostra o endereço de entrega antes da busca", async ({ page }) => {
  await simularApi(page);
  await page.goto("/");
  const cep = page.getByLabel(/cep/i);
  await cep.fill("30130010");
  await expect(
    page.getByText("Entrega em Avenida Afonso Pena, Centro, Belo Horizonte/MG"),
  ).toBeVisible();
  await cep.fill("99999999");
  await expect(page.getByText("Não achamos esse CEP. Confira os números.")).toBeVisible();
});

test("CEP incompleto não inicia a busca", async ({ page }) => {
  await simularApi(page);
  await page.goto("/");
  await page.getByLabel(/produto/i).fill("geladeira");
  await page.getByLabel(/cep/i).fill("3013");
  await page.getByRole("button", { name: /comparar/i }).click();
  await expect(page.getByText("CEP incompleto: são 8 dígitos.")).toBeVisible();
  await expect(page).toHaveURL(/\/$/);
});

test("CEP que não existe mostra o motivo e como seguir, sem repetir o erro", async ({ page }) => {
  await simularApi(page);
  await page.goto("/busca?q=geladeira+frost+free&cep=99999999");
  const alerta = page.getByRole("alert").filter({ hasText: /Não achamos o CEP 99999-999/ });
  await expect(alerta).toBeVisible();
  await expect(alerta.getByRole("button", { name: "Tentar de novo" })).toHaveCount(0);
  await expect(alerta.getByRole("link", { name: "Buscar sem CEP" })).toHaveAttribute(
    "href",
    "/busca?q=geladeira+frost+free",
  );
  await alerta.getByRole("button", { name: "Corrigir o CEP" }).click();
  await expect(page.getByLabel(/cep/i).first()).toBeFocused();
});

test("CEP sem entrega diz que as lojas não atendem o endereço", async ({ page }) => {
  await simularApi(page);
  await page.goto("/busca?q=geladeira+frost+free&cep=69900000");
  await expect(page.getByText("Nenhuma loja entrega no CEP 69900-000")).toBeVisible();
});

test("lojas fora do ar não viram lista vazia sem explicação", async ({ page }) => {
  await simularApi(page);
  await page.goto("/busca?q=lojas+fora");
  await expect(page.getByText("Nenhuma loja respondeu")).toBeVisible();
});

test("busca sem resultado diz o que fazer", async ({ page }) => {
  await simularApi(page);
  await page.goto("/busca?q=xyzzy+quasar");
  await expect(page.getByText("Nenhuma loja tem “xyzzy quasar”")).toBeVisible();
});

test("promoção com histórico mostra a queda verificada e o desconto anunciado", async ({
  page,
}) => {
  await simularApi(page, { comHistorico: true });
  await page.goto(BUSCA_BH);
  const destaque = page.getByRole("region", { name: DESTAQUE });
  await expect(destaque).toContainText("Electrolux 400L");
  await destaque.getByRole("button", { name: "Ver a conta" }).click();
  await expect(destaque).toContainText(/Menor preço desta loja em \d+ dias/);
  await expect(destaque).toContainText("desconto anunciado pela loja");
  await expect(destaque).toContainText("Desconto anunciado sem respaldo");
  await expect(destaque).toContainText("SUPEROFERTA");
});

test("sem histórico, o desconto anunciado não vira economia confirmada", async ({ page }) => {
  await simularApi(page);
  await page.goto(BUSCA_BH);
  const destaque = page.getByRole("region", { name: DESTAQUE });
  await destaque.getByRole("button", { name: "Ver a conta" }).click();
  await expect(destaque).toContainText("desconto anunciado pela loja");
  await expect(destaque).toContainText("Histórico insuficiente para confirmar a economia");
  await expect(destaque).not.toContainText("Menor preço desta loja");
});

test("Mais ofertas mostra o resto sem perder o que já estava na tela", async ({ page }) => {
  await simularApi(page);
  await page.goto(BUSCA_BH);
  const mais = page.getByRole("button", { name: /Mais ofertas/ });
  await expect(mais).toBeVisible();
  const antes = await page.locator("main article").count();
  await mais.click();
  await expect.poll(() => page.locator("main article").count()).toBeGreaterThan(antes);
});

test("recarregar a página refaz a busca da URL", async ({ page }) => {
  await simularApi(page);
  await page.goto(BUSCA_BH);
  await expect(page.getByText(DESTAQUE)).toBeVisible();
  await page.reload();
  await expect(page.getByText(DESTAQUE)).toBeVisible();
});

test("no celular os filtros abrem numa gaveta e nada passa da largura", async ({
  page,
  isMobile,
}) => {
  test.skip(!isMobile, "só no celular");
  await simularApi(page);
  await page.goto(BUSCA_BH);
  await expect(page.getByText(DESTAQUE)).toBeVisible();
  await page.getByRole("button", { name: /^Filtros/ }).click();
  const gaveta = page.getByRole("dialog");
  await expect(gaveta).toBeVisible();
  await gaveta.getByText("Só total confirmado").click();
  await gaveta.getByRole("button", { name: /^Ver / }).click();
  await expect(gaveta).toBeHidden();
  const largura = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(largura).toBeLessThanOrEqual(page.viewportSize()!.width);
});
