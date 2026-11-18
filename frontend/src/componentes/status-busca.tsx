import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";

import { plural } from "@/nucleo/formato";
import type { CelulaFonte, EstadoFonte } from "@/nucleo/transmissao";
import { lojasFora } from "@/nucleo/vitrine";

const MOTIVO: Partial<Record<EstadoFonte, string>> = {
  bloqueada: "recusou a consulta",
  tempo_esgotado: "não respondeu a tempo",
  erro: "respondeu com erro",
};

function contagem(fontes: CelulaFonte[]) {
  const ativas = fontes.filter((f) => f.situacao !== "desativada");
  const responderam = ativas.filter(
    (f) => f.situacao !== "aguardando" && f.situacao !== "catalogo",
  ).length;
  return { ativas, responderam };
}

export function LinhaProgresso({ fontes, terminou }: { fontes: CelulaFonte[]; terminou: boolean }) {
  const { ativas, responderam } = contagem(fontes);
  const fracao = ativas.length ? responderam / ativas.length : 0;
  return (
    <div
      role="progressbar"
      aria-label="Lojas que já responderam"
      aria-valuemin={0}
      aria-valuemax={ativas.length || 1}
      aria-valuenow={responderam}
      aria-hidden={terminou || undefined}
      data-terminou={terminou}
      className="linha-progresso"
    >
      <span style={{ transform: `scaleX(${Math.max(0.03, fracao)})` }} />
    </div>
  );
}

export function StatusBusca({
  fontes,
  terminou,
  ofertas,
  interrompida = false,
  acao,
}: {
  fontes: CelulaFonte[];
  terminou: boolean;
  ofertas: number;
  interrompida?: boolean;
  /** ação discreta no fim da linha; o texto encolhe para a linha não quebrar e empurrar a lista */
  acao?: ReactNode;
}) {
  const { ativas, responderam } = contagem(fontes);
  const fora = lojasFora(ativas);
  const lojas = interrompida
    ? "A consulta às lojas foi interrompida"
    : !ativas.length
      ? "Preparando a busca"
      : terminou
        ? fora.length
          ? `${responderam - fora.length} de ${plural(ativas.length, "loja respondeu", "lojas responderam")}`
          : plural(ativas.length, "loja consultada", "lojas consultadas")
        : `Consultando ${responderam} de ${plural(ativas.length, "loja", "lojas")}`;
  // Terminada a busca, a contagem de ofertas e a de lojas dividem a mesma linha.
  const texto =
    terminou && !interrompida && ativas.length
      ? `${plural(ofertas, "oferta", "ofertas")} · ${lojas}`
      : lojas;

  return (
    <div className="numero flex items-start gap-x-4 text-[0.875rem] text-apagado">
      <p className="sr-only" role="status">
        {terminou ? `Busca concluída. ${texto}.` : "Consultando as lojas."}
      </p>
      {terminou && fora.length > 0 ? (
        <details className="gaveta-detalhes min-w-0 flex-1">
          <summary className="botao-texto max-w-full cursor-pointer">
            <span className="min-w-0 truncate">{texto}</span>
            <span className="sr-only">, ver as que ficaram de fora</span>
            <ChevronDown className="chevron size-4" aria-hidden />
          </summary>
          <ul className="mt-1 grid gap-x-8 gap-y-0.5 pb-2 sm:grid-cols-2 lg:grid-cols-3">
            {fora.map((f) => (
              <li key={f.id}>
                <span className="text-tinta">{f.nome}</span> {MOTIVO[f.situacao]}
              </li>
            ))}
          </ul>
        </details>
      ) : (
        <p className="flex min-h-9 min-w-0 flex-1 items-center" aria-hidden>
          <span className="truncate">{texto}</span>
        </p>
      )}
      {acao}
    </div>
  );
}
