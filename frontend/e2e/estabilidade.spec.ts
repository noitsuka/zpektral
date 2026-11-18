import { expect, test, type Page } from "@playwright/test";

import type { EventoLote, Oferta } from "../src/nucleo/tipos";
import { eventos, simularApi, transmitirAosPoucos, type Trecho } from "./api-falsa";
import { cls, registrarDeslocamentos } from "./cls";

const BUSCA = "/busca?q=geladeira+frost+free&cep=30130010";
const DESTAQUE = "Menor total no seu CEP";
const ATUALIZAR = { name: "Atualizar a ordem" };

// A primeira passada de cada loja traz só o preço do produto; o frete vem na segunda.
function catalogo(lote: EventoLote): EventoLote {
  const semFrete = (o: Oferta): Oferta => ({
    ...o,
    total: o.preco,
    total_exato: false,
    totais: { pix: o.preco_pix, avista: o.preco, parcelado: null },
    frete: { ...o.frete, status: "calculando", valor: null, prazo: null, prazo_dias: null },
  });
  return { ...lote, fase: "catalogo", ofertas: lote.ofertas.map(semFrete) };
}

type Amostra = { visiveis: string[]; altura: number | null; href: string | null };

// A cada mudança no DOM: os grupos na primeira tela, a altura e o link do menor total.
async function amostrar(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __amostras: Amostra[] };
    w.__amostras = [];
    new MutationObserver(() => {
      const destaque = document.querySelector("section[aria-labelledby=titulo-melhor]");
      w.__amostras.push({
        visiveis: [...document.querySelectorAll('main section[id^="produto-"]')]
          .filter((s) => s.getBoundingClientRect().top < innerHeight)
          .map((s) => s.id),
        altura: destaque ? Math.round(destaque.getBoundingClientRect().height) : null,
        href: destaque?.querySelector("a[target=_blank]")?.getAttribute("href") ?? null,
      });
    }).observe(document, { subtree: true, childList: true, characterData: true });
  });
  return () => page.evaluate(() => (window as unknown as { __amostras: Amostra[] }).__amostras);
}

const fimDaBusca = (page: Page) =>
  expect(page.getByText(/lojas? (consultadas?|responderam)/).first()).toBeVisible({
    timeout: 15_000,
  });
const primeiraDaLista = (page: Page) =>
  page.getByRole("region", { name: "Ofertas por produto" }).locator("article").first();

type Portoes = {
  catalogoBeta?: Promise<void>;
  freteAlfa?: Promise<void>;
  freteBeta?: Promise<void>;
};

/**
 * A busca da geladeira lote a lote: Alfa e Beta mandam o catálogo e depois o frete, a Delta
 * falha, a Epsilon recusa e a Gama responde bem depois. O frete da Beta traz o novo menor
 * total, com um título longo de duas linhas. Os portões seguram a transmissão até o teste
 * soltar, para não depender da velocidade da máquina.
 */
function emLotes(portoes: Portoes = {}) {
  const todos = eventos("busca-geladeira");
  const um = (nome: string, fonte?: string) =>
    todos.find((e) => e.nome === nome && (!fonte || (e.dados as EventoLote).fonte.id === fonte))!;
  const lote = (fonte: string) => um("lote", fonte).dados as EventoLote;
  const beta = lote("beta");
  beta.ofertas[0].titulo +=
    " com Dispenser de Água na Porta, Painel Touch e Prateleiras de Vidro Temperado Reguláveis";
  const trechos: Trecho[] = [
    { ...um("inicio"), espera: 0 },
    { nome: "lote", dados: catalogo(lote("alfa")), espera: 300 },
    { nome: "lote", dados: catalogo(beta), espera: 500, depoisDe: portoes.catalogoBeta },
    { nome: "lote", dados: lote("alfa"), espera: 500, depoisDe: portoes.freteAlfa },
    { ...um("falha_fonte", "delta"), espera: 400 },
    { nome: "lote", dados: beta, espera: 500, depoisDe: portoes.freteBeta },
    { ...um("falha_fonte", "epsilon"), espera: 400 },
    { nome: "lote", dados: lote("gama"), espera: 1500 },
    { ...um("fim"), espera: 300 },
  ];
  return trechos;
}

function portao() {
  let abrir = () => {};
  const aberto = new Promise<void>((r) => (abrir = r));
  return { aberto, abrir };
}

// O catálogo da Alfa na tela e medido (a lista registra o que foi visto a cada quadro).
async function alfaNaTela(page: Page) {
  await expect(primeiraDaLista(page)).toContainText("Loja Alfa", { timeout: 15_000 });
  await page.evaluate(
    () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))),
  );
}

