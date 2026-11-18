"use client";

import { useEffect, useReducer } from "react";

import { urlTransmissao } from "@/nucleo/api";
import { INICIAL, reduzir, type AcaoTransmissao } from "@/nucleo/transmissao";

// Cada loja tem 12 s no servidor; meio minuto sem evento algum é conexão travada.
const SILENCIO_MAXIMO_MS = 30_000;

const EVENTOS: Record<string, (dados: never) => AcaoTransmissao> = {
  inicio: (dados) => ({ tipo: "inicio", dados }),
  lote: (dados) => ({ tipo: "lote", dados }),
  falha_fonte: (dados) => ({ tipo: "falha_fonte", dados }),
  fim: (dados) => ({ tipo: "fim", dados }),
};

export function useTransmissaoBusca(q: string, cep: string | null, tentativa = 0) {
  const [estado, despachar] = useReducer(reduzir, INICIAL);

  useEffect(() => {
    if (!q) return;
    despachar({ tipo: "iniciar" });
    const fonte = new EventSource(urlTransmissao(q, cep));
    let terminou = false;
    let vigia: ReturnType<typeof setTimeout> | undefined;
    const falhar = () => {
      if (terminou) return;
      terminou = true;
      clearTimeout(vigia);
      fonte.close();
      despachar({
        tipo: "falha",
        mensagem: "A busca foi interrompida. Tente de novo em alguns segundos.",
      });
    };
    const vigiar = () => {
      clearTimeout(vigia);
      vigia = setTimeout(falhar, SILENCIO_MAXIMO_MS);
    };
    vigiar();

    for (const [nome, paraAcao] of Object.entries(EVENTOS)) {
      fonte.addEventListener(nome, (evento) => {
        let dados: unknown;
        try {
          dados = JSON.parse((evento as MessageEvent<string>).data);
        } catch {
          return;
        }
        vigiar();
        despachar(paraAcao(dados as never));
        if (nome === "fim") {
          terminou = true;
          clearTimeout(vigia);
          fonte.close();
        }
      });
    }
    fonte.onerror = falhar;
    return () => {
      clearTimeout(vigia);
      fonte.close();
    };
  }, [q, cep, tentativa]);

  return estado;
}
