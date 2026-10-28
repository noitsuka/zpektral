"use client";

export default function PaginaErro({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="text-2xl font-bold tracking-tight">Algo deu errado nesta página</h1>
      <p className="text-sm text-apagado">Tente de novo. Se continuar, volte em alguns minutos.</p>
      <button
        type="button"
        onClick={reset}
        className="rounded-quadro border border-traco px-4 py-2 text-sm hover:border-tinta/25"
      >
        Tentar de novo
      </button>
    </main>
  );
}
