"use client";

import { useEffect, useRef } from "react";

import {
  ROTAS,
  altitude,
  ehTerra,
  latLon,
  pontoNaEsfera,
  pontosDaEsfera,
  trechoDoArco,
  type Vetor,
} from "@/nucleo/globo";

const PONTOS = 22000;
const RELEVO_MAXIMO = 6000;
const ALTURA_PICO = 0.11;
const PICO_MINIMO = 0.18;
const GIRO_POR_MS = (2 * Math.PI) / 80000;
const INCLINACAO = -0.2;
const LONGITUDE_INICIAL = -48;
const DURACAO_ENTRADA = 1700;
const PASSOS_ARCO = 64;
const PERIODO_PACOTE = 4600;
const CAUDA = 0.22;
const LUZ = normalizar([-0.5, 0.45, 0.75]);

type Ponto = { alvo: Vetor; origem: Vetor; relevo: number; atraso: number; brilho: number };

function normalizar(v: number[]): Vetor {
  const m = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / m, v[1] / m, v[2] / m];
}

function criarPontos(): Ponto[] {
  let semente = 11;
  const aleatorio = () => {
    semente = (semente * 16807) % 2147483647;
    return semente / 2147483647;
  };
  const pontos: Ponto[] = [];
  for (const p of pontosDaEsfera(PONTOS)) {
    const { lat, lon } = latLon(p);
    if (!ehTerra(lat, lon)) continue;
    const distancia = 1.9 + aleatorio() * 1.4;
    const a = aleatorio() * Math.PI * 2;
    const b = (aleatorio() - 0.5) * Math.PI;
    pontos.push({
      alvo: p,
      origem: [
        Math.cos(b) * Math.cos(a) * distancia,
        Math.sin(b) * distancia,
        Math.cos(b) * Math.sin(a) * distancia,
      ],
      relevo: lat < -60 || lat > 60 ? 0 : Math.min(1, altitude(lat, lon) / RELEVO_MAXIMO),
      atraso: aleatorio() * 0.4,
      brilho: aleatorio(),
    });
  }
  return pontos;
}

function graticula(): Vetor[][] {
  const linhas: Vetor[][] = [];
  for (let lat = -60; lat <= 60; lat += 30) {
    const linha: Vetor[] = [];
    for (let lon = -180; lon <= 180; lon += 3) linha.push(pontoNaEsfera(lat, lon));
    linhas.push(linha);
  }
  for (let lon = -180; lon < 180; lon += 30) {
    const linha: Vetor[] = [];
    for (let lat = -84; lat <= 84; lat += 3) linha.push(pontoNaEsfera(lat, lon));
    linhas.push(linha);
  }
  return linhas;
}

