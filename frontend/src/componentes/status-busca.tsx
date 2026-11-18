import { ChevronDown } from "lucide-react";

import { plural } from "@/nucleo/formato";
import type { CelulaFonte, EstadoFonte } from "@/nucleo/transmissao";
import { lojasFora } from "@/nucleo/vitrine";

const MOTIVO: Partial<Record<EstadoFonte, string>> = {
  bloqueada: "recusou a consulta",
  tempo_esgotado: "não respondeu a tempo",
  erro: "respondeu com erro",
};

function estadoDoTraco(s: EstadoFonte): string {
  return s === "erro" || s === "tempo_esgotado" || s === "bloqueada" ? "fora" : s;
}

export function StatusBusca({
  fontes,
  terminou,
  ofertas,
  interrompida = false,
}: {
  fontes: CelulaFonte[];
  terminou: boolean;
  ofertas: number;
  interrompida?: boolean;
}) {
  const ativas = fontes.filter((f) => f.situacao !== "desativada");
  const fora = lojasFora(ativas);
  const responderam = ativas.filter(
    (f) => f.situacao !== "aguardando" && f.situacao !== "catalogo",
  );
  const texto = interrompida
    ? "A consulta às lojas foi interrompida"
    : !ativas.length
      ? "Preparando a busca"
      : terminou
        ? fora.length
          ? `${responderam.length - fora.length} de ${plural(ativas.length, "loja respondeu", "lojas responderam")}`
          : `${plural(ativas.length, "loja consultada", "lojas consultadas")}`
        : `Consultando as lojas: ${responderam.length} de ${ativas.length}`;

  return (
    <div className="flex min-h-11 flex-wrap items-center gap-x-4">
      <div
        role="progressbar"
        aria-label="Lojas que já responderam"
        aria-valuemin={0}
        aria-valuemax={ativas.length || 1}
        aria-valuenow={responderam.length}
        className="flex h-3.5 w-full max-w-64 items-end gap-px sm:w-64 sm:gap-0.5"
      >
        {ativas.length
          ? ativas.map((f) => (
              <span key={f.id} className="traco-loja" data-estado={estadoDoTraco(f.situacao)} />
            ))
          : Array.from({ length: 40 }, (_, i) => (
              <span key={i} className="traco-loja" data-estado="aguardando" />
            ))}
      </div>
      <p className="sr-only" role="status">
        {terminou
          ? `Busca concluída. ${texto}. ${plural(ofertas, "oferta encontrada", "ofertas encontradas")}.`
          : "Consultando as lojas."}
      </p>
      {!(terminou && fora.length > 0) ? (
        <p className="flex min-h-11 items-center text-[0.875rem] text-tinta-2" aria-hidden>
          {texto}
        </p>
      ) : (
        <details className="gaveta-detalhes w-full text-[0.875rem] sm:w-auto">
          <summary className="inline-flex min-h-11 cursor-pointer items-center gap-1 text-tinta-2 hover:text-tinta">
            {texto}, {plural(fora.length, "ficou de fora", "ficaram de fora")}
            <ChevronDown className="seta-detalhes size-4 transition-transform" aria-hidden />
          </summary>
          <ul className="mt-1 grid gap-x-6 gap-y-0.5 pb-1 text-tinta-2 sm:grid-cols-2">
            {fora.map((f) => (
              <li key={f.id}>
                <span className="font-medium text-tinta">{f.nome}</span> {MOTIVO[f.situacao]}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
