import { totalPara } from "@/nucleo/filtros";
import { mediana } from "@/nucleo/referencia";
import type { Filtros, Oferta } from "@/nucleo/tipos";

const MINIMO_OFERTAS_NIVEL = 10;
const RELEVANCIA_MINIMA_NIVEL = 90;
const RELEVANCIA_REBAIXADA = 50;
const FATOR_MINIMO = 4;
const DESVIOS = 3;
const MAD_PARA_DESVIO = 1.4826;

export function rebaixarMuitoAbaixo(ofertas: Oferta[]): Oferta[] {
  const logs = ofertas
    .filter((o) => o.relevancia >= RELEVANCIA_MINIMA_NIVEL && o.melhor_preco > 0)
    .map((o) => Math.log(o.melhor_preco));
  if (logs.length < MINIMO_OFERTAS_NIVEL) return ofertas;
  const centro = mediana(logs)!;
  const mad = mediana(logs.map((v) => Math.abs(v - centro)))!;
  const piso = centro - Math.max(DESVIOS * MAD_PARA_DESVIO * mad, Math.log(FATOR_MINIMO));
  return ofertas.map((o) =>
    o.melhor_preco > 0 && Math.log(o.melhor_preco) < piso && o.relevancia > RELEVANCIA_REBAIXADA
      ? {
          ...o,
          relevancia: RELEVANCIA_REBAIXADA,
          alertas: o.alertas.includes("preco_fora_da_curva")
            ? o.alertas
            : [...o.alertas, "preco_fora_da_curva"],
        }
      : o,
  );
}

function freteGratis(o: Oferta): boolean {
  return (
    o.frete.valor === 0 && (o.frete.status === "calculado" || o.frete.status === "gratis_anunciado")
  );
}

export function filtrarAoVivo(ofertas: Oferta[], f: Filtros): Oferta[] {
  return ofertas.filter((o) => {
    if (o.relevancia < f.relevancia_min) return false;
    if (!o.disponivel || o.frete.status === "nao_entrega") return false;
    const total = totalPara(o, f.pagamento);
    if (f.preco_min !== null && total < f.preco_min) return false;
    if (f.preco_max !== null && total > f.preco_max) return false;
    if (f.lojas.length && !f.lojas.includes(o.loja.id)) return false;
    if (f.condicao.length && !f.condicao.includes(o.condicao ?? "novo")) return false;
    if (f.voltagem.length) {
      if (o.voltagem === null) {
        if (f.voltagem_estrita) return false;
      } else if (o.voltagem !== "bivolt" && !f.voltagem.includes(o.voltagem)) return false;
    }
    if (f.frete === "calculado" && !o.total_exato) return false;
    if (f.frete === "gratis" && !freteGratis(o)) return false;
    return true;
  });
}

export function usarPaginaDoServidor(
  pagina: { pronto: boolean; total: number } | null,
  ofertasAoVivo: number,
): boolean {
  if (!pagina?.pronto) return false;
  return pagina.total > 0 || ofertasAoVivo === 0;
}
