import Link from "next/link";
import type { ReactNode } from "react";
import type { Noticia } from "@/lib/tipos";
import { ThemeToggle } from "./ThemeToggle";

export function ImpactBadge({ noticia }: { noticia: Pick<Noticia, "impactScope" | "impactLabel"> }) {
  const global = noticia.impactScope === "global";
  return (
    <span className={`impact-badge ${global ? "impact-badge--global" : "impact-badge--regional"}`}>
      <span className={`pill-indicator ${global ? "pill-indicator--global" : "pill-indicator--regional"}`}></span>
      {noticia.impactLabel}
    </span>
  );
}

export function CountryChips({ paises, limite }: { paises: string[]; limite?: number }) {
  return (
    <>
      {paises.slice(0, limite ?? paises.length).map((p) => (
        <span key={p} className="country-chip">
          {p}
        </span>
      ))}
    </>
  );
}

export function UtilityBar({ edicao }: { edicao: { iso: string; texto: string } }) {
  return (
    <div className="utility-bar">
      <div className="container utility-bar__inner">
        <div className="utility-bar__left">
          <span className="edition-badge">EDIÇÃO INTERNACIONAL</span>
          <span className="utility-divider">|</span>
          <time dateTime={edicao.iso}>{edicao.texto}</time>
        </div>
        <div className="utility-bar__right">
          <span className="demo-notice" title="Resumos de matérias reais; cada uma cita e linka a fonte original">
            <span className="status-dot"></span> Notícias reais com fonte citada
          </span>
          <ThemeToggle />
        </div>
      </div>
    </div>
  );
}

export function Masthead({ busca, children }: { busca?: ReactNode; children?: ReactNode }) {
  return (
    <header className="masthead">
      <div className="container">
        <div className={`masthead__grid${children ? "" : " masthead__grid--compact"}`}>
          <div className="masthead__meta">
            <p className="masthead__kicker">MONITOR DE IMPACTO SISTÊMICO</p>
            <p className="masthead__sub">Análise de eventos com repercussão mundial ou efeito cascata entre países vizinhos.</p>
          </div>
          <div className="masthead__brand">
            <Link href="/" className="brand-logo">
              MERIDIAN
            </Link>
            <p className="brand-tagline">ECONOMIA GLOBAL &bull; FRONTEIRAS &bull; GEOPOLÍTICA</p>
          </div>
          <div className="masthead__search">{busca}</div>
        </div>
        {children}
      </div>
    </header>
  );
}

export function SiteFooter({ fontes }: { fontes: string[] }) {
  return (
    <footer className="site-footer">
      <div className="container site-footer__inner">
        <div className="site-footer__brand">
          <span className="brand-logo brand-logo--sm">MERIDIAN</span>
          <p>
            Jornalismo analítico sobre choques econômicos globais, corredores logísticos e tensões transfronteiriças. As matérias são
            resumos em português de reportagens publicadas por {fontes.join(", ")}, com link para a fonte original.
          </p>
        </div>
        <div className="site-footer__links">
          <div>
            <h3>Raio de Cobertura</h3>
            <ul>
              <li>
                <Link href="/?impacto=global">Risco Sistêmico Global</Link>
              </li>
              <li>
                <Link href="/?impacto=regional">Fronteiras &amp; Blocos Vizinhos</Link>
              </li>
            </ul>
          </div>
          <div>
            <h3>Critério Editorial</h3>
            <p className="footer-note">
              Publicamos apenas acontecimentos com potencial de alterar cadeias produtivas internacionais ou gerar impacto direto em
              nações adjacentes.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
