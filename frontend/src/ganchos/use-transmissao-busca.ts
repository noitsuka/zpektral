"use client";

import { useEffect, useReducer } from "react";

import { urlTransmissao } from "@/nucleo/api";
import { INICIAL, reduzir, type AcaoTransmissao } from "@/nucleo/transmissao";
import type { Filtros } from "@/nucleo/tipos";

const EVENTOS: Record<string, (dados: never) => AcaoTransmissao> = {
  inicio: (dados) => ({ tipo: "inicio", dados }),
  lote: (dados) => ({ tipo: "lote", dados }),
  falha_fonte: (dados) => ({ tipo: "falha_fonte", dados }),
  fim: (dados) => ({ tipo: "fim", dados }),
};

export function useTransmissaoBusca(
  q: string,
  cep: string | null,
  filtros: Filtros,
  tentativa = 0,
) {
  const [estado, despachar] = useReducer(reduzir, INICIAL);

  useEffect(() => {
    if (!q) return;
    despachar({ tipo: "iniciar" });
    const fonte = new EventSource(urlTransmissao(q, cep, filtros));
    let terminou = false;

    for (const [nome, paraAcao] of Object.entries(EVENTOS)) {
      fonte.addEventListener(nome, (evento) => {
        let dados: unknown;
        try {
          dados = JSON.parse((evento as MessageEvent<string>).data);
        } catch {
          return;
        }
        despachar(paraAcao(dados as never));
        if (nome === "fim") {
          terminou = true;
          fonte.close();
        }
      });
    }
    fonte.onerror = () => {
      if (terminou) return;
      fonte.close();
      despachar({
        tipo: "falha",
        mensagem: "A busca foi interrompida. Tente de novo em alguns segundos.",
      });
    };
    return () => fonte.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, cep, tentativa]);

  return estado;
}
