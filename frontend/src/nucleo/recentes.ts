export type BuscaRecente = { q: string; cep: string | null };

const LIMITE = 6;

const chave = (b: BuscaRecente) => `${b.q.trim().toLowerCase()}|${b.cep ?? ""}`;

export function adicionarRecente(lista: BuscaRecente[], busca: BuscaRecente): BuscaRecente[] {
  const nova = { q: busca.q.trim(), cep: busca.cep };
  return [nova, ...lista.filter((b) => chave(b) !== chave(nova))].slice(0, LIMITE);
}

export function removerRecente(lista: BuscaRecente[], busca: BuscaRecente): BuscaRecente[] {
  return lista.filter((b) => chave(b) !== chave(busca));
}

export function lerRecentes(bruto: string | null): BuscaRecente[] {
  if (!bruto) return [];
  let dados: unknown;
  try {
    dados = JSON.parse(bruto);
  } catch {
    return [];
  }
  if (!Array.isArray(dados)) return [];
  const validas: BuscaRecente[] = [];
  for (const item of dados) {
    if (typeof item !== "object" || item === null) continue;
    const { q, cep } = item as Record<string, unknown>;
    if (typeof q !== "string" || !q.trim() || q.length > 120) continue;
    if (cep !== undefined && cep !== null && !(typeof cep === "string" && /^\d{8}$/.test(cep)))
      continue;
    validas.push({ q, cep: typeof cep === "string" ? cep : null });
  }
  return validas.slice(0, LIMITE);
}
