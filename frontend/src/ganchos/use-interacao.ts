"use client";

import { useEffect, useState, type RefObject } from "react";

const NO_BLOCO = ["pointerenter", "pointerleave", "pointerdown", "focusin", "focusout"];
const NA_JANELA = ["pointerup", "pointercancel"];

/**
 * Diz se a pessoa está mexendo no bloco: ponteiro em cima ou pressionado, foco dentro ou a
 * conta de alguma oferta aberta ali.
 */
export function useInteracao(ref: RefObject<HTMLElement | null>): boolean {
  const [interagindo, setInteragindo] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let sobre = false;
    let pressionado = false;
    let focado = false;
    const aoEvento = (e: Event) => {
      if (e.type === "pointerenter" || e.type === "pointerleave") sobre = e.type === "pointerenter";
      else if (e.type === "pointerdown") pressionado = true;
      else if (e.type === "focusin") focado = true;
      else if (e.type === "focusout")
        focado = el.contains((e as FocusEvent).relatedTarget as Node | null);
      else if (pressionado) pressionado = false;
      else return;
      setInteragindo(
        sobre || pressionado || focado || !!el.querySelector('[aria-expanded="true"]'),
      );
    };
    NO_BLOCO.forEach((tipo) => el.addEventListener(tipo, aoEvento));
    NA_JANELA.forEach((tipo) => addEventListener(tipo, aoEvento));
    return () => {
      NO_BLOCO.forEach((tipo) => el.removeEventListener(tipo, aoEvento));
      NA_JANELA.forEach((tipo) => removeEventListener(tipo, aoEvento));
    };
  }, [ref]);

  return interagindo;
}
