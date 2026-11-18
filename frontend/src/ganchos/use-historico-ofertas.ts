"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { historicoDasOfertas } from "@/nucleo/api";
import type { HistoricoOfertas } from "@/nucleo/tipos";

const POR_PEDIDO = 50;

// Pede o histórico só das ofertas que ainda não foram pedidas, em lotes.
export function useHistoricoOfertas() {
  const pedidos = useRef(new Set<string>());
  const controlador = useRef<AbortController | null>(null);
  const [historico, setHistorico] = useState<HistoricoOfertas>({});
  const [emVoo, setEmVoo] = useState(0);

  const pedir = useCallback((lista: string[]) => {
    const novos = lista.filter((id) => !pedidos.current.has(id));
    if (!novos.length) return;
    controlador.current ??= new AbortController();
    const { signal } = controlador.current;
    novos.forEach((id) => pedidos.current.add(id));
    for (let i = 0; i < novos.length; i += POR_PEDIDO) {
      const lote = novos.slice(i, i + POR_PEDIDO);
      setEmVoo((n) => n + 1);
      historicoDasOfertas(lote, signal)
        .then((recebidos) => setHistorico((atual) => ({ ...atual, ...recebidos })))
        .catch(() => {
          if (!signal.aborted) lote.forEach((id) => pedidos.current.delete(id));
        })
        .finally(() => setEmVoo((n) => n - 1));
    }
  }, []);

  useEffect(
    () => () => {
      controlador.current?.abort();
      controlador.current = null;
      pedidos.current.clear();
    },
    [],
  );

  return { historico, carregando: emVoo > 0, pedir };
}
