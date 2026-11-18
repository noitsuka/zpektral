import type { Oferta } from "@/nucleo/tipos";
import { agrupar } from "@/nucleo/vitrine";

/**
 * Ordem da lista enquanto as lojas respondem: o que a pessoa já viu fica no lugar, e o resto
 * segue o ranking logo abaixo. Assim uma oferta melhor que chega depois aparece a seguir do que
 * já foi visto, sem empurrar nada na tela. `vistos` traz, na ordem da tela, os ids das ofertas
 * de cada grupo visto e depois a chave do grupo: o id segura a oferta quando o grupo muda de
 * chave no fim da busca, e a chave segura o grupo quando a oferta volta com outro id.
 */
export function ordemEstavel(ranking: Oferta[], vistos: readonly string[]): Oferta[] {
  if (!vistos.length) return ranking;
  const porId = new Map(ranking.map((o) => [o.id, [o]]));
  const porGrupo = new Map(agrupar(ranking).map((g) => [g.chave, g.ofertas]));
  const fixos = new Set<Oferta>();
  for (const marca of vistos)
    for (const o of porId.get(marca) ?? porGrupo.get(marca) ?? []) fixos.add(o);
  return [...fixos, ...ranking.filter((o) => !fixos.has(o))];
}

export function mesmaOrdem(a: readonly string[], b: readonly string[]): boolean {
  return a.length === b.length && a.every((id, i) => id === b[i]);
}

const emGrupos = (ofertas: Oferta[]) => agrupar(ofertas).flatMap((g) => g.ofertas.map((o) => o.id));

/** A lista mostrada, já agrupada, difere da que o ranking montaria agora. */
export function foraDeOrdem(mostrada: Oferta[], ranking: Oferta[]): boolean {
  return !mesmaOrdem(emGrupos(mostrada), emGrupos(ranking));
}

/** Nunca troca a oferta do destaque debaixo do ponteiro ou do foco de quem está nela. */
export function destaqueSeguro<T>(
  exibido: T | null,
  melhor: T | null,
  interagindo: boolean,
): T | null {
  return interagindo && exibido !== null ? exibido : melhor;
}
