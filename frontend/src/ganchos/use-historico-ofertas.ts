"use client";

import { useEffect, useRef, useState } from "react";

import { historicoDasOfertas } from "@/nucleo/api";
import type { HistoricoOfertas } from "@/nucleo/tipos";

const POR_PEDIDO = 50;

export function useHistoricoOfertas(ids: string[], ativo: boolean): HistoricoOfertas {
  const chave = ativo ? ids.join(",") : "";
  const pedidos = useRef(new Set<string>());
  const [historico, setHistorico] = useState<HistoricoOfertas>({});

  useEffect(() => {
    if (!chave) return;
    const jaPedidos = pedidos.current;
    const novos = chave.split(",").filter((id) => !jaPedidos.has(id));
    if (!novos.length) return;
    const controlador = new AbortController();
    const pendentes = new Set(novos);
    novos.forEach((id) => jaPedidos.add(id));
    for (let i = 0; i < novos.length; i += POR_PEDIDO) {
      const lote = novos.slice(i, i + POR_PEDIDO);
      historicoDasOfertas(lote, controlador.signal)
        .then((recebidos) => setHistorico((atual) => ({ ...atual, ...recebidos })))
        .catch(() => undefined)
        .finally(() => lote.forEach((id) => pendentes.delete(id)));
    }
    return () => {
      controlador.abort();
      pendentes.forEach((id) => jaPedidos.delete(id));
    };
  }, [chave]);

  return historico;
}
