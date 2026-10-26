import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CountryChips, ImpactBadge, Masthead, UtilityBar } from "@/components/Editorial";
import { NewsImage } from "@/components/NewsImage";
import { formatarData, formatarDataLonga, noticiaPorSlug, relacionadas, todasNoticias } from "@/lib/noticias";

// Só existem as matérias geradas no build; qualquer outro slug dá 404.
export const dynamicParams = false;

export function generateStaticParams() {
  return todasNoticias().map((n) => ({ slug: n.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const noticia = noticiaPorSlug((await params).slug);
  if (!noticia) return {};
  return {
    title: noticia.title,
    description: noticia.subtitle,
    alternates: { canonical: `/noticias/${noticia.slug}` },
    openGraph: {
      type: "article",
      title: noticia.title,
      description: noticia.subtitle,
      publishedTime: noticia.date,
      images: [{ url: noticia.image, alt: noticia.title }],
    },
    twitter: { card: "summary_large_image", title: noticia.title, description: noticia.subtitle, images: [noticia.image] },
  };
}

export default async function PaginaNoticia({ params }: { params: Promise<{ slug: string }> }) {
  const noticia = noticiaPorSlug((await params).slug);
  if (!noticia) notFound();
  const outras = relacionadas(noticia);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: noticia.title,
    description: noticia.subtitle,
    image: [noticia.image],
    datePublished: noticia.date,
    author: { "@type": "Organization", name: noticia.author },
    isBasedOn: noticia.sourceUrl,
  };

  return (
    <>
      <UtilityBar edicao={{ iso: noticia.date, texto: formatarDataLonga(noticia.date) }} />
      <Masthead />
      <main className="main-content container">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }} />
        <div className="article-page">
          <article className="modal-article">
            <div className="modal-article__topbar">
              <div className="modal-article__badges">
                <ImpactBadge noticia={noticia} />
                <span className="country-chip">{noticia.category}</span>
              </div>
              <Link href="/" className="modal-close-btn">
                &larr; Voltar à capa
              </Link>
            </div>

            <div className="modal-article__scroll">
              <header className="modal-article__header">
                <p className="modal-article__kicker">{noticia.kicker}</p>
                <h1 className="modal-article__title">{noticia.title}</h1>
                <p className="modal-article__subtitle">{noticia.subtitle}</p>
                <div className="modal-article__byline">
                  <div className="byline-author">
                    <strong>Por {noticia.author}</strong>
                    <span> · {noticia.location}</span>
                  </div>
                  <div className="byline-meta">
                    <time dateTime={noticia.date}>{formatarData(noticia.date)}</time>{" "}
                    <span>&bull;</span>{" "}
                    <span>{noticia.readTime}</span>
                  </div>
                </div>
              </header>

              <figure className="modal-article__figure">
                <NewsImage src={noticia.image} alt={noticia.title} scope={noticia.impactScope} lazy={false} />
                {noticia.imageCaption && <figcaption>{noticia.imageCaption}</figcaption>}
              </figure>

              <section className="impact-briefing" aria-label="Resumo de impacto geopolítico">
                <div className="impact-briefing__header">
                  <h2 className="impact-briefing__title">Mapeamento de Repercussão Internacional</h2>
                  <span className="severity-badge">{noticia.severity || "Monitoramento Ativo"}</span>
                </div>
                <div className="impact-briefing__affected">
                  <span className="affected-label">Países / Blocos diretamente afetados:</span>
                  <div className="country-tags">
                    <CountryChips paises={noticia.affectedCountries} />
                  </div>
                </div>
                {noticia.keyPoints.length > 0 && (
                  <div className="impact-briefing__why">
                    <h3>Por que este evento importa:</h3>
                    <ul>
                      {noticia.keyPoints.map((p) => (
                        <li key={p}>{p}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </section>

              <p className="modal-article__source">
                Fonte:{" "}
                <a href={noticia.sourceUrl} target="_blank" rel="noopener noreferrer">
                  {noticia.source} &rarr; ler a matéria original
                </a>
              </p>

              <div className="modal-article__body">
                {noticia.body.map((p) => (
                  <p key={p}>{p}</p>
                ))}
              </div>

              {outras.length > 0 && (
                <section className="modal-related">
                  <h3 className="modal-related__title">Outras leituras de impacto relacionado</h3>
                  <div className="modal-related__grid">
                    {outras.map((r) => (
                      <Link key={r.slug} href={`/noticias/${r.slug}`} className="related-mini-card">
                        <ImpactBadge noticia={r} />
                        <h4>{r.title}</h4>
                      </Link>
                    ))}
                  </div>
                </section>
              )}
            </div>
          </article>
        </div>
      </main>
    </>
  );
}
