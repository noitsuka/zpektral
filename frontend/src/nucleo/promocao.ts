import { diaAbreviado, porcentagem, reais } from "@/nucleo/formato";
import { avaliarHistorico } from "@/nucleo/tendencia";
import type { Oferta, PontoHistorico } from "@/nucleo/tipos";

type TipoSelo =
  | "menor_em_dias"
  | "abaixo_do_habitual"
  | "acima_do_habitual"
  | "anunciado"
  | "sem_respaldo"
  | "historico_insuficiente"
  | "pix"
  | "promocao_da_loja"
  | "validade";

export type Selo = {
  tipo: TipoSelo;
  texto: string;
  evidencia: string;
  tom: "economia" | "alerta" | "neutro";
};

export type Promocao = {
  selos: Selo[];
  // Fração abaixo do habitual desta loja, só com histórico suficiente. Pix e desconto
  // anunciado ficam fora: comparar com o habitual exige o mesmo tipo de preço dos dois lados.
  economiaVerificada: number;
  quedaVerificada: boolean;
};

const MAXIMO_PROMOCOES = 3;

const DIA_EM_SAO_PAULO = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" });

// O instante decide se ainda vale; o dia mostrado é o de São Paulo, não o de UTC.
function validadeInformada(valor: string | null | undefined, agora: number): string | null {
  const instante = valor ? Date.parse(valor) : NaN;
  if (!(instante > agora)) return null;
  return DIA_EM_SAO_PAULO.format(instante);
}

export function avaliarPromocao(
  oferta: Oferta,
  serie: PontoHistorico[] | undefined,
  hoje: string,
  agora: number = Date.now(),
): Promocao {
  const selos: Selo[] = [];
  // o preço da versão mais barata não é o do item que a série acompanha
  const comparavel = serie && !oferta.alertas.includes("preco_varia_por_versao");
  const avaliacao = comparavel ? avaliarHistorico(oferta.preco, serie, hoje) : null;

  if (avaliacao?.situacao === "menor") {
    selos.push({
      tipo: "menor_em_dias",
      texto: `Menor preço desta loja em ${avaliacao.dias} dias`,
      evidencia: `habitual ${reais(Math.round(avaliacao.mediana))}, visto nas buscas do Zpektral`,
      tom: "economia",
    });
  } else if (avaliacao?.situacao === "abaixo" || avaliacao?.situacao === "acima") {
    const abaixo = avaliacao.situacao === "abaixo";
    selos.push({
      tipo: abaixo ? "abaixo_do_habitual" : "acima_do_habitual",
      texto: `${porcentagem(Math.abs(avaliacao.variacao))} ${abaixo ? "abaixo" : "acima"} do habitual desta loja`,
      evidencia: `habitual ${reais(Math.round(avaliacao.mediana))} em ${avaliacao.dias} dias`,
      tom: abaixo ? "economia" : "alerta",
    });
  }

  const de = oferta.preco_original;
  if (de && de > oferta.preco) {
    selos.push({
      tipo: "anunciado",
      texto: `${porcentagem(1 - oferta.preco / de)} de desconto anunciado pela loja`,
      evidencia: `de ${reais(de)} por ${reais(oferta.preco)}`,
      tom: "neutro",
    });
    if (!avaliacao) {
      selos.push({
        tipo: "historico_insuficiente",
        texto: "Histórico insuficiente para confirmar a economia",
        evidencia: "o Zpektral ainda viu poucos dias de preço desta oferta",
        tom: "neutro",
      });
    } else {
      const maior = Math.max(...serie!.filter((p) => p.dia < hoje).map((p) => p.preco));
      if (de > maior) {
        selos.push({
          tipo: "sem_respaldo",
          texto: "Desconto anunciado sem respaldo",
          evidencia: `o preço de antes, ${reais(de)}, é maior que o mais alto visto nesta loja em ${avaliacao.dias} dias, ${reais(maior)}`,
          tom: "alerta",
        });
      } else if (avaliacao.situacao !== "menor" && avaliacao.situacao !== "abaixo") {
        selos.push({
          tipo: "sem_respaldo",
          texto: "Desconto anunciado sem respaldo",
          evidencia: `o preço de hoje não está abaixo do habitual desta loja, ${reais(Math.round(avaliacao.mediana))}`,
          tom: "alerta",
        });
      }
    }
  }

  if (oferta.preco_pix !== null && oferta.preco_pix < oferta.preco) {
    selos.push({
      tipo: "pix",
      texto: `${reais(oferta.preco - oferta.preco_pix)} a menos no Pix`,
      evidencia: "preço no Pix informado pela loja",
      tom: "economia",
    });
  }

  const nomes = new Set((oferta.promocoes ?? []).map((n) => n.trim()).filter(Boolean));
  for (const nome of [...nomes].slice(0, MAXIMO_PROMOCOES)) {
    selos.push({
      tipo: "promocao_da_loja",
      texto: nome,
      evidencia: "informada pela loja",
      tom: "neutro",
    });
  }

  const validade = validadeInformada(oferta.preco_valido_ate, agora);
  if (validade) {
    selos.push({
      tipo: "validade",
      texto: `Preço válido até ${diaAbreviado(validade)}`,
      evidencia: "data informada pela loja",
      tom: "neutro",
    });
  }

  const queda =
    avaliacao && (avaliacao.situacao === "menor" || avaliacao.situacao === "abaixo")
      ? -avaliacao.variacao
      : 0;
  return { selos, economiaVerificada: queda, quedaVerificada: queda > 0 };
}
