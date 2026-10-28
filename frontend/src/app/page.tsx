import Link from "next/link";

import { LinkGitHub } from "@/componentes/icone-github";
import { InicioBusca } from "@/componentes/inicio-busca";
import { Logo } from "@/componentes/logo";

export default function Inicio() {
  return (
    <div className="relative isolate flex min-h-dvh flex-col overflow-hidden">
      <header className="relative z-10 mx-auto flex w-full max-w-6xl items-center px-5 pt-7 sm:px-8">
        <Logo grande />
      </header>

      <main className="flex flex-1 flex-col justify-center py-8">
        <InicioBusca />
      </main>

      <footer className="mx-auto flex w-full max-w-6xl items-center justify-between px-5 pb-5 sm:px-8">
        <Link href="/privacidade" className="rotulo text-tenue transition-colors hover:text-tinta">
          Privacidade
        </Link>
        <LinkGitHub />
      </footer>
    </div>
  );
}
