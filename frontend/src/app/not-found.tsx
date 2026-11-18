import Link from "next/link";

export default function NaoEncontrada() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-3 px-4">
      <h1 className="text-[1.5rem] font-semibold">Página não encontrada</h1>
      <p className="text-tinta-2">O endereço pode ter mudado ou estar incompleto.</p>
      <Link href="/" className="botao botao-primario mt-2 self-start">
        Voltar para a busca
      </Link>
    </main>
  );
}
