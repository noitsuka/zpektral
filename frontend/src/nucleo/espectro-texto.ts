type Pico = { posicao: number; forca: number };

const MAXIMO = 24;

function fnv1a(texto: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < texto.length; i++) {
    h ^= texto.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

export function picosDoTexto(texto: string): Pico[] {
  const palavras = texto.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const picos: Pico[] = [];
  for (const palavra of palavras) {
    const h = fnv1a(palavra);
    picos.push({ posicao: (h % 10007) / 10007, forca: 0.6 + ((h >>> 16) % 41) / 100 });
    for (let i = 0; i + 1 < palavra.length; i++) {
      const g = fnv1a(`${palavra}:${i}:${palavra.slice(i, i + 2)}`);
      picos.push({ posicao: (g % 10007) / 10007, forca: 0.15 + ((g >>> 16) % 31) / 100 });
    }
  }
  const fortes = picos.filter((p) => p.forca >= 0.6);
  const fracos = picos.filter((p) => p.forca < 0.6);
  return [...fortes, ...fracos].slice(0, MAXIMO);
}
