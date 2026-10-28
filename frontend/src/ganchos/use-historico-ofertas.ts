"use client";

import { useEffect, useState } from "react";

import { historicoDasOfertas } from "@/nucleo/api";
import type { HistoricoOfertas } from "@/nucleo/tipos";

const POR_PEDIDO = 50;

export function useHistoricoOfertas(ids: string[], ativo: boolean): HistoricoOfertas {
  const chave = ativo ? ids.slice(0, POR_PEDIDO).join(",") : "";
  const [historico, setHistorico] = useState<HistoricoOfertas>({});

  useEffect(() => {
    if (!chave) return;
    const controlador = new AbortController();
    historicoDasOfertas(chave.split(","), controlador.signal)
      .then((novos) => setHistorico((atual) => ({ ...atual, ...novos })))
      .catch(() => undefined);
    return () => controlador.abort();
  }, [chave]);

  return historico;
}
