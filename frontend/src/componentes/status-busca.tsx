export function StatusBusca({
  responderam,
  total,
  terminou,
}: {
  responderam: number;
  total: number;
  terminou: boolean;
}) {
  if (terminou || !total) return null;
  const fracao = Math.max(0.08, responderam / total);
  return (
    <div role="status" className="barra-progresso" aria-live="polite">
      <span className="sr-only">Buscando ofertas</span>
      <span
        aria-hidden
        className="barra-progresso-cheia"
        style={{ transform: `scaleX(${fracao})` }}
      />
    </div>
  );
}