test("a lista e o menor total ficam parados enquanto as lojas respondem", async ({ page }) => {
  await simularApi(page);
  const catalogoBeta = portao();
  await transmitirAosPoucos(page, emLotes({ catalogoBeta: catalogoBeta.aberto }));
  await registrarDeslocamentos(page);
  const amostras = await amostrar(page);
  await page.goto(BUSCA);
  await alfaNaTela(page);
  catalogoBeta.abrir();
  await fimDaBusca(page);
  expect(await cls(page)).toBeLessThan(0.1);

  const lista = await amostras();
  const comGrupos = lista.filter((a) => a.visiveis.length);
  const primeiros = comGrupos[0].visiveis.slice(0, 3);
  for (const a of comGrupos) expect(a.visiveis.slice(0, primeiros.length)).toEqual(primeiros);
  const comDestaque = lista.filter((a) => a.altura !== null);
  expect(new Set(comDestaque.map((a) => a.href)).size).toBeGreaterThan(1);
  expect(new Set(comDestaque.map((a) => a.altura)).size).toBe(1);

  // terminada a busca, a lista fica onde está e oferece a ordem do ranking
  const destaque = page.getByRole("region", { name: DESTAQUE });
  await expect(destaque.getByRole("link", { name: /^Ir para / })).toHaveAttribute(
    "href",
    /beta\.example\/produto\/0/,
  );
  await expect(primeiraDaLista(page)).toContainText("Loja Alfa");
  await page.getByRole("button", ATUALIZAR).click();
  await expect(primeiraDaLista(page)).toContainText("Loja Gama");
  await expect(primeiraDaLista(page)).toContainText("R$ 2.426,00");
  await expect(page.getByRole("button", ATUALIZAR)).toHaveCount(0);
});

test("trocar a ordem durante a busca aplica o ranking na hora", async ({ page }) => {
  await simularApi(page);
  const catalogoBeta = portao();
  const freteAlfa = portao();
  await transmitirAosPoucos(
    page,
    emLotes({ catalogoBeta: catalogoBeta.aberto, freteAlfa: freteAlfa.aberto }),
  );
  await page.goto(BUSCA);
  await alfaNaTela(page);
  catalogoBeta.abrir();
  const lista = page.getByRole("region", { name: "Ofertas por produto" });
  await expect(lista.getByText("Loja Beta").first()).toBeAttached({ timeout: 15_000 });
  // a Beta é mais barata, mas a Alfa já estava na tela e fica no lugar
  await expect(primeiraDaLista(page)).toContainText("Loja Alfa");

  await page.getByLabel(/ordenar/i).selectOption("menor_total");
  await expect(primeiraDaLista(page)).toContainText("Loja Beta");
  await expect(primeiraDaLista(page)).toContainText("R$ 1.999,00");
  freteAlfa.abrir();
  await fimDaBusca(page);
  await page.getByRole("button", ATUALIZAR).click();
  await expect(primeiraDaLista(page)).toContainText("Loja Gama");
  await expect(primeiraDaLista(page)).toContainText("R$ 2.426,00");
});

for (const modo of ["ponteiro", "foco"] as const) {
  test(`o menor total não troca de loja com o ${modo} em cima`, async ({ page }) => {
    await simularApi(page);
    const freteBeta = portao();
    await transmitirAosPoucos(page, emLotes({ freteBeta: freteBeta.aberto }));
    await page.goto(BUSCA);
    const cta = page.getByRole("region", { name: DESTAQUE }).getByRole("link", { name: /^Ir / });
    await expect(cta).toHaveAttribute("href", /alfa\.example\/produto\/0/, { timeout: 15_000 });
    if (modo === "ponteiro") await cta.hover();
    else await cta.focus();

    freteBeta.abrir();
    // com o frete da Beta, o menor total passou a ser dela
    await expect(
      page.getByText(/Consultando [34] de 5 lojas|lojas responderam/).first(),
    ).toBeVisible();
    await page.waitForTimeout(300);
    await expect(cta).toHaveAttribute("href", /alfa\.example\/produto\/0/);

    if (modo === "ponteiro") await page.mouse.move(0, 0);
    else await cta.blur();
    await expect(cta).toHaveAttribute("href", /beta\.example\/produto\/0/);
  });
}

test("sem nada fora do lugar, a busca não oferece reordenar", async ({ page }) => {
  await simularApi(page);
  const todos = eventos("busca-geladeira");
  const alfa = todos.find((e) => e.nome === "lote")!;
  await transmitirAosPoucos(page, [
    { ...todos[0], espera: 0 },
    { ...alfa, espera: 300 },
    { ...todos.at(-1)!, espera: 500 },
  ]);
  await page.goto(BUSCA);
  await fimDaBusca(page);
  await expect(page.getByRole("region", { name: DESTAQUE })).toContainText("Loja Alfa");
  await expect(page.getByRole("button", ATUALIZAR)).toHaveCount(0);
});
