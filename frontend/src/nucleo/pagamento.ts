import { totalPara } from "@/nucleo/filtros";
import { porcentagem, reais } from "@/nucleo/formato";
import { custoDoParcelamento } from "@/nucleo/juros";
import type { Oferta, Pagamento } from "@/nucleo/tipos";

// Os totais da API já incluem o frete; o valor da parcela informado pela loja, não.
export function textoDoPagamento(oferta: Oferta, pagamento: Pagamento): string | null {
  const t = oferta.totais;
  if (!t) return null;
  const total = totalPara(oferta, pagamento);
  const p = oferta.parcelamento && oferta.parcelamento.parcelas > 1 ? oferta.parcelamento : null;
  const custo = p ? custoDoParcelamento(oferta.preco, p) : null;
  const comJuros = custo !== null && custo.mensal > 0;
  const juros = custo ? `com juros de ${porcentagem(custo.mensal)} ao mês` : "";

  if (p && pagamento === "parcelado" && t.parcelado !== null && total === t.parcelado)
    return `em ${p.parcelas}x no cartão, ${comJuros ? juros : "sem juros"}`;

  const noPix = t.pix !== null && total === t.pix && t.pix < t.avista;
  if (noPix) {
    if (!p || t.parcelado === null) return `no Pix; no cartão, ${reais(t.avista)}`;
    return comJuros
      ? `no Pix; no cartão, ${reais(t.avista)} à vista ou ${reais(t.parcelado)} em ${p.parcelas}x`
      : `no Pix; no cartão, ${reais(t.avista)} em até ${p.parcelas}x sem juros`;
  }
  if (!p || t.parcelado === null) return "no cartão";
  return comJuros
    ? `no cartão à vista, ou ${reais(t.parcelado)} em ${p.parcelas}x ${juros}`
    : `no cartão, em até ${p.parcelas}x sem juros`;
}
