import Link from "next/link";

import { LinkGitHub } from "@/componentes/icone-github";
import { Logo } from "@/componentes/logo";

export function Cabecalho() {
  return (
    <header className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6 sm:py-6">
      <Logo grande />
      <nav aria-label="Principal">
        <Link
          href="/ofertas"
          className="inline-flex min-h-11 items-center text-[0.9375rem] text-apagado transition-colors hover:text-tinta"
        >
          Quedas de preço
        </Link>
      </nav>
    </header>
  );
}

export function Rodape() {
  return (
    <footer className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4 px-4 py-3 sm:px-6 sm:py-5">
      <Link
        href="/privacidade"
        className="inline-flex min-h-11 items-center text-[0.875rem] text-tenue transition-colors hover:text-tinta"
      >
        Privacidade
      </Link>
      <LinkGitHub />
    </footer>
  );
}
