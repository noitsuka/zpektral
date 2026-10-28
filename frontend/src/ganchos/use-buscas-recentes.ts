"use client";

import { useSyncExternalStore } from "react";

import {
  adicionarRecente,
  lerRecentes,
  removerRecente,
  type BuscaRecente,
} from "@/nucleo/recentes";

const CHAVE = "zpektral:recentes";
const VAZIA: BuscaRecente[] = [];
const ouvintes = new Set<() => void>();
let bruto: string | null = null;
let cache: BuscaRecente[] = VAZIA;

function ler(): string | null {
  try {
    return window.localStorage.getItem(CHAVE);
  } catch {
    return null;
  }
}

function instantaneo(): BuscaRecente[] {
  const atual = ler();
  if (atual !== bruto) {
    bruto = atual;
    cache = lerRecentes(atual);
  }
  return cache;
}

function gravar(lista: BuscaRecente[]) {
  try {
    window.localStorage.setItem(CHAVE, JSON.stringify(lista));
  } catch {}
  ouvintes.forEach((o) => o());
}

function assinar(ouvinte: () => void) {
  ouvintes.add(ouvinte);
  window.addEventListener("storage", ouvinte);
  return () => {
    ouvintes.delete(ouvinte);
    window.removeEventListener("storage", ouvinte);
  };
}

export function registrarBusca(busca: BuscaRecente) {
  gravar(adicionarRecente(instantaneo(), busca));
}

export function useBuscasRecentes() {
  const lista = useSyncExternalStore(assinar, instantaneo, () => VAZIA);
  return {
    recentes: lista,
    remover: (busca: BuscaRecente) => gravar(removerRecente(instantaneo(), busca)),
  };
}
