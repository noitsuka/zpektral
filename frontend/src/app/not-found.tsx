import Link from "next/link";

export default function NaoEncontrada() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="font-mono text-sm text-tenue">404</p>
      <h1 className="text-2xl font-bold tracking-tight">Página não encontrada</h1>
      <Link href="/" className="text-sm text-ouro underline-offset-4 hover:underline">
        Voltar para a busca
      </Link>
    </main>
  );
}
