import { expect, type Page, test } from "@playwright/test";

const CEP = "01310100";

function reais(texto: string): number {
  const valor = texto.match(/R\$\s*([\d.]+,\d{2})/);
  if (!valor) throw new Error(`sem valor em reais: ${texto}`);
  return Number(valor[1].replaceAll(".", "").replace(",", "."));
}

async function buscar(page: Page, q: string) {
  const erros: string[] = [];
  page.on("pageerror", (e) => erros.push(String(e)));
  await page.goto(`/busca?${new URLSearchParams({ q, cep: CEP })}`);
  await expect(page.getByText(/lojas? (consultadas?|responderam)/).first()).toBeVisible({
    timeout: 60_000,
  });
  return erros;
}

test("o total do destaque é o produto mais o frete, e o link vai para a loja", async ({ page }) => {
  const erros = await buscar(page, "geladeira frost free");
  const destaque = page.getByRole("region", { name: /Menor total com entrega no CEP/ });
  await expect(destaque).toBeVisible();
  const campo = (rotulo: RegExp) =>
    destaque
      .locator("div", { has: page.getByText(rotulo) })
      .last()
      .innerText();
  const produto = reais(await campo(/^Produto$/i));
  const frete = await campo(/^Frete/i);
  const total = reais(await destaque.getByText(/^R\$/).first().innerText());
  const valorFrete = /grátis/i.test(frete) ? 0 : reais(frete);
  const noPix = await campo(/^No Pix$/i).catch(() => "");
  const totalPix = /R\$/.test(noPix) ? reais(noPix) : null;
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
  const pnr = page.getByText(/Multy 4 Prateleiras Menta - Pnr/i).first();
  const artely = page.getByText(/Multy.*Artely|Artely.*Multy/i).first();
  await expect(pnr).toBeVisible();
  await expect(artely).toBeVisible();
  const grupoPnr = pnr.locator("xpath=ancestor::*[@data-grupo][1]");
  const grupoArtely = artely.locator("xpath=ancestor::*[@data-grupo][1]");
  if ((await grupoPnr.count()) && (await grupoArtely.count()))
    expect(await grupoPnr.getAttribute("data-grupo")).not.toBe(
      await grupoArtely.getAttribute("data-grupo"),
    );
});

test("o histórico de preço responde para as ofertas da busca", async ({ page }) => {
  const historico = page.waitForResponse((r) => r.url().includes("/historico/ofertas"), {
    timeout: 60_000,
  });
  await buscar(page, "air fryer");
  expect((await historico).status()).toBe(200);
});
