"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { registrarBusca } from "@/ganchos/use-buscas-recentes";
import { useCepSalvo } from "@/ganchos/use-cep-salvo";
import { digitosCep, ehCep, mascararCep } from "@/nucleo/formato";

export function useEnviarBusca({
  consultaInicial = "",
  cepInicial,
}: {
  consultaInicial?: string;
  cepInicial?: string;
}) {
  const router = useRouter();
  const [cepSalvo, salvarCep] = useCepSalvo();
  const [consulta, setConsulta] = useState(consultaInicial);
  const [cepDigitado, setCepDigitado] = useState<string | null>(cepInicial ?? null);
  const [erro, setErro] = useState<string | null>(null);
  const cep = cepDigitado ?? mascararCep(cepSalvo);

  function enviar() {
    const q = consulta.trim();
    if (q.length < 2) {
      setErro("Digite o nome de um produto.");
      return;
    }
    if (cep && !ehCep(cep)) {
      setErro("CEP incompleto: são 8 dígitos.");
      return;
    }
    setErro(null);
    const params = new URLSearchParams({ q });
    const digitos = cep ? digitosCep(cep) : null;
    if (digitos) {
      params.set("cep", digitos);
      salvarCep(digitos);
    }
    registrarBusca({ q, cep: digitos });
    router.push(`/busca?${params}`);
  }

  return {
    consulta,
    setConsulta: (v: string) => {
      setConsulta(v);
      if (erro) setErro(null);
    },
    cep,
    setCep: (v: string) => {
      setCepDigitado(mascararCep(v));
      if (erro) setErro(null);
    },
    erro,
    enviar,
  };
}
