import type { MetadataRoute } from "next";

import { MARCA } from "@/nucleo/marca";

export default function manifesto(): MetadataRoute.Manifest {
  return {
    name: MARCA.nome,
    short_name: MARCA.nome,
    description: MARCA.descricao,
    lang: "pt-BR",
    start_url: "/",
    display: "standalone",
    background_color: "#0b0c0b",
    theme_color: "#0b0c0b",
    icons: [
      { src: "/icon.svg", type: "image/svg+xml", sizes: "any" },
      { src: "/apple-icon", type: "image/png", sizes: "180x180" },
    ],
  };
}
