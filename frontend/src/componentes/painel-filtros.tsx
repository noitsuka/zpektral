"use client";

import { SlidersHorizontal, X } from "lucide-react";
import { useRef, useState, type ReactNode } from "react";

import {
  CONDICOES,
  FILTROS_PADRAO,
  FRETES,
  contarFiltrosAtivos,
  limparFiltros,
  voltagemFazSentido,
} from "@/nucleo/filtros";
import { plural, quantidade, reais } from "@/nucleo/formato";
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
    <fieldset className="border-t border-traco px-5 py-5 first:border-t-0">
      <legend className="float-left mb-2 w-full text-[0.9375rem] font-medium">{titulo}</legend>
      <div className="clear-both">{children}</div>
    </fieldset>
  );
}

function Escolha({
  tipo,
  nome,
  marcado,
  aoMudar,
  children,
  contagem,
}: {
  tipo: "radio" | "checkbox";
  nome: string;
  marcado: boolean;
  aoMudar: () => void;
  children: ReactNode;
  contagem?: number;
}) {
  return (
    <label className="flex min-h-10 cursor-pointer items-center gap-3 text-[0.9375rem] text-apagado transition-colors hover:text-tinta has-checked:text-tinta pointer-coarse:min-h-11">
      <input
        type={tipo}
        name={nome}
        checked={marcado}
        onChange={aoMudar}
        className="size-4 shrink-0 accent-[var(--color-ouro)]"
      />
      <span className="min-w-0 flex-1">{children}</span>
      {contagem !== undefined && (
        <span className="font-mono text-[0.8125rem] text-tenue tabular-nums">
          {quantidade(contagem)}
        </span>
      )}
    </label>
  );
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
    <label className="flex min-w-0 flex-1 flex-col gap-1.5">
      <span className="text-[0.8125rem] text-apagado">{rotulo}</span>
      <span className="campo flex items-center gap-1.5 px-3">
        <span className="text-[0.8125rem] text-tenue" aria-hidden>
          R$
        </span>
        <input
          value={exibido}
          onChange={(e) => setRascunho(e.target.value.replace(/[^\d,.]/g, ""))}
          onBlur={confirmar}
          onKeyDown={(e) => e.key === "Enter" && confirmar()}
          inputMode="decimal"
          placeholder={dica}
          className="h-11 w-full min-w-0 bg-transparent font-mono text-[0.9375rem] tabular-nums outline-none placeholder:font-sans"
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

  return (
    <div>
      <Secao titulo="Frete">
        {FRETES.map((s) => (
          <Escolha
            key={s.valor}
            tipo="radio"
            nome="frete"
            marcado={filtros.frete === s.valor}
            aoMudar={() => aplicar({ frete: s.valor })}
            contagem={
              s.valor === "calculado"
                ? facetas?.com_total_exato
                : s.valor === "gratis"
                  ? facetas?.frete_gratis
                  : undefined
            }
          >
            {s.rotulo}
          </Escolha>
        ))}
      </Secao>

      <Secao titulo="Total">
        <div className="flex gap-3">
          <CampoPreco
            rotulo="De"
            dica="mín."
            centavos={filtros.preco_min}
            aoConfirmar={(c) => aplicar({ preco_min: c })}
          />
          <CampoPreco
            rotulo="Até"
            dica="máx."
            centavos={filtros.preco_max}
            aoConfirmar={(c) => aplicar({ preco_max: c })}
          />
        </div>
        {/* fora do campo: valor no placeholder parece filtro já aplicado e não cabe na largura */}
        {facetas?.preco_min != null && facetas.preco_max != null && (
          <p className="mt-2 text-[0.8125rem] text-apagado">
            Nesta busca, de <span className="numero">{reais(facetas.preco_min)}</span> a{" "}
            <span className="numero">{reais(facetas.preco_max)}</span>
          </p>
        )}
      </Secao>

      <Secao titulo="Preço">
        <Escolha
          tipo="checkbox"
          nome="queda"
          marcado={filtros.queda_verificada}
          aoMudar={() => aplicar({ queda_verificada: !filtros.queda_verificada })}
        >
          Só com queda verificada
          <span className="block text-[0.8125rem] leading-snug text-tenue">
            abaixo do habitual da própria loja, nas buscas do Zpektral
          </span>
        </Escolha>
      </Secao>

      {(lojas.length > 1 || filtros.lojas.length > 0) && (
        <Secao titulo="Lojas">
          {lojasVisiveis.map((s) => (
            <Escolha
              key={s.id}
              tipo="checkbox"
              nome="lojas"
              marcado={filtros.lojas.includes(s.id)}
              aoMudar={() => aplicar({ lojas: alternar(filtros.lojas, s.id) })}
              contagem={s.quantidade}
            >
              <span className="block truncate">{s.nome}</span>
            </Escolha>
          ))}
          {lojas.length > 8 && (
            <button
              type="button"
              onClick={() => setTodasLojas((v) => !v)}
              className="botao-texto mt-1 text-ouro underline decoration-ouro/40 hover:text-ouro"
            >
              {todasLojas ? "Mostrar menos" : `Ver as ${lojas.length} lojas`}
            </button>
          )}
        </Secao>
      )}

      {(voltagens.length > 0 || filtros.voltagem.length > 0) && (
        <Secao titulo="Voltagem">
          {voltagens.map(([v, n]) => (
            <Escolha
              key={v}
              tipo="checkbox"
              nome="voltagem"
              marcado={filtros.voltagem.includes(v)}
              aoMudar={() => aplicar({ voltagem: alternar(filtros.voltagem, v) })}
              contagem={n}
            >
              {ROTULO_VOLTAGEM[v] ?? v}
            </Escolha>
          ))}
          {filtros.voltagem.length > 0 && (
            <Escolha
              tipo="checkbox"
              nome="voltagem_estrita"
              marcado={filtros.voltagem_estrita}
              aoMudar={() => aplicar({ voltagem_estrita: !filtros.voltagem_estrita })}
            >
              Esconder anúncios que não dizem a voltagem
            </Escolha>
          )}
        </Secao>
      )}

      {(temUsadoOuRecondicionado || filtros.condicao.join() !== FILTROS_PADRAO.condicao.join()) && (
        <Secao titulo="Condição">
          {CONDICOES.map((c) => (
            <Escolha
              key={c.valor}
              tipo="checkbox"
              nome="condicao"
              marcado={filtros.condicao.includes(c.valor)}
              aoMudar={() => {
                const proximo = alternar<Condicao>(filtros.condicao, c.valor);
                if (proximo.length) aplicar({ condicao: proximo });
              }}
              contagem={condicoes[c.valor]}
            >
              {c.rotulo}
            </Escolha>
          ))}
          <p className="mt-1 text-[0.8125rem] text-tenue">
            Lido do anúncio. Lojas que não informam a condição contam como novo.
          </p>
        </Secao>
      )}
    </div>
  );
}

