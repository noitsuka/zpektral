"use client";

import { useState, type KeyboardEvent, type PointerEvent } from "react";

import { diaAbreviado, reais } from "@/nucleo/formato";
import { mediana } from "@/nucleo/referencia";
import { janelasDisponiveis, recortar, trechos } from "@/nucleo/tendencia";
import type { PontoHistorico } from "@/nucleo/tipos";

const LARGURA = 320;
const ALTURA = 112;
const MARGEM_Y = 10;
const MS_POR_DIA = 86_400_000;

const tempo = (dia: string) => Date.parse(`${dia}T12:00:00Z`);

export function GraficoPreco({
  pontos,
  atual,
  hoje,
}: {
  pontos: PontoHistorico[];
  atual: number;
  hoje: string;
}) {
  const completos = [...pontos.filter((p) => p.dia < hoje), { dia: hoje, preco: atual }];
  const janelas = janelasDisponiveis(completos, hoje);
  const [escolhida, setEscolhida] = useState<number | null>(null);
  const janela = escolhida ?? janelas.at(-1) ?? 7;
  const visiveis = recortar(completos, hoje, janela);
  const [indice, setIndice] = useState<number | null>(null);
  const selecionado = visiveis[Math.min(indice ?? visiveis.length - 1, visiveis.length - 1)];

  const passados = completos.filter((p) => p.dia < hoje).map((p) => p.preco);
  const habitual = passados.length >= 3 ? mediana(passados) : null;
  const precos = visiveis.map((p) => p.preco);
  const menor = Math.min(...precos);
  const maior = Math.max(...precos);
  const piso = Math.min(menor, habitual ?? menor);
  const teto = Math.max(maior, habitual ?? maior);
  const faixa = teto - piso || teto * 0.1 || 1;
  const inicio = tempo(hoje) - (janela - 1) * MS_POR_DIA;
  const x = (dia: string) => ((tempo(dia) - inicio) / ((janela - 1) * MS_POR_DIA || 1)) * LARGURA;
  const y = (preco: number) =>
    MARGEM_Y + (1 - (preco - piso + faixa * 0.08) / (faixa * 1.16)) * (ALTURA - 2 * MARGEM_Y);

  function escolherPeloPonteiro(evento: PointerEvent<SVGSVGElement>) {
    const caixa = evento.currentTarget.getBoundingClientRect();
    const alvo = ((evento.clientX - caixa.left) / caixa.width) * LARGURA;
    let melhor = 0;
    visiveis.forEach((p, i) => {
      if (Math.abs(x(p.dia) - alvo) < Math.abs(x(visiveis[melhor].dia) - alvo)) melhor = i;
    });
    setIndice(melhor);
  }

  function teclar(evento: KeyboardEvent<HTMLDivElement>) {
    const atualIndice = indice ?? visiveis.length - 1;
    const proximo: Record<string, number> = {
      ArrowLeft: atualIndice - 1,
      ArrowDown: atualIndice - 1,
      ArrowRight: atualIndice + 1,
      ArrowUp: atualIndice + 1,
      Home: 0,
      End: visiveis.length - 1,
    };
    if (!(evento.key in proximo)) return;
    evento.preventDefault();
    setIndice(Math.max(0, Math.min(visiveis.length - 1, proximo[evento.key])));
  }

  const legenda = (p: PontoHistorico) =>
    `${p.dia === hoje ? "Hoje" : diaAbreviado(p.dia)}: ${reais(p.preco)}`;

  return (
    <figure>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <figcaption className="rotulo-campo">Preço nesta loja</figcaption>
        {janelas.length > 1 && (
          <div role="group" aria-label="Período" className="flex gap-1">
            {janelas.map((j) => (
              <button
                key={j}
                type="button"
                aria-pressed={j === janela}
                onClick={() => {
                  setEscolhida(j);
                  setIndice(null);
                }}
                className={`min-h-8 min-w-11 rounded-controle border px-2 text-[0.8125rem] font-medium ${
                  j === janela
                    ? "border-tinta bg-tinta text-etiqueta"
                    : "border-fio text-tinta-2 hover:border-borda hover:text-tinta"
                }`}
              >
                {j} dias
              </button>
            ))}
          </div>
        )}
      </div>

      <p className="numero mt-2 text-[0.9375rem] font-semibold" aria-live="polite">
        {legenda(selecionado)}
      </p>

      <div
        role="slider"
        tabIndex={0}
        aria-label={`Preço por dia nos últimos ${janela} dias`}
        aria-valuemin={0}
        aria-valuemax={visiveis.length - 1}
        aria-valuenow={visiveis.indexOf(selecionado)}
        aria-valuetext={legenda(selecionado)}
        onKeyDown={teclar}
        className="mt-1 rounded-controle"
      >
        <svg
          viewBox={`0 0 ${LARGURA} ${ALTURA}`}
          preserveAspectRatio="none"
          className="h-28 w-full touch-none overflow-visible"
          aria-hidden
          onPointerMove={escolherPeloPonteiro}
          onPointerDown={escolherPeloPonteiro}
        >
          <line
            x1={0}
            x2={LARGURA}
            y1={ALTURA}
            y2={ALTURA}
            className="stroke-fio"
            vectorEffect="non-scaling-stroke"
          />
          {habitual !== null && (
            <line
              x1={0}
              x2={LARGURA}
              y1={y(habitual)}
              y2={y(habitual)}
              className="stroke-tinta-3"
              strokeDasharray="4 4"
              vectorEffect="non-scaling-stroke"
            />
          )}
          <line
            x1={x(selecionado.dia)}
            x2={x(selecionado.dia)}
            y1={0}
            y2={ALTURA}
            className="stroke-borda"
            vectorEffect="non-scaling-stroke"
          />
          {trechos(visiveis).map((trecho) =>
            trecho.length > 1 ? (
              <polyline
                key={trecho[0].dia}
                points={trecho.map((p) => `${x(p.dia)},${y(p.preco)}`).join(" ")}
                className="fill-none stroke-tinta"
                strokeWidth={1.75}
                strokeLinejoin="round"
                vectorEffect="non-scaling-stroke"
              />
            ) : null,
          )}
          {visiveis.map((p) => (
            <line
              key={p.dia}
              x1={x(p.dia)}
              x2={x(p.dia)}
              y1={y(p.preco)}
              y2={y(p.preco)}
              strokeLinecap="round"
              strokeWidth={p === selecionado ? 9 : p.dia === hoje ? 7 : 4}
              className={p.dia === hoje || p === selecionado ? "stroke-acao" : "stroke-tinta"}
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </svg>
      </div>

      <div className="mt-1.5 flex justify-between text-[0.75rem] text-tinta-3">
        <span>{diaAbreviado(new Date(inicio).toISOString().slice(0, 10))}</span>
        <span>hoje</span>
      </div>
      <p className="numero mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[0.8125rem] text-tinta-2">
        <span>Menor {reais(menor)}</span>
        <span>Maior {reais(maior)}</span>
        {habitual !== null && (
          <span>
            <span
              aria-hidden
              className="mr-1 inline-block w-4 border-t border-dashed border-tinta-3 align-middle"
            />
            Habitual {reais(Math.round(habitual))}
          </span>
        )}
      </p>
      <p className="mt-1 text-[0.75rem] text-tinta-3">
        Dias sem consulta ficam sem linha. Preços vistos nas buscas feitas no Zpektral.
      </p>
    </figure>
  );
}
