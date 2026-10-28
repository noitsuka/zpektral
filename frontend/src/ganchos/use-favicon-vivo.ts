"use client";

import { useEffect } from "react";

import { svgSimbolo } from "@/nucleo/simbolo";
import type { Espectro } from "@/nucleo/espectro";

const ESTATICO = "/icon.svg";

function setIcone(href: string) {
  let link = document.querySelector<HTMLLinkElement>("link[data-live-icon]");
  if (!link) {
    link = document.createElement("link");
    link.rel = "icon";
    link.type = "image/svg+xml";
    link.dataset.liveIcon = "";
    document.head.appendChild(link);
  }
  link.href = href;
}

function urlDados(svg: string) {
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

export function useFaviconVivo(espectro: Espectro, varrendo: boolean) {
  useEffect(() => {
    if (!varrendo) {
      setIcone(urlDados(svgSimbolo(espectro)));
      return;
    }
    const id = setInterval(() => {
      const ruido = Array.from({ length: 4 }, () => 0.15 + Math.random() * 0.85) as Espectro;
      setIcone(urlDados(svgSimbolo(ruido, { dourada: false })));
    }, 220);
    return () => clearInterval(id);
  }, [espectro, varrendo]);

  useEffect(() => () => setIcone(ESTATICO), []);
}
