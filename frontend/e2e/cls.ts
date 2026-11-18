import type { Page } from "@playwright/test";

type Deslocamento = { t: number; v: number; de: string[] };

/**
 * Guarda cada layout-shift que não veio logo depois de um toque, clique ou tecla, com o bloco
 * de onde cada pedaço deslocado veio (grupo, menor total ou outro elemento).
 */
export async function registrarDeslocamentos(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __deslocamentos: Deslocamento[] };
    w.__deslocamentos = [];
    const bloco = (no: Node | null) => {
      const el = no && (no instanceof Element ? no : no.parentElement);
      const dono = el?.closest("section[id], section[aria-labelledby], [aria-hidden]");
      return `${el?.tagName.toLowerCase()} em ${dono?.id || dono?.getAttribute("aria-labelledby") || dono?.tagName.toLowerCase()}`;
    };
    new PerformanceObserver((lista) => {
      for (const e of lista.getEntries() as (PerformanceEntry & {
        value: number;
        hadRecentInput: boolean;
        sources: { node: Node | null }[];
      })[])
        if (!e.hadRecentInput)
          w.__deslocamentos.push({
            t: e.startTime,
            v: e.value,
            de: e.sources.map((s) => bloco(s.node)),
          });
    }).observe({ type: "layout-shift", buffered: true });
  });
}

const lidos = (page: Page) =>
  page.evaluate(() => (window as unknown as { __deslocamentos: Deslocamento[] }).__deslocamentos);

/** CLS como o Chrome mede: a maior janela de sessão (pausas de até 1 s, no máximo 5 s). */
export async function cls(page: Page): Promise<number> {
  let maior = 0;
  let janela = 0;
  let inicio = -Infinity;
  let ultimo = -Infinity;
  for (const { t, v } of await lidos(page)) {
    if (t - ultimo > 1000 || t - inicio > 5000) {
      janela = 0;
      inicio = t;
    }
    janela += v;
    ultimo = t;
    maior = Math.max(maior, janela);
  }
  return maior;
}

/** Os maiores deslocamentos, para saber o que mexeu quando o CLS passa do limite. */
export async function maioresDeslocamentos(page: Page, quantos = 3): Promise<string> {
  return (await lidos(page))
    .sort((a, b) => b.v - a.v)
    .slice(0, quantos)
    .map((d) => `${d.v.toFixed(3)} em ${Math.round(d.t)} ms (${[...new Set(d.de)].join(", ")})`)
    .join("; ");
}
