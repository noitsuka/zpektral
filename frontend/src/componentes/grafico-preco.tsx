import { diaAbreviado, reais } from "@/nucleo/formato";
import type { PontoHistorico } from "@/nucleo/tipos";

const LARGURA = 300;
const ALTURA = 64;
const MARGEM = 6;

function tempo(dia: string): number {
  return Date.parse(`${dia}T12:00:00Z`);
}

export function GraficoPreco({ pontos, mediana }: { pontos: PontoHistorico[]; mediana: number }) {
  if (pontos.length < 2) return null;
  const inicio = tempo(pontos[0].dia);
  const fim = tempo(pontos[pontos.length - 1].dia);
  const precos = pontos.map((p) => p.preco);
  const menor = Math.min(...precos, mediana);
  const maior = Math.max(...precos, mediana);
  const faixa = maior - menor || 1;
  const x = (dia: string) =>
    MARGEM + ((tempo(dia) - inicio) / (fim - inicio || 1)) * (LARGURA - 2 * MARGEM);
  const y = (preco: number) => MARGEM + (1 - (preco - menor) / faixa) * (ALTURA - 2 * MARGEM);
  const linha = pontos.map((p) => `${x(p.dia).toFixed(1)},${y(p.preco).toFixed(1)}`).join(" ");
  const area = `${MARGEM},${ALTURA} ${linha} ${LARGURA - MARGEM},${ALTURA}`;
  const ultimo = pontos[pontos.length - 1];

  return (
    <figure className="mt-2">
      <svg
        viewBox={`0 0 ${LARGURA} ${ALTURA}`}
        preserveAspectRatio="none"
        className="h-16 w-full overflow-visible"
        role="img"
        aria-label={`Preço nesta loja de ${diaAbreviado(pontos[0].dia)} até hoje, entre ${reais(Math.min(...precos))} e ${reais(Math.max(...precos))}`}
      >
        <polygon points={area} className="fill-ouro/[0.07]" />
        <line
          x1={MARGEM}
          x2={LARGURA - MARGEM}
          y1={y(mediana)}
          y2={y(mediana)}
          className="stroke-tenue"
          strokeDasharray="3 4"
          strokeWidth={1}
          vectorEffect="non-scaling-stroke"
        />
        <polyline
          points={linha}
          pathLength={1}
          className="linha-grafico fill-none stroke-tinta/70"
          strokeWidth={1.5}
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        <circle cx={x(ultimo.dia)} cy={y(ultimo.preco)} r={3} className="fill-ouro" />
      </svg>
      <figcaption className="mt-1 flex justify-between font-sans text-[11.5px] text-tenue">
        <span>{diaAbreviado(pontos[0].dia)}</span>
        <span>tracejado: preço habitual</span>
        <span>hoje</span>
      </figcaption>
    </figure>
  );
}