export function BotaoFiltros({ visiveis, ...props }: Props & { visiveis: number }) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const botao = useRef<HTMLButtonElement>(null);
  const [aberto, setAberto] = useState(false);
  const ativos = contarFiltrosAtivos(props.filtros);

  return (
    <>
      <button
        ref={botao}
        type="button"
        onClick={() => {
          setAberto(true);
          dialogo.current?.showModal();
        }}
        aria-haspopup="dialog"
        className={`botao botao-linha shrink-0 gap-1.5 px-2.5 text-[0.875rem] sm:gap-2 sm:px-3.5 ${
          ativos ? "border-ouro/50 text-ouro" : ""
        }`}
      >
        <SlidersHorizontal className="size-4" aria-hidden />
        Filtros
        {ativos > 0 && (
          <span className="grid min-w-5 place-items-center rounded-full bg-ouro px-1 font-mono text-[0.75rem] leading-5 text-fundo">
            {ativos}
            <span className="sr-only"> ativos</span>
          </span>
        )}
      </button>
      <dialog
        ref={dialogo}
        aria-labelledby="titulo-filtros"
        onClose={() => {
          setAberto(false);
          botao.current?.focus();
        }}
        onClick={(e) => e.target === dialogo.current && dialogo.current?.close()}
        className="dialogo-filtros"
      >
        {aberto && (
          <div className="flex h-full max-h-[inherit] flex-col">
            <div className="flex items-center justify-between py-2 pr-2 pl-5">
              <h2 id="titulo-filtros" className="text-[1.0625rem] font-semibold">
                Filtros
              </h2>
              <button
                type="button"
                onClick={() => dialogo.current?.close()}
                className="grid size-11 place-items-center rounded-quadro text-apagado transition-colors hover:text-tinta"
              >
                <X className="size-5" aria-hidden />
                <span className="sr-only">Fechar os filtros</span>
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain border-t border-traco">
              <PainelFiltros {...props} />
            </div>
            <div className="flex items-center gap-3 border-t border-traco px-5 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
              <button
                type="button"
                disabled={!ativos}
                onClick={() => props.onChange(limparFiltros(props.filtros))}
                className="botao botao-linha"
              >
                Limpar
              </button>
              <button
                type="button"
                onClick={() => dialogo.current?.close()}
                className="botao botao-ouro flex-1"
              >
                Ver {plural(visiveis, "oferta", "ofertas")}
              </button>
            </div>
          </div>
        )}
      </dialog>
    </>
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
  if (filtros.queda_verificada)
    chips.push({
      chave: "queda",
      rotulo: "Queda verificada",
      remover: { queda_verificada: false },
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
            className="inline-flex min-h-8 items-center gap-1.5 rounded-quadro border border-ouro/40 bg-ouro-suave px-2.5 text-[0.8125rem] text-ouro transition-colors hover:border-ouro/80 pointer-coarse:min-h-11"
          >
            {c.rotulo}
            <X className="size-3.5" aria-hidden />
            <span className="sr-only">, remover filtro</span>
          </button>
        </li>
      ))}
      <li>
        <button
          type="button"
          onClick={() => onChange(limparFiltros(filtros))}
          className="botao-texto min-h-8 px-1.5 text-[0.8125rem] pointer-coarse:min-h-11"
        >
          Limpar tudo
        </button>
      </li>
    </ul>
  );
}
