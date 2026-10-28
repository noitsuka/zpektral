"use client";

import Link from "next/link";

import { MARCA } from "@/nucleo/marca";
import { FEIXE, arestasPrisma, formaDoSimbolo, pontosPrisma } from "@/nucleo/simbolo";
import { REPOUSO, type Espectro } from "@/nucleo/espectro";

type PropsSimbolo = {
  tamanho?: number;
  espectro?: Espectro;
  recorte?: boolean;
  className?: string;
};

const RECORTE = { x: 5.4, y: 3.4, w: 21.2, h: 25.3 };

export function Simbolo({
  tamanho = 24,
  espectro = REPOUSO,
  recorte = false,
  className = "",
}: PropsSimbolo) {
  const { linhas } = formaDoSimbolo(REPOUSO);
  const atuais = formaDoSimbolo(espectro).linhas;
  return (
    <svg
      viewBox={recorte ? `${RECORTE.x} ${RECORTE.y} ${RECORTE.w} ${RECORTE.h}` : "0 0 32 32"}
      width={recorte ? (tamanho * RECORTE.w) / RECORTE.h : tamanho}
      height={tamanho}
      aria-hidden
      className={`overflow-visible ${className}`}
    >
      <rect x={FEIXE.x} y={FEIXE.y} width={FEIXE.w} height={FEIXE.h} className="fill-tinta" />
      <polygon points={pontosPrisma} className="fill-tinta" fillOpacity={0.35} />
      <path d={arestasPrisma} className="fill-none stroke-tinta" strokeWidth={0.7} />
      {linhas.map((l, i) => (
        <rect
          key={i}
          x={l.x}
          y={l.y}
          width={l.w}
          height={l.h}
          className={l.dourada ? "fill-ouro" : "fill-tinta/75"}
          style={{ transformBox: "fill-box", transform: `scaleX(${atuais[i].w / l.w})` }}
        />
      ))}
    </svg>
  );
}

export function Logo({
  compacto = false,
  grande = false,
  espectro,
}: {
  compacto?: boolean;
  grande?: boolean;
  espectro?: Espectro;
}) {
  return (
    <Link
      href="/"
      className={`inline-flex items-baseline font-semibold tracking-[-0.02em] [font-stretch:118%] ${
        grande ? "text-[26px]" : "text-[22px]"
      }`}
      aria-label={`${MARCA.nome}, início`}
    >
      <Simbolo
        recorte
        tamanho={grande ? 29 : 25}
        espectro={espectro}
        className="relative top-[0.2em] mr-[0.05em]"
      />
      <span aria-hidden className={compacto ? "hidden lg:inline" : ""}>
        {MARCA.nome.slice(1)}
      </span>
    </Link>
  );
}
