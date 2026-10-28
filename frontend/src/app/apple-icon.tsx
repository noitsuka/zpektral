import { ImageResponse } from "next/og";

import { svgSimbolo } from "@/nucleo/simbolo";
import { REPOUSO } from "@/nucleo/espectro";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function IconeApple() {
  const simbolo = `data:image/svg+xml,${encodeURIComponent(svgSimbolo(REPOUSO, { linhas: 4 }))}`;
  return new ImageResponse(
    // eslint-disable-next-line @next/next/no-img-element
    <img src={simbolo} width={180} height={180} alt="" />,
    size,
  );
}
