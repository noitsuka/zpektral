import { MAPA_RELEVO } from "@/nucleo/mapa-relevo";
import { MAPA_TERRA } from "@/nucleo/mapa-terra";

export type Vetor = [number, number, number];
type Lugar = { nome: string; lat: number; lon: number };
type Rota = { de: Lugar; para: Lugar; internacional: boolean };

function decodificar(base64: string): Uint8Array {
  const binario = atob(base64);
  const saida = new Uint8Array(binario.length);
  for (let i = 0; i < binario.length; i++) saida[i] = binario.charCodeAt(i);
  return saida;
}

let bits: Uint8Array | null = null;
let niveis: Uint8Array | null = null;

function mapa(): Uint8Array {
  bits ??= decodificar(MAPA_TERRA.dados);
  return bits;
}

export function altitude(lat: number, lon: number): number {
  niveis ??= decodificar(MAPA_RELEVO.dados);
  const { largura, altura, metrosPorNivel } = MAPA_RELEVO;
  const l = Math.min(altura - 1, Math.max(0, Math.floor(((90 - lat) / 180) * altura)));
  const c = (((Math.floor(((lon + 180) / 360) * largura) % largura) + largura) % largura) | 0;
  return niveis[l * largura + c] * metrosPorNivel;
}

export function ehTerra(lat: number, lon: number): boolean {
  const { largura, altura } = MAPA_TERRA;
  const l = Math.min(altura - 1, Math.max(0, Math.floor(((90 - lat) / 180) * altura)));
  const c = (((Math.floor(((lon + 180) / 360) * largura) % largura) + largura) % largura) | 0;
  const i = l * largura + c;
  return (mapa()[i >> 3] & (1 << (i & 7))) !== 0;
}

export function pontoNaEsfera(lat: number, lon: number): Vetor {
  const fi = (lat * Math.PI) / 180;
  const lambda = (lon * Math.PI) / 180;
  return [Math.cos(fi) * Math.sin(lambda), Math.sin(fi), Math.cos(fi) * Math.cos(lambda)];
}

export function latLon([x, y, z]: Vetor): { lat: number; lon: number } {
  return { lat: (Math.asin(y) * 180) / Math.PI, lon: (Math.atan2(x, z) * 180) / Math.PI };
}

export function pontosDaEsfera(n: number): Vetor[] {
  const pontos: Vetor[] = [];
  const ouro = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < n; i++) {
    const y = 1 - (2 * (i + 0.5)) / n;
    const r = Math.sqrt(1 - y * y);
    pontos.push([r * Math.cos(i * ouro), y, r * Math.sin(i * ouro)]);
  }
  return pontos;
}

export function trechoDoArco(a: Vetor, b: Vetor, f: number): Vetor {
  const cos = Math.min(1, Math.max(-1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]));
  const angulo = Math.acos(cos);
  const seno = Math.sin(angulo) || 1;
  const ka = Math.sin((1 - f) * angulo) / seno;
  const kb = Math.sin(f * angulo) / seno;
  const altura = 1 + Math.min(0.24, angulo * 0.14) * Math.sin(Math.PI * f);
  return [
    (ka * a[0] + kb * b[0]) * altura,
    (ka * a[1] + kb * b[1]) * altura,
    (ka * a[2] + kb * b[2]) * altura,
  ];
}

const SHENZHEN = { nome: "Shenzhen", lat: 22.6, lon: 114.05 };
const GUANGZHOU = { nome: "Guangzhou", lat: 23.13, lon: 113.26 };
const MIAMI = { nome: "Miami", lat: 25.8, lon: -80.3 };
const NOVA_YORK = { nome: "Nova York", lat: 40.73, lon: -73.9 };
const CAJAMAR = { nome: "Cajamar", lat: -23.35, lon: -46.88 };
const EXTREMA = { nome: "Extrema", lat: -22.85, lon: -46.32 };
const SAO_PAULO = { nome: "São Paulo", lat: -23.55, lon: -46.63 };
const CURITIBA = { nome: "Curitiba", lat: -25.43, lon: -49.27 };

export const ROTAS: Rota[] = [
  { de: SHENZHEN, para: CURITIBA, internacional: true },
  { de: GUANGZHOU, para: SAO_PAULO, internacional: true },
  { de: MIAMI, para: SAO_PAULO, internacional: true },
  { de: NOVA_YORK, para: CURITIBA, internacional: true },
  { de: CAJAMAR, para: { nome: "Rio de Janeiro", lat: -22.88, lon: -43.3 }, internacional: false },
  { de: CAJAMAR, para: { nome: "Belo Horizonte", lat: -19.92, lon: -43.94 }, internacional: false },
  { de: CAJAMAR, para: { nome: "Salvador", lat: -12.97, lon: -38.48 }, internacional: false },
  { de: CAJAMAR, para: { nome: "Recife", lat: -8.08, lon: -35.3 }, internacional: false },
  { de: CAJAMAR, para: { nome: "Fortaleza", lat: -3.77, lon: -38.55 }, internacional: false },
  { de: CAJAMAR, para: { nome: "Manaus", lat: -3.1, lon: -60.02 }, internacional: false },
  { de: EXTREMA, para: { nome: "Brasília", lat: -15.79, lon: -47.88 }, internacional: false },
  { de: EXTREMA, para: { nome: "Porto Alegre", lat: -29.95, lon: -51.35 }, internacional: false },
  { de: EXTREMA, para: { nome: "Goiânia", lat: -16.68, lon: -49.25 }, internacional: false },
];
