"use client";

import { useState } from "react";
import type { Escopo } from "@/lib/tipos";

// SVG editorial de reserva quando a imagem da fonte não carrega
function fallbackSvg(bg: string, accent: string, label: string) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500">
    <rect width="800" height="500" fill="${bg}"/>
    <g stroke="${accent}" stroke-opacity="0.22" stroke-width="1">
      <line x1="0" y1="100" x2="800" y2="100"/><line x1="0" y1="250" x2="800" y2="250"/><line x1="0" y1="400" x2="800" y2="400"/>
      <line x1="200" y1="0" x2="200" y2="500"/><line x1="400" y1="0" x2="400" y2="500"/><line x1="600" y1="0" x2="600" y2="500"/>
    </g>
    <circle cx="400" cy="250" r="140" fill="none" stroke="${accent}" stroke-opacity="0.35" stroke-width="2" stroke-dasharray="6 6"/>
    <text x="50" y="70" fill="${accent}" font-family="Georgia, serif" font-size="18" font-weight="bold" letter-spacing="3">${label}</text>
    <text x="50" y="440" fill="#ffffff" fill-opacity="0.85" font-family="Georgia, serif" font-size="22">MERIDIAN • ECONOMIA &amp; GEOPOLÍTICA</text>
  </svg>`;
  return "data:image/svg+xml;charset=UTF-8," + encodeURIComponent(svg);
}

// Montados uma vez só, não a cada cartão renderizado
const RESERVA: Record<Escopo, string> = {
  global: fallbackSvg("#2b131d", "#e11d48", "IMPACTO GLOBAL"),
  internacional: fallbackSvg("#102a2e", "#14b8a6", "IMPACTO ENTRE PAÍSES"),
  nacional: fallbackSvg("#1f1c19", "#a8998a", "IMPACTO NACIONAL"),
};

export function NewsImage({ src, alt, scope, lazy = true }: { src?: string; alt: string; scope: Escopo; lazy?: boolean }) {
  // Guarda qual endereço falhou, para uma imagem nova no mesmo lugar ganhar outra chance
  const [falhou, setFalhou] = useState<string | null>(null);
  const usarReserva = !src || falhou === src;

  // A imagem do HTML estático pode falhar antes de o React ligar o onError; nesse caso o evento
  // já passou e o leitor ficaria com o ícone de imagem quebrada. Aqui o estado final é conferido.
  function conferir(img: HTMLImageElement | null) {
    if (img && src && !usarReserva && img.complete && img.naturalWidth === 0) setFalhou(src);
  }

  // Imagens vêm de vários domínios das fontes, então não passam pelo next/image.
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      ref={conferir}
      src={usarReserva ? RESERVA[scope] : src}
      alt={alt}
      loading={lazy ? "lazy" : "eager"}
      referrerPolicy="no-referrer"
      onError={() => src && setFalhou(src)}
    />
  );
}