export function GloboRotas({ className = "" }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const calmo = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const pontos = criarPontos();
    const linhasGrade = graticula();
    const rotas = ROTAS.map((r, i) => {
      const de = pontoNaEsfera(r.de.lat, r.de.lon);
      const para = pontoNaEsfera(r.para.lat, r.para.lon);
      const trecho: Vetor[] = [];
      for (let s = 0; s <= PASSOS_ARCO; s++) trecho.push(trechoDoArco(de, para, s / PASSOS_ARCO));
      return { de, para, trecho, fase: (i * 0.173) % 1, internacional: r.internacional };
    });

    let largura = 0;
    let altura = 0;
    let quadro = 0;
    let visivel = true;
    let inicio = 0;
    let anterior = 0;
    let giro = (-LONGITUDE_INICIAL * Math.PI) / 180;
    let embalo = 0;
    const ponteiro = { x: 0, y: 0, alvoX: 0, alvoY: 0 };
    const arraste = { ativo: false, x: 0 };

    const redimensionar = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      largura = canvas.clientWidth;
      altura = canvas.clientHeight;
      canvas.width = largura * dpr;
      canvas.height = altura * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const desenhar = (agora: number) => {
      if (!inicio) inicio = agora;
      const dt = Math.min(64, agora - (anterior || agora));
      anterior = agora;
      if (!arraste.ativo) {
        giro += dt * GIRO_POR_MS * (calmo ? 0.5 : 1) + embalo;
        embalo *= 0.93;
      }
      ponteiro.x += (ponteiro.alvoX - ponteiro.x) * 0.05;
      ponteiro.y += (ponteiro.alvoY - ponteiro.y) * 0.05;

      const g = giro + (calmo ? 0 : ponteiro.x * 0.12);
      const inc = INCLINACAO + (calmo ? 0 : ponteiro.y * 0.1);
      const cg = Math.cos(g);
      const sg = Math.sin(g);
      const ci = Math.cos(inc);
      const si = Math.sin(inc);
      const raio = Math.min(largura, altura) * 0.39;
      const cx = largura / 2;
      const cy = altura / 2;
      const girar = (v: Vetor): Vetor => {
        const x = v[0] * cg + v[2] * sg;
        const z = -v[0] * sg + v[2] * cg;
        return [x, v[1] * ci - z * si, v[1] * si + z * ci];
      };
      const tela = (v: Vetor) => {
        const p = 3 / (3 - v[2] * 0.5);
        return { x: cx + v[0] * raio * p, y: cy - v[1] * raio * p };
      };

      ctx.clearRect(0, 0, largura, altura);
      const entrada = Math.min(1, (agora - inicio) / DURACAO_ENTRADA);
      const suave = 1 - Math.pow(1 - entrada, 3);

      const corpo = ctx.createRadialGradient(
        cx - raio * 0.35,
        cy - raio * 0.4,
        raio * 0.1,
        cx,
        cy,
        raio * 1.02,
      );
      corpo.addColorStop(0, `rgba(242,243,241,${0.05 * suave})`);
      corpo.addColorStop(0.7, `rgba(242,243,241,${0.015 * suave})`);
      corpo.addColorStop(1, "rgba(242,243,241,0)");
      ctx.fillStyle = corpo;
      ctx.beginPath();
      ctx.arc(cx, cy, raio * 1.02, 0, Math.PI * 2);
      ctx.fill();

      const borda = ctx.createLinearGradient(cx - raio, cy - raio, cx + raio, cy + raio);
      borda.addColorStop(0, `rgba(242,243,241,${0.28 * suave})`);
      borda.addColorStop(0.5, `rgba(242,243,241,${0.06 * suave})`);
      borda.addColorStop(1, `rgba(242,243,241,${0.02 * suave})`);
      ctx.strokeStyle = borda;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.arc(cx, cy, raio * 1.005, 0, Math.PI * 2);
      ctx.stroke();

      ctx.lineWidth = 0.6;
      for (const linha of linhasGrade) {
        ctx.beginPath();
        let aberto = false;
        for (const v of linha) {
          const r = girar(v);
          if (r[2] < 0) {
            aberto = false;
            continue;
          }
          const p = tela(r);
          if (aberto) ctx.lineTo(p.x, p.y);
          else ctx.moveTo(p.x, p.y);
          aberto = true;
        }
        ctx.strokeStyle = `rgba(242,243,241,${0.05 * suave})`;
        ctx.stroke();
      }

      const varredura = agora * 0.00018;
      for (const pt of pontos) {
        const local = Math.min(1, Math.max(0, (entrada - pt.atraso) / (1 - pt.atraso)));
        const f = 1 - Math.pow(1 - local, 3);
        const pos: Vetor =
          f < 1
            ? [
                pt.origem[0] + (pt.alvo[0] - pt.origem[0]) * f,
                pt.origem[1] + (pt.alvo[1] - pt.origem[1]) * f,
                pt.origem[2] + (pt.alvo[2] - pt.origem[2]) * f,
              ]
            : pt.alvo;
        const r = girar(pos);
        if (f >= 1 && r[2] < 0) continue;
        const n = f >= 1 ? r : girar(pt.alvo);
        const luz = Math.max(0, n[0] * LUZ[0] + n[1] * LUZ[1] + n[2] * LUZ[2]);
        const onda = 0.5 + 0.5 * Math.sin(pt.alvo[0] * 9 + pt.alvo[1] * 7 - varredura * 6);
        const borda = Math.min(1, Math.max(0, r[2]) * 2.2);
        const alfa = (0.16 + 0.62 * luz + 0.14 * onda * (0.5 + pt.brilho)) * (0.3 + 0.7 * borda);
        const p = tela(r);
        const tamanho = 1.1 + luz * 0.6;
        ctx.fillStyle = `rgba(242,243,241,${(alfa * (0.25 + 0.75 * f)).toFixed(3)})`;
        ctx.fillRect(p.x - tamanho / 2, p.y - tamanho / 2, tamanho, tamanho);

        if (f >= 1 && pt.relevo > PICO_MINIMO && r[2] > 0.2) {
          const topo = tela(
            girar([
              pt.alvo[0] * (1 + pt.relevo * ALTURA_PICO),
              pt.alvo[1] * (1 + pt.relevo * ALTURA_PICO),
              pt.alvo[2] * (1 + pt.relevo * ALTURA_PICO),
            ]),
          );
          const pico = ctx.createLinearGradient(p.x, p.y, topo.x, topo.y);
          pico.addColorStop(0, `rgba(242,243,241,${Math.min(0.9, alfa * 1.15).toFixed(3)})`);
          pico.addColorStop(1, "rgba(242,243,241,0)");
          ctx.strokeStyle = pico;
          ctx.lineWidth = 0.8;
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(topo.x, topo.y);
          ctx.stroke();
        }
      }

      if (entrada < 1) return;
      const aparece = Math.min(1, (agora - inicio - DURACAO_ENTRADA) / 800);
      for (const rota of rotas) {
        const projetados = rota.trecho.map((v) => {
          const r = girar(v);
          const dentro = Math.min(1, Math.max(0, (1.04 - Math.hypot(r[0], r[1])) / 0.08));
          const fade = Math.min(1, Math.max(0, (r[2] - 0.02) / 0.3)) * dentro;
          return { ...tela(r), visivel: fade > 0, fade };
        });
        ctx.lineWidth = rota.internacional ? 1 : 0.8;
        for (let s = 0; s < PASSOS_ARCO; s++) {
          const a = projetados[s];
          const b = projetados[s + 1];
          const fade = Math.min(a.fade, b.fade);
          if (fade <= 0) continue;
          ctx.strokeStyle = `rgba(233,196,106,${(0.22 * fade * aparece).toFixed(3)})`;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }

        const ciclo = (agora / PERIODO_PACOTE + rota.fase) % 1;
        const cabeca = Math.min(1, ciclo * 1.3);
        const inicioCauda = Math.max(0, cabeca - CAUDA);
        const i0 = Math.floor(inicioCauda * PASSOS_ARCO);
        const i1 = Math.floor(cabeca * PASSOS_ARCO);
        for (let s = i0; s < i1; s++) {
          const a = projetados[s];
          const b = projetados[s + 1];
          if (!a.visivel || !b.visivel) continue;
          const t = (s - i0) / Math.max(1, i1 - i0);
          ctx.strokeStyle = `rgba(233,196,106,${(t * 0.95 * Math.min(a.fade, b.fade) * aparece).toFixed(3)})`;
          ctx.lineWidth = 1 + t * 0.9;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
        const ponta = projetados[i1];
        if (ponta?.visivel && cabeca < 1) {
          ctx.fillStyle = `rgba(233,196,106,${(0.18 * aparece).toFixed(3)})`;
          ctx.beginPath();
          ctx.arc(ponta.x, ponta.y, 4.5, 0, Math.PI * 2);
          ctx.fill();
          ctx.fillStyle = `rgba(255,236,190,${aparece.toFixed(3)})`;
          ctx.beginPath();
          ctx.arc(ponta.x, ponta.y, 1.6, 0, Math.PI * 2);
          ctx.fill();
        }

        const chegada = projetados[PASSOS_ARCO];
        if (chegada.visivel) {
          const depois = (ciclo * 1.3 - 1) / 0.3;
          if (depois > 0 && depois < 1) {
            ctx.strokeStyle = `rgba(233,196,106,${((1 - depois) * 0.8 * aparece).toFixed(3)})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(chegada.x, chegada.y, 2 + depois * 12, 0, Math.PI * 2);
            ctx.stroke();
          }
          ctx.fillStyle = `rgba(233,196,106,${(0.85 * aparece).toFixed(3)})`;
          ctx.fillRect(chegada.x - 1.2, chegada.y - 1.2, 2.4, 2.4);
        }
        const saida = projetados[0];
        if (saida.visivel) {
          ctx.strokeStyle = `rgba(233,196,106,${(0.6 * aparece).toFixed(3)})`;
          ctx.lineWidth = 0.8;
          ctx.strokeRect(saida.x - 2.5, saida.y - 2.5, 5, 5);
        }
      }
    };

    const laco = (agora: number) => {
      quadro = requestAnimationFrame(laco);
      if (!visivel || document.hidden) {
        anterior = 0;
        return;
      }
      desenhar(agora);
    };

    const aoMover = (e: PointerEvent) => {
      ponteiro.alvoX = (e.clientX / window.innerWidth - 0.5) * 2;
      ponteiro.alvoY = (e.clientY / window.innerHeight - 0.5) * 2;
      if (!arraste.ativo) return;
      const delta = ((e.clientX - arraste.x) / Math.max(largura, 1)) * 3.2;
      giro += delta;
      embalo = delta * 0.5;
      arraste.x = e.clientX;
    };
    const aoPressionar = (e: PointerEvent) => {
      arraste.ativo = true;
      arraste.x = e.clientX;
      canvas.setPointerCapture(e.pointerId);
    };
    const aoSoltar = () => {
      arraste.ativo = false;
    };

    redimensionar();
    const observador = new IntersectionObserver(([e]) => (visivel = e.isIntersecting));
    observador.observe(canvas);
    window.addEventListener("resize", redimensionar);
    window.addEventListener("pointermove", aoMover, { passive: true });
    canvas.addEventListener("pointerdown", aoPressionar);
    canvas.addEventListener("pointerup", aoSoltar);
    canvas.addEventListener("pointercancel", aoSoltar);
    quadro = requestAnimationFrame(laco);

    return () => {
      cancelAnimationFrame(quadro);
      observador.disconnect();
      window.removeEventListener("resize", redimensionar);
      window.removeEventListener("pointermove", aoMover);
      canvas.removeEventListener("pointerdown", aoPressionar);
      canvas.removeEventListener("pointerup", aoSoltar);
      canvas.removeEventListener("pointercancel", aoSoltar);
    };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden
      className={`cursor-grab touch-pan-y active:cursor-grabbing ${className}`}
    />
  );
}
