import Link from "next/link";
import type { ReactNode } from "react";
import { ROTULO_CONSEQUENCIA, ROTULO_ESCOPO, type Noticia } from "@/lib/tipos";
import { ThemeToggle } from "./ThemeToggle";

export function ImpactBadge({ noticia }: { noticia: Pick<Noticia, "impactScope"> }) {
  return (
    <span className={`impact-badge impact-badge--${noticia.impactScope}`}>
      <span className={`pill-indicator pill-indicator--${noticia.impactScope}`}></span>
      {ROTULO_ESCOPO[noticia.impactScope]}
    </span>
  );
}

export function ConsequenceBadge({ noticia }: { noticia: Pick<Noticia, "consequence"> }) {
  return (
    <span className={`consequence-badge consequence-badge--${noticia.consequence}`}>{ROTULO_CONSEQUENCIA[noticia.consequence]}</span>
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
            <p className="masthead__sub">Acontecimentos com consequências para vários países ou para sistemas globais.</p>
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
            Jornalismo econômico sobre acontecimentos com consequências para vários países ou para sistemas globais. As matérias são
            resumos em português de reportagens publicadas por {fontes.join(", ")}, com link para a fonte original.
          </p>
        </div>
        <div className="site-footer__links">
          <div>
            <h3>Raio de Cobertura</h3>
            <ul>
              <li>
                <Link href="/?impacto=global">Impacto global</Link>
              </li>
              <li>
                <Link href="/?impacto=internacional">Impacto entre países</Link>
              </li>
            </ul>
          </div>
          <div>
            <h3>Critério Editorial</h3>
            <p className="footer-note">
              Cada matéria indica o alcance da consequência (nacional, entre países ou global) e o tamanho dela (em
              acompanhamento, relevante ou crítica), com base no que as fontes citadas mostram. Citar vários países ou uma
              multinacional não basta para classificar um fato como global.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
}
