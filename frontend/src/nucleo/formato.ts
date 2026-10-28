const formatoReais = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const formatoNumero = new Intl.NumberFormat("pt-BR");

export function reais(centavos: number): string {
  return formatoReais.format(centavos / 100).replace(/\u00a0/g, " ");
}

export function quantidade(n: number): string {
  return formatoNumero.format(n);
}

export function partesReais(centavos: number): { reais: string; fracao: string } {
  const reais = Math.trunc(centavos / 100);
  const fracao = Math.abs(centavos % 100);
  return { reais: formatoNumero.format(reais), fracao: String(fracao).padStart(2, "0") };
}

export function digitosCep(bruto: string): string {
  return bruto.replace(/\D/g, "").slice(0, 8);
}

export function mascararCep(bruto: string): string {
  const digitos = digitosCep(bruto);
  return digitos.length > 5 ? `${digitos.slice(0, 5)}-${digitos.slice(5)}` : digitos;
}

export function ehCep(bruto: string): boolean {
  const digitos = digitosCep(bruto);
  return digitos.length === 8 && digitos !== "00000000";
}

const weekday = new Intl.DateTimeFormat("pt-BR", {
  weekday: "short",
  day: "numeric",
  month: "short",
  timeZone: "UTC",
});

export function dataEntrega(dataIso: string): string {
  const data = new Date(`${dataIso}T12:00:00Z`);
  return Number.isNaN(data.getTime()) ? dataIso : weekday.format(data);
}

const relogio = new Intl.DateTimeFormat("pt-BR", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

export function horaCotacao(iso: string): string {
  const data = new Date(iso);
  return Number.isNaN(data.getTime()) ? "" : relogio.format(data);
}

export function segundos(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1).replace(".", ",")} s`;
}

export function plural(n: number, um: string, varios: string): string {
  return `${quantidade(n)} ${n === 1 ? um : varios}`;
}

const formatoPorcentagem = new Intl.NumberFormat("pt-BR", {
  style: "percent",
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

export function porcentagem(fracao: number): string {
  return formatoPorcentagem.format(fracao).replace(/\u00a0/g, " ");
}

const diaEmBrasilia = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" });

export function hojeEmBrasilia(agora: Date = new Date()): string {
  return diaEmBrasilia.format(agora);
}

const diaCurto = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "short",
  timeZone: "UTC",
});

export function diaAbreviado(dataIso: string): string {
  const data = new Date(`${dataIso}T12:00:00Z`);
  return Number.isNaN(data.getTime()) ? dataIso : diaCurto.format(data).replace(".", "");
}
