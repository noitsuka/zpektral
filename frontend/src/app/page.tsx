import { Cabecalho, Rodape } from "@/componentes/moldura";
import { InicioBusca } from "@/componentes/inicio-busca";

export default function Inicio() {
  return (
    <div className="flex min-h-dvh flex-col">
      <Cabecalho />
      <main className="flex flex-1 flex-col justify-center pt-2 pb-10 lg:pb-16">
        <InicioBusca />
      </main>
      <Rodape />
    </div>
  );
}
