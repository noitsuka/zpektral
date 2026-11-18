"use client";

import { useCallback, useLayoutEffect, useRef, useSyncExternalStore, type RefObject } from "react";

import { mesmaOrdem } from "@/nucleo/ordem-estavel";

type Vistos = { chave: string; ids: readonly string[] };

const NENHUM: readonly string[] = [];
const semAviso = () => () => {};

function medir(lista: HTMLElement | null, chave: string, atual: Vistos): Vistos {
  if (!lista) return atual;
  const presentes = new Set<string>();
  const vistos: string[] = [];
  for (const grupo of lista.querySelectorAll<HTMLElement>("[data-chaves]")) {
    const ids: string[] = JSON.parse(grupo.dataset.chaves!);
    ids.forEach((id) => presentes.add(id));
    if (grupo.getBoundingClientRect().top < innerHeight) vistos.push(...ids);
  }
  const antes = atual.chave === chave ? atual.ids : NENHUM;
  // o que saiu da lista deixa de contar: se voltar, entra como novidade
  const ids = [...new Set([...antes.filter((id) => presentes.has(id)), ...vistos])];
  return atual.chave === chave && mesmaOrdem(ids, antes) ? atual : { chave, ids };
}

/**
 * Ids das ofertas e chave de cada grupo que a pessoa já viu (o topo do grupo passou da base da
 * tela), na ordem da tela, só enquanto `ativo`. Mede logo depois de cada render, antes da
 * pintura, para o próximo lote já saber o que está na tela, e ao rolar ou redimensionar, uma
 * vez por quadro. Medir não pede render: quem renderizar depois lê a medida mais nova.
 * Trocar `chave` (ordem, filtro, nova busca) começa do zero.
 */
export function useVistos(
  lista: RefObject<HTMLElement | null>,
  ativo: boolean,
  chave: string,
): readonly string[] {
  const medida = useRef<Vistos>({ chave, ids: NENHUM });
  const ler = useCallback(() => medida.current, []);
  const vistos = useSyncExternalStore(semAviso, ler, ler);

  useLayoutEffect(() => {
    if (!ativo) return;
    const atualizar = () => (medida.current = medir(lista.current, chave, medida.current));
    atualizar();
    let quadro = 0;
    const agendar = () => {
      quadro ||= requestAnimationFrame(() => {
        quadro = 0;
        atualizar();
      });
    };
    addEventListener("scroll", agendar, { passive: true });
    addEventListener("resize", agendar);
    return () => {
      cancelAnimationFrame(quadro);
      removeEventListener("scroll", agendar);
      removeEventListener("resize", agendar);
    };
  });

  return vistos.chave === chave ? vistos.ids : NENHUM;
}
