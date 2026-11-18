"use client";

import { ImageOff } from "lucide-react";
import { useState } from "react";

export function Foto({ imagem, tamanho }: { imagem: string | null | undefined; tamanho: string }) {
  const [falhou, setFalhou] = useState(false);
  return (
    <div
      className={`${tamanho} shrink-0 overflow-hidden rounded-controle border border-fio bg-white`}
    >
      {imagem && !falhou ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={imagem}
          alt=""
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onError={() => setFalhou(true)}
          className="size-full object-contain p-1"
        />
      ) : (
        <div className="grid size-full place-items-center bg-etiqueta-2">
          <ImageOff className="size-5 text-tinta-3" aria-hidden />
        </div>
      )}
    </div>
  );
}
