"use client";

import { useEffect } from "react";

const CAMPOS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

export function useAtalhoBusca() {
  useEffect(() => {
    function aoTeclar(evento: KeyboardEvent) {
      if (evento.key !== "/" || evento.ctrlKey || evento.metaKey || evento.altKey) return;
      const alvo = evento.target as HTMLElement | null;
      if (alvo && (CAMPOS.has(alvo.tagName) || alvo.isContentEditable)) return;
      const campo = document.querySelector<HTMLInputElement>('input[enterkeyhint="search"]');
      if (!campo) return;
      evento.preventDefault();
      campo.focus();
      campo.select();
    }
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, []);
}
