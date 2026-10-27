"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { CATEGORIAS, ESCOPOS, ROTULO_ESCOPO, escopoDaUrl, type Escopo, type Noticia } from "@/lib/tipos";
import { ConsequenceBadge, CountryChips, ImpactBadge, Masthead } from "./Editorial";
import { NewsImage } from "./NewsImage";

type FiltroImpacto = "all" | Escopo;
export type NoticiaResumo = Omit<Noticia, "keyPoints" | "body"> & { dataFormatada: string; textoBusca: string };

/** Lê ?impacto= da URL (links do rodapé). Fica num Suspense para a home continuar estática. */
export function NewsFeedComParametros({ noticias }: { noticias: NoticiaResumo[] }) {
  const impacto = escopoDaUrl(useSearchParams().get("impacto"));
  return <NewsFeed key={impacto} noticias={noticias} impactoInicial={impacto} />;
}

export function NewsFeed({ noticias, impactoInicial = "all" }: { noticias: NoticiaResumo[]; impactoInicial?: FiltroImpacto }) {
  const [impacto, setImpacto] = useState<FiltroImpacto>(impactoInicial);
  const [categoria, setCategoria] = useState<string>("all");
  const [busca, setBusca] = useState("");

  const termo = busca.trim().toLowerCase();
  const filtradas = useMemo(
    () =>
      noticias.filter(
        (n) =>
          (impacto === "all" || n.impactScope === impacto) &&
          (categoria === "all" || n.category === categoria) &&
          (!termo || n.textoBusca.includes(termo))
      ),
    [noticias, impacto, categoria, termo]
  );

  const visaoPadrao = impacto === "all" && categoria === "all" && !termo;

  function limpar() {
    setImpacto("all");
    setCategoria("all");
    setBusca("");
  }

  const caixaBusca = (
    <>
      <label htmlFor="search-input" className="sr-only">
        Buscar notícias, países ou blocos
      </label>
      <div className="search-box">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <circle cx="11" cy="11" r="8"></circle>
          <path d="m21 21-4.3-4.3"></path>
        </svg>
        <input
          type="search"
          id="search-input"
          placeholder="Buscar país, bloco ou tema..."
          autoComplete="off"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
      </div>
    </>
  );

  const pilulas: { valor: FiltroImpacto; rotulo: string; indicador?: string }[] = [
    { valor: "all", rotulo: "Todos os Eventos" },
    ...ESCOPOS.map((e) => ({ valor: e, rotulo: ROTULO_ESCOPO[e], indicador: `pill-indicator--${e}` })),
  ];

  const manchete = visaoPadrao ? filtradas.find((n) => n.featured) ?? filtradas[0] : undefined;
  const grade = manchete ? filtradas.filter((n) => n.slug !== manchete.slug) : filtradas;
  const radar = noticias.filter((n) => n.impactScope === "internacional").slice(0, 5);

  let tituloFeed = "Panorama Internacional & Desdobramentos";
  if (!visaoPadrao) {
    const partes: string[] = [];
    if (impacto !== "all") partes.push(ROTULO_ESCOPO[impacto]);
    if (categoria !== "all") partes.push(categoria);
    if (termo) partes.push(`Busca: "${busca.trim()}"`);
    tituloFeed = partes.join(" · ");
  }
  const contagem = visaoPadrao
    ? `${grade.length} reportagens analíticas`
    : `${filtradas.length} ${filtradas.length === 1 ? "reportagem encontrada" : "reportagens encontradas"}`;

  return (
    <>
      <Masthead busca={caixaBusca}>
        <nav className="filter-bar" aria-label="Filtros editoriais">
          <div className="filter-group">
            <span className="filter-group__label">Raio de Impacto:</span>
            <div className="impact-pills" role="group" aria-label="Filtrar por nível de impacto">
              {pilulas.map((p) => (
                <button
                  key={p.valor}
                  type="button"
                  className={`impact-pill${impacto === p.valor ? " active" : ""}`}
                  aria-pressed={impacto === p.valor}
                  onClick={() => setImpacto(p.valor)}
                >
                  {p.indicador && <span className={`pill-indicator ${p.indicador}`}></span>}
                  {p.rotulo}
                </button>
              ))}
            </div>
          </div>
          <div className="category-tabs" role="group" aria-label="Editorias">
            {["all", ...CATEGORIAS].map((c) => (
              <button
                key={c}
                type="button"
                className={`category-tab${categoria === c ? " active" : ""}`}
                aria-pressed={categoria === c}
                onClick={() => setCategoria(c)}
              >
                {c === "all" ? "Todas" : c}
              </button>
            ))}
          </div>
        </nav>
      </Masthead>

      <main className="main-content container">
        {filtradas.length === 0 ? (
          <section className="empty-state" aria-live="polite">
            <h2>Nenhuma reportagem encontrada para os filtros selecionados</h2>
            <p>Tente limpar os termos de busca ou alternar o raio de impacto.</p>
            <button type="button" className="btn-primary" onClick={limpar}>
              Restaurar todos os destaques
            </button>
          </section>
        ) : (
          <>
            {manchete && (
              <section className="editorial-top">
                <div className="lead-story">
                  <Link href={`/noticias/${manchete.slug}`} className="lead-card">
                    <div className="lead-card__media">
                      <NewsImage src={manchete.image} alt={manchete.title} scope={manchete.impactScope} lazy={false} />
                      <div className="lead-card__overlay-badges">
                        <ImpactBadge noticia={manchete} />
                        <ConsequenceBadge noticia={manchete} />
                      </div>
                    </div>
                    <div className="lead-card__content">
                      <div className="story-meta-top">
                        <span className="story-kicker">
                          {manchete.kicker} &bull; {manchete.category}
                        </span>
                        <span>{manchete.dataFormatada}</span>
                      </div>
                      <h1 className="lead-card__title">{manchete.title}</h1>
                      <p className="lead-card__summary">{manchete.subtitle}</p>
                      <div className="affected-bar">
                        <span className="affected-bar__label">Raio de repercussão:</span>
                        <CountryChips paises={manchete.affectedCountries} />
                      </div>
                      <div className="lead-card__footer">
                        <span>
                          Por <strong>{manchete.author}</strong> ({manchete.location})
                        </span>
                        <span className="read-more-cta">Ler análise completa &rarr;</span>
                      </div>
                    </div>
                  </Link>
                </div>
                <aside className="sidebar-radar" aria-label="Acontecimentos com impacto entre países">
                  <div className="sidebar-radar__header">
                    <span className="radar-tag">ENTRE PAÍSES</span>
                    <h2 className="sidebar-radar__title">Impacto entre países</h2>
                    <p className="sidebar-radar__desc">Decisões e choques que afetam diretamente a economia de outros países ou de um bloco.</p>
                  </div>
                  <div className="radar-list">
                    {radar.length === 0 && <p className="sidebar-radar__desc">Nenhuma matéria recente com impacto entre países.</p>}
                    {radar.map((n) => (
                      <Link key={n.slug} href={`/noticias/${n.slug}`} className="radar-item">
                        <div className="radar-item__corridor">
                          <span>{n.corridorTag || n.affectedCountries.slice(0, 3).join(" • ")}</span>
                          <span>{n.dataFormatada}</span>
                        </div>
                        <h3 className="radar-item__title">{n.title}</h3>
                        <p className="radar-item__summary">{n.subtitle}</p>
                        <div className="news-card__countries">
                          <CountryChips paises={n.affectedCountries} limite={4} />
                        </div>
                      </Link>
                    ))}
                  </div>
                </aside>
              </section>
            )}

            <div className="section-divider">
              <div className="section-divider__title-wrap">
                <h2 className="section-divider__title">{tituloFeed}</h2>
                <span className="results-count">{contagem}</span>
              </div>
              <div className="impact-legend">
                {ESCOPOS.map((e) => (
                  <span key={e} className="legend-item">
                    <span className={`pill-indicator pill-indicator--${e}`}></span> {ROTULO_ESCOPO[e]}
                  </span>
                ))}
              </div>
            </div>

            <section className="news-grid" aria-label="Lista de reportagens">
              {grade.map((n) => (
                <Link key={n.slug} href={`/noticias/${n.slug}`} className="news-card">
                  <div className="news-card__image-wrap">
                    <NewsImage src={n.image} alt={n.title} scope={n.impactScope} />
                  </div>
                  <div className="news-card__body">
                    <div className="story-meta-top">
                      <span className="story-kicker">{n.category}</span>
                      <span className="story-badges">
                        <ImpactBadge noticia={n} />
                        <ConsequenceBadge noticia={n} />
                      </span>
                    </div>
                    <h3 className="news-card__title">{n.title}</h3>
                    <p className="news-card__excerpt">{n.subtitle}</p>
                    <div className="news-card__countries">
                      <CountryChips paises={n.affectedCountries} limite={4} />
                    </div>
                    <div className="news-card__footer">
                      <span>{n.location}</span>
                      <span>
                        {n.dataFormatada} &bull; {n.readTime}
                      </span>
                    </div>
                  </div>
                </Link>
              ))}
            </section>
          </>
        )}
      </main>
    </>
  );
}
