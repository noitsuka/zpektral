import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { BuscaComParametros } from "./busca";

export async function generateMetadata({ searchParams }: PageProps<"/busca">): Promise<Metadata> {
  const bruto = (await searchParams).q;
  const q = (Array.isArray(bruto) ? bruto[0] : bruto)?.trim().slice(0, 80);
  return {
    title: q ? `${q}: preços e frete` : "Buscar",
    robots: { index: false, follow: true },
  };
}

export default async function PaginaBusca({ searchParams }: PageProps<"/busca">) {
  const bruto = (await searchParams).q;
  const q = (Array.isArray(bruto) ? bruto[0] : bruto)?.trim() ?? "";
  if (q.length < 2) redirect("/");
  return <BuscaComParametros />;
}
