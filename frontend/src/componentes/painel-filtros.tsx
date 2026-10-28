"use client";

import { SlidersHorizontal, X } from "lucide-react";
import { useEffect, useId, useRef, useState, useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";

import {
  CONDICOES,
  FILTROS_PADRAO,
  FRETES,
  contarFiltrosAtivos,
  voltagemFazSentido,
} from "@/nucleo/filtros";
import { quantidade, reais } from "@/nucleo/formato";
import type { Condicao, Facetas, Filtros } from "@/nucleo/tipos";

type Props = {
  filtros: Filtros;
  facetas: Facetas | null;
  onChange: (proximo: Filtros) => void;
};

const ROTULO_VOLTAGEM: Record<string, string> = {
  "110V": "110V",
  "220V": "220V",
  bivolt: "Bivolt",
};

function Secao({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <fieldset className="border-b border-traco px-4 py-4 last:border-0">
      <legend className="rotulo float-left mb-3 w-full text-tenue">{titulo}</legend>
      <div className="clear-both">{children}</div>
    </fieldset>
  );
}

function Opcao({
  ativo,
  onClick,
  children,
}: {
  ativo: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={ativo}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-peca border px-2.5 py-1.5 text-xs transition-colors ${
        ativo
          ? "border-ouro/60 bg-ouro-suave text-ouro"
          : "border-traco text-apagado hover:border-tinta/25 hover:text-tinta"
      }`}
    >
      {children}
    </button>
  );
}

function Contagem({ n }: { n: number }) {
  return <span className="font-mono text-[10px] tabular-nums opacity-60">{quantidade(n)}</span>;
}

function alternar<T>(lista: T[], item: T): T[] {
  return lista.includes(item) ? lista.filter((v) => v !== item) : [...lista, item];
}

function reaisParaCentavos(bruto: string): number | null {
  const n = Number(bruto.replace(/\./g, "").replace(",", "."));
  return bruto.trim() && Number.isFinite(n) && n >= 0 ? Math.round(n * 100) : null;
}

function CampoPreco({
  rotulo,
  dica,
  centavos,
  aoConfirmar,
}: {
  rotulo: string;
  dica: string;
  centavos: number | null;
  aoConfirmar: (centavos: number | null) => void;
}) {
  const [rascunho, setRascunho] = useState<string | null>(null);
  const exibido = rascunho ?? (centavos === null ? "" : String(centavos / 100).replace(".", ","));
  const confirmar = () => {
    if (rascunho === null) return;
    aoConfirmar(reaisParaCentavos(rascunho));
    setRascunho(null);
  };
  return (
    <label className="flex min-w-0 flex-1 flex-col gap-1">
      <span className="text-[11px] text-tenue">{rotulo}</span>
      <span className="flex items-center gap-1.5 rounded-peca border border-traco px-2.5 focus-within:border-ouro/50">
        <span className="text-xs text-tenue">R$</span>
        <input
          value={exibido}
          onChange={(e) => setRascunho(e.target.value.replace(/[^\d,.]/g, ""))}
          onBlur={confirmar}
          onKeyDown={(e) => e.key === "Enter" && confirmar()}
          inputMode="decimal"
          placeholder={dica}
          className="h-9 w-full min-w-0 bg-transparent font-mono text-[13px] tabular-nums outline-none placeholder:text-tenue/70"
        />
      </span>
    </label>
  );
}

function PainelFiltros({ filtros, facetas, onChange }: Props) {
  const [todasLojas, setTodasLojas] = useState(false);
  const aplicar = (alteracao: Partial<Filtros>) => onChange({ ...filtros, ...alteracao });

  const lojas = facetas?.lojas ?? [];
  const lojasVisiveis = todasLojas ? lojas : lojas.slice(0, 8);
  const voltagens = voltagemFazSentido(facetas) ? Object.entries(facetas?.voltagens ?? {}) : [];
  const condicoes = facetas?.condicoes ?? {};
  const temUsadoOuRecondicionado = (condicoes.usado ?? 0) + (condicoes.recondicionado ?? 0) > 0;
  const fretes = FRETES.filter(
    (s) =>
      s.valor === "todos" ||
      filtros.frete === s.valor ||
      (s.valor === "calculado" && (facetas?.com_total_exato ?? 0) > 0) ||
      (s.valor === "gratis" && (facetas?.frete_gratis ?? 0) > 0),
  );

  return (
    <div className="text-sm">
      <Secao titulo="Total">
        <div className="flex gap-2">
          <CampoPreco
            rotulo="De"
            dica={
              facetas?.preco_min != null ? reais(facetas.preco_min).replace("R$", "").trim() : "mín"
            }
            centavos={filtros.preco_min}
            aoConfirmar={(c) => aplicar({ preco_min: c })}
          />
          <CampoPreco
            rotulo="Até"
            dica={
              facetas?.preco_max != null ? reais(facetas.preco_max).replace("R$", "").trim() : "máx"
            }
            centavos={filtros.preco_max}
            aoConfirmar={(c) => aplicar({ preco_max: c })}
          />
        </div>
      </Secao>

      {fretes.length > 1 && (
        <Secao titulo="Frete">
          <div className="flex flex-wrap gap-1.5">
            {fretes.map((s) => (
              <Opcao
                key={s.valor}
                ativo={filtros.frete === s.valor}
                onClick={() => aplicar({ frete: s.valor })}
              >
                {s.rotulo}
                {s.valor === "calculado" && facetas ? (
                  <Contagem n={facetas.com_total_exato} />
                ) : null}
                {s.valor === "gratis" && facetas ? <Contagem n={facetas.frete_gratis} /> : null}
              </Opcao>
            ))}
          </div>
        </Secao>
      )}

      {(lojas.length > 1 || filtros.lojas.length > 0) && (
        <Secao titulo="Lojas">
          <ul className="grid gap-0.5">
            {lojasVisiveis.map((s) => (
              <li key={s.id}>
                <label className="flex cursor-pointer items-center gap-2.5 rounded-peca px-1 py-1.5 text-apagado hover:bg-white/[0.03] hover:text-tinta">
                  <input
                    type="checkbox"
                    checked={filtros.lojas.includes(s.id)}
                    onChange={() => aplicar({ lojas: alternar(filtros.lojas, s.id) })}
                    className="size-3.5 accent-[var(--color-ouro)]"
                  />
                  <span className="truncate">{s.nome}</span>
                  <span className="ml-auto">
                    <Contagem n={s.quantidade} />
                  </span>
                </label>
              </li>
            ))}
          </ul>
          {lojas.length > 8 && (
            <button
              type="button"
              onClick={() => setTodasLojas((v) => !v)}
              className="mt-2 text-xs text-tenue underline-offset-4 hover:text-tinta hover:underline"
            >
              {todasLojas ? "Mostrar menos" : `Ver as ${lojas.length} lojas`}
            </button>
          )}
        </Secao>
      )}

      {(voltagens.length > 0 || filtros.voltagem.length > 0) && (
        <Secao titulo="Voltagem">
          <div className="flex flex-wrap gap-1.5">
            {voltagens.map(([v, n]) => (
              <Opcao
                key={v}
                ativo={filtros.voltagem.includes(v)}
                onClick={() => aplicar({ voltagem: alternar(filtros.voltagem, v) })}
              >
                {ROTULO_VOLTAGEM[v] ?? v}
                <Contagem n={n} />
              </Opcao>
            ))}
          </div>
          {filtros.voltagem.length > 0 && (
            <label className="mt-3 flex cursor-pointer items-center gap-2 text-xs text-apagado">
              <input
                type="checkbox"
                checked={filtros.voltagem_estrita}
                onChange={(e) => aplicar({ voltagem_estrita: e.target.checked })}
                className="size-3.5 accent-[var(--color-ouro)]"
              />
              Esconder anúncios que não dizem a voltagem
            </label>
          )}
        </Secao>
      )}

      {(temUsadoOuRecondicionado || filtros.condicao.join() !== FILTROS_PADRAO.condicao.join()) && (
        <Secao titulo="Condição">
          <div className="flex flex-wrap gap-1.5">
            {CONDICOES.map((c) => (
              <Opcao
                key={c.valor}
                ativo={filtros.condicao.includes(c.valor)}
                onClick={() => {
                  const proximo = alternar<Condicao>(filtros.condicao, c.valor);
                  if (proximo.length) aplicar({ condicao: proximo });
                }}
              >
                {c.rotulo}
                {condicoes[c.valor] ? <Contagem n={condicoes[c.valor]} /> : null}
              </Opcao>
            ))}
          </div>
          <p className="mt-2 text-[11px] leading-relaxed text-tenue">
            Lido do anúncio. Lojas que não informam a condição contam como novo.
          </p>
        </Secao>
      )}
    </div>
  );
}

const CONSULTA_CELULAR = "(max-width: 639px)";

function assinarCelular(aviso: () => void) {
  const consulta = window.matchMedia(CONSULTA_CELULAR);
  consulta.addEventListener("change", aviso);
  return () => consulta.removeEventListener("change", aviso);
}

function useCelular(): boolean {
  return useSyncExternalStore(
    assinarCelular,
    () => window.matchMedia(CONSULTA_CELULAR).matches,
    () => false,
  );
}

export function BotaoFiltros(props: Props) {
  const [aberto, setAberto] = useState(false);
  const raiz = useRef<HTMLDivElement>(null);
  const painel = useRef<HTMLDivElement>(null);
  const idPainel = useId();
  const celular = useCelular();
  const ativos = contarFiltrosAtivos(props.filtros);

  useEffect(() => {
    if (!aberto) return;
    const fecharTecla = (e: KeyboardEvent) => e.key === "Escape" && setAberto(false);
    const fecharFora = (e: PointerEvent) => {
      const alvo = e.target as Node;
      if (raiz.current?.contains(alvo) || painel.current?.contains(alvo)) return;
      setAberto(false);
    };
    window.addEventListener("keydown", fecharTecla);
    window.addEventListener("pointerdown", fecharFora);
    return () => {
      window.removeEventListener("keydown", fecharTecla);
      window.removeEventListener("pointerdown", fecharFora);
    };
  }, [aberto]);

  useEffect(() => {
    if (!aberto || !celular) return;
    const anterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = anterior;
    };
  }, [aberto, celular]);

  const conteudo = (
    <div
      ref={painel}
      id={idPainel}
      role="dialog"
      aria-modal={celular || undefined}
      aria-label="Filtros"
      className={
        celular
          ? "fixed inset-x-0 bottom-0 z-50 flex max-h-[88dvh] animate-surgir flex-col rounded-t-quadro border-t border-traco bg-painel pb-[env(safe-area-inset-bottom)] shadow-2xl"
          : "absolute top-full right-0 z-50 mt-2 flex max-h-[min(36rem,calc(100dvh-9rem))] w-[22rem] animate-aparecer flex-col rounded-quadro border border-traco bg-painel shadow-2xl"
      }
    >
      <div className="flex items-center justify-between border-b border-traco px-4 py-3">
        <p className="text-sm font-semibold">Filtros</p>
        <button
          type="button"
          onClick={() => setAberto(false)}
          aria-label="Fechar filtros"
          className="rounded-peca p-1 text-apagado hover:text-tinta"
        >
          <X className="size-4" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <PainelFiltros {...props} />
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-traco px-4 py-3">
        <button
          type="button"
          disabled={!ativos}
          onClick={() =>
            props.onChange({
              ...FILTROS_PADRAO,
              ordem: props.filtros.ordem,
              pagamento: props.filtros.pagamento,
            })
          }
          className="text-xs text-apagado underline-offset-4 hover:text-tinta hover:underline disabled:opacity-40 disabled:hover:no-underline"
        >
          Limpar filtros
        </button>
        <button
          type="button"
          onClick={() => setAberto(false)}
          className="rounded-peca bg-ouro px-4 py-2 text-xs font-semibold text-fundo hover:brightness-110"
        >
          Ver resultados
        </button>
      </div>
    </div>
  );

  return (
    <div ref={raiz} className="relative">
      <button
        type="button"
        onClick={() => setAberto((v) => !v)}
        aria-expanded={aberto}
        aria-controls={idPainel}
        className={`inline-flex h-9 items-center gap-2 rounded-peca border px-3 text-xs font-medium transition-colors ${
          aberto || ativos
            ? "border-ouro/50 bg-ouro-suave text-ouro"
            : "border-traco text-tinta hover:border-tinta/25"
        }`}
      >
        <SlidersHorizontal className="size-3.5" aria-hidden />
        Filtros
        {ativos > 0 && (
          <span className="grid size-4 place-items-center rounded-full bg-ouro font-mono text-[10px] text-fundo">
            {ativos}
          </span>
        )}
      </button>

      {aberto &&
        (celular
          ? createPortal(
              <>
                <div
                  aria-hidden
                  onClick={() => setAberto(false)}
                  className="fixed inset-0 z-40 animate-aparecer bg-black/70"
                />
                {conteudo}
              </>,
              document.body,
            )
          : conteudo)}
    </div>
  );
}

export function ChipsFiltros({ filtros, facetas, onChange }: Props) {
  const nomeDaLoja = new Map((facetas?.lojas ?? []).map((l) => [l.id, l.nome]));
  const chips: { chave: string; rotulo: string; remover: Partial<Filtros> }[] = [];
  if (filtros.preco_min !== null)
    chips.push({
      chave: "min",
      rotulo: `De ${reais(filtros.preco_min)}`,
      remover: { preco_min: null },
    });
  if (filtros.preco_max !== null)
    chips.push({
      chave: "max",
      rotulo: `Até ${reais(filtros.preco_max)}`,
      remover: { preco_max: null },
    });
  if (filtros.frete !== "todos")
    chips.push({
      chave: "frete",
      rotulo: FRETES.find((s) => s.valor === filtros.frete)?.rotulo ?? filtros.frete,
      remover: { frete: "todos" },
    });
  for (const id of filtros.lojas)
    chips.push({
      chave: `loja-${id}`,
      rotulo: nomeDaLoja.get(id) ?? id,
      remover: { lojas: filtros.lojas.filter((l) => l !== id) },
    });
  for (const v of filtros.voltagem)
    chips.push({
      chave: `volt-${v}`,
      rotulo: ROTULO_VOLTAGEM[v] ?? v,
      remover: { voltagem: filtros.voltagem.filter((x) => x !== v) },
    });
  if (filtros.condicao.join() !== FILTROS_PADRAO.condicao.join())
    chips.push({
      chave: "condicao",
      rotulo: filtros.condicao
        .map((c) => CONDICOES.find((x) => x.valor === c)?.rotulo ?? c)
        .join(", "),
      remover: { condicao: FILTROS_PADRAO.condicao },
    });

  if (!chips.length) return null;
  return (
    <ul className="flex flex-wrap items-center gap-1.5" aria-label="Filtros ativos">
      {chips.map((c) => (
        <li key={c.chave}>
          <button
            type="button"
            onClick={() => onChange({ ...filtros, ...c.remover })}
            className="inline-flex items-center gap-1.5 rounded-peca border border-ouro/40 bg-ouro-suave px-2 py-1 text-xs text-ouro hover:border-ouro/70"
          >
            {c.rotulo}
            <X className="size-3" aria-hidden />
            <span className="sr-only">remover filtro</span>
          </button>
        </li>
      ))}
      <li>
        <button
          type="button"
          onClick={() =>
            onChange({ ...FILTROS_PADRAO, ordem: filtros.ordem, pagamento: filtros.pagamento })
          }
          className="px-1 text-xs text-tenue underline-offset-4 hover:text-tinta hover:underline"
        >
          Limpar
        </button>
      </li>
    </ul>
  );
}
