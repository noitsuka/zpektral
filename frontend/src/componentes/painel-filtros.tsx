"use client";

import { SlidersHorizontal, X } from "lucide-react";
import { useRef, useState, type ReactNode } from "react";

import {
  CONDICOES,
  FILTROS_PADRAO,
  FRETES,
  PAGAMENTOS,
  contarFiltrosAtivos,
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
    <fieldset className="border-b border-fio px-4 py-4 last:border-0 lg:px-0">
      <legend className="float-left mb-2 w-full text-[0.875rem] font-semibold">{titulo}</legend>
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
    <label className="flex min-h-11 cursor-pointer items-center gap-2.5 text-[0.9375rem] lg:min-h-8 lg:text-[0.875rem]">
      <input
        type={tipo}
        name={nome}
        checked={marcado}
        onChange={aoMudar}
        className="size-4 shrink-0 accent-[var(--acao)]"
      />
      <span className="min-w-0 flex-1">{children}</span>
      {contagem !== undefined && (
        <span className="numero text-[0.8125rem] text-tinta-3">{quantidade(contagem)}</span>
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
    <label className="flex min-w-0 flex-1 flex-col gap-1">
      <span className="text-[0.8125rem] text-tinta-2">{rotulo}</span>
      <span className="campo flex items-center gap-1.5 px-2.5">
        <span className="text-[0.8125rem] text-tinta-3" aria-hidden>
          R$
        </span>
        <input
          value={exibido}
          onChange={(e) => setRascunho(e.target.value.replace(/[^\d,.]/g, ""))}
          onBlur={confirmar}
          onKeyDown={(e) => e.key === "Enter" && confirmar()}
          inputMode="decimal"
          placeholder={dica}
          className="numero h-10 w-full min-w-0 bg-transparent text-base outline-none"
        />
      </span>
    </label>
  );
}

export function PainelFiltros({ filtros, facetas, onChange }: Props) {
  const [todasLojas, setTodasLojas] = useState(false);
  const aplicar = (alteracao: Partial<Filtros>) => onChange({ ...filtros, ...alteracao });

  const lojas = facetas?.lojas ?? [];
  const lojasVisiveis = todasLojas ? lojas : lojas.slice(0, 8);
  const voltagens = voltagemFazSentido(facetas) ? Object.entries(facetas?.voltagens ?? {}) : [];
  const condicoes = facetas?.condicoes ?? {};
  const temUsadoOuRecondicionado = (condicoes.usado ?? 0) + (condicoes.recondicionado ?? 0) > 0;
  const semPreco = (centavos: number | null | undefined, padrao: string) =>
    centavos != null ? reais(centavos).replace("R$", "").trim() : padrao;

  return (
    <div>
      <Secao titulo="Pagar com">
        {PAGAMENTOS.map((p) => (
          <Escolha
            key={p.valor}
            tipo="radio"
            nome="pagamento"
            marcado={filtros.pagamento === p.valor}
            aoMudar={() => aplicar({ pagamento: p.valor })}
          >
            {p.rotulo}
            <span className="block text-[0.8125rem] leading-tight text-tinta-3">{p.dica}</span>
          </Escolha>
        ))}
      </Secao>

      <Secao titulo="Total">
        <div className="flex gap-2">
          <CampoPreco
            rotulo="De"
            dica={semPreco(facetas?.preco_min, "mín.")}
            centavos={filtros.preco_min}
            aoConfirmar={(c) => aplicar({ preco_min: c })}
          />
          <CampoPreco
            rotulo="Até"
            dica={semPreco(facetas?.preco_max, "máx.")}
            centavos={filtros.preco_max}
            aoConfirmar={(c) => aplicar({ preco_max: c })}
          />
        </div>
      </Secao>

      <Secao titulo="Preço">
        <Escolha
          tipo="checkbox"
          nome="queda"
          marcado={filtros.queda_verificada}
          aoMudar={() => aplicar({ queda_verificada: !filtros.queda_verificada })}
        >
          Só com queda verificada
          <span className="block text-[0.8125rem] leading-tight text-tinta-3">
            abaixo do habitual da própria loja, nas buscas do Zpektral
          </span>
        </Escolha>
      </Secao>

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
              className="mt-1 min-h-11 text-[0.875rem] font-medium text-acao underline lg:min-h-8"
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
          <p className="mt-1 text-[0.8125rem] text-tinta-3">
            Lido do anúncio. Lojas que não informam a condição contam como novo.
          </p>
        </Secao>
      )}
    </div>
  );
}

function limpar(filtros: Filtros): Filtros {
  return { ...FILTROS_PADRAO, ordem: filtros.ordem, pagamento: filtros.pagamento };
}

export function BotaoFiltros({ visiveis, ...props }: Props & { visiveis: number }) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const [aberto, setAberto] = useState(false);
  const ativos = contarFiltrosAtivos(props.filtros);

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setAberto(true);
          dialogo.current?.showModal();
        }}
        aria-haspopup="dialog"
        className="botao botao-secundario flex-1 px-3 text-[0.9375rem]"
      >
        <SlidersHorizontal className="size-4" aria-hidden />
        Filtros
        {ativos > 0 && (
          <span className="numero grid min-w-5 place-items-center rounded-full bg-acao px-1 text-[0.75rem] text-sobre-acao">
            {ativos}
            <span className="sr-only"> ativos</span>
          </span>
        )}
      </button>
      <dialog
        ref={dialogo}
        aria-labelledby="titulo-filtros"
        onClose={() => setAberto(false)}
        onClick={(e) => e.target === dialogo.current && dialogo.current?.close()}
        className="dialogo-filtros"
      >
        {aberto && (
          <div className="flex max-h-[90dvh] flex-col">
            <div className="flex items-center justify-between border-b border-fio py-1 pr-1 pl-4">
              <h2 id="titulo-filtros" className="font-semibold">
                Filtros
              </h2>
              <button
                type="button"
                onClick={() => dialogo.current?.close()}
                className="grid size-11 place-items-center text-tinta-2 hover:text-tinta"
              >
                <X className="size-5" aria-hidden />
                <span className="sr-only">Fechar os filtros</span>
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
              <PainelFiltros {...props} />
            </div>
            <div className="flex items-center gap-3 border-t border-fio px-4 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
              <button
                type="button"
                disabled={!ativos}
                onClick={() => props.onChange(limpar(props.filtros))}
                className="botao botao-secundario"
              >
                Limpar
              </button>
              <button
                type="button"
                onClick={() => dialogo.current?.close()}
                className="botao botao-primario flex-1"
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
            className="inline-flex min-h-8 items-center gap-1.5 rounded-controle border border-acao bg-acao-suave px-2.5 text-[0.8125rem] font-medium text-acao hover:bg-etiqueta"
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
          onClick={() => onChange(limpar(filtros))}
          className="min-h-8 px-1.5 text-[0.8125rem] font-medium text-tinta-2 underline hover:text-tinta"
        >
          Limpar tudo
        </button>
      </li>
    </ul>
  );
}
