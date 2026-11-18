import Link from "next/link";

export default function NaoEncontrada() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-3 px-4">
      <h1 className="text-[1.5rem] font-semibold [font-stretch:104%]">Página não encontrada</h1>
      <p className="text-apagado">O endereço pode ter mudado ou estar incompleto.</p>
      <Link href="/" className="botao botao-ouro mt-2 self-start">
        Voltar para a busca
      </Link>
    </main>
  );
}
