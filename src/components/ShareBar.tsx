"use client";

import { useState } from "react";

// O endereço é montado no clique a partir de window.location, assim o link vale
// para qualquer domínio (preview da Vercel, domínio próprio, localhost).
function enderecoCompleto(caminho: string) {
  return new URL(caminho, window.location.origin).toString();
}

const REDES: { nome: string; montar: (url: string, titulo: string) => string }[] = [
  { nome: "WhatsApp", montar: (url, titulo) => `https://wa.me/?text=${encodeURIComponent(`${titulo} ${url}`)}` },
  { nome: "X", montar: (url, titulo) => `https://twitter.com/intent/tweet?url=${encodeURIComponent(url)}&text=${encodeURIComponent(titulo)}` },
  { nome: "LinkedIn", montar: (url) => `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}` },
  { nome: "Facebook", montar: (url) => `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}` },
  { nome: "Telegram", montar: (url, titulo) => `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(titulo)}` },
  { nome: "E-mail", montar: (url, titulo) => `mailto:?subject=${encodeURIComponent(titulo)}&body=${encodeURIComponent(url)}` },
];

async function copiarTexto(texto: string) {
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch {
    // Sem permissão de clipboard (http, navegador antigo): cópia pelo método clássico
    const campo = document.createElement("textarea");
    campo.value = texto;
    campo.setAttribute("readonly", "");
    campo.style.position = "fixed";
    campo.style.opacity = "0";
    document.body.appendChild(campo);
    campo.select();
    const ok = document.execCommand("copy");
    campo.remove();
    return ok;
  }
}

export function ShareBar({ titulo, caminho }: { titulo: string; caminho: string }) {
  const [aviso, setAviso] = useState("");

  function avisar(texto: string) {
    setAviso(texto);
    setTimeout(() => setAviso(""), 2500);
  }

  async function copiar() {
    avisar((await copiarTexto(enderecoCompleto(caminho))) ? "Link copiado" : "Não foi possível copiar o link");
  }

  async function compartilhar() {
    const url = enderecoCompleto(caminho);
    if (navigator.share) {
      try {
        await navigator.share({ title: titulo, url });
      } catch {
        // o leitor fechou a janela de compartilhamento
      }
      return;
    }
    // Sem compartilhamento nativo (a maioria dos desktops): copia o link
    avisar((await copiarTexto(url)) ? "Link copiado" : "Não foi possível copiar o link");
  }

  function abrir(montar: (url: string, titulo: string) => string) {
    const destino = montar(enderecoCompleto(caminho), titulo);
    if (destino.startsWith("mailto:")) window.location.assign(destino);
    else window.open(destino, "_blank", "noopener,noreferrer");
  }

  return (
    <div className="share-bar" role="group" aria-label="Compartilhar esta matéria">
      <button type="button" className="share-btn share-btn--primary" onClick={compartilhar}>
        Compartilhar
      </button>
      <button type="button" className="share-btn" onClick={copiar}>
        Copiar link
      </button>
      {REDES.map((r) => (
        <button key={r.nome} type="button" className="share-btn" onClick={() => abrir(r.montar)}>
          {r.nome}
        </button>
      ))}
      <span className="share-bar__aviso" role="status" aria-live="polite">
        {aviso}
      </span>
    </div>
  );
}
