"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { Resultados } from "@/componentes/resultados";

function Busca() {
  const params = useSearchParams();
  const cep = params.get("cep") ?? "";
  return <Resultados key={`${params.get("q")}|${cep}`} />;
}

export function BuscaComParametros() {
  return (
    <Suspense>
      <Busca />
    </Suspense>
  );
}
