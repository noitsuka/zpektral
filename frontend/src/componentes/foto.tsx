"use client";

import { ImageOff } from "lucide-react";
import { useState } from "react";

export function Foto({ imagem, tamanho }: { imagem: string | null | undefined; tamanho: string }) {
  const [falhou, setFalhou] = useState(false);
  return (
    <div className={`${tamanho} shrink-0 overflow-hidden rounded-quadro bg-white`}>
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
        <div className="grid size-full place-items-center bg-relevo">
          <ImageOff className="size-4 text-tenue" aria-hidden />
        </div>
      )}
    </div>
  );
}
