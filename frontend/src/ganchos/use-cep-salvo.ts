"use client";

import { useCallback, useSyncExternalStore } from "react";

const CHAVE = "zpektral.cep";
const ouvintes = new Set<() => void>();

function ler(): string {
  try {
    return localStorage.getItem(CHAVE) ?? "";
  } catch {
    return "";
  }
}

function assinar(ouvinte: () => void) {
  ouvintes.add(ouvinte);
  return () => ouvintes.delete(ouvinte);
}

export function useCepSalvo(): [string, (cep: string) => void] {
  const cep = useSyncExternalStore(assinar, ler, () => "");
  const salvar = useCallback((cep: string) => {
    try {
      localStorage.setItem(CHAVE, cep);
    } catch {
      // Sem localStorage (aba anônima, cota cheia) o CEP só não fica lembrado.
    }
    ouvintes.forEach((l) => l());
  }, []);
  return [cep, salvar];
}
