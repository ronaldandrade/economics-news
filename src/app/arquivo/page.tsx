import type { Metadata } from "next";
import Link from "next/link";
import { ConsequenceBadge, ImpactBadge, Masthead, UtilityBar } from "@/components/Editorial";
import { formatarData, formatarDataLonga, formatarMes, todasNoticias, type Noticia } from "@/lib/noticias";

export const metadata: Metadata = {
  title: "Arquivo",
  description: "Todas as matérias publicadas, da mais recente para a mais antiga, agrupadas por mês.",
  alternates: { canonical: "/arquivo" },
};

// A capa mostra só as matérias mais recentes; aqui ficam todas, em lista leve (sem imagem nem texto).
export default function Arquivo() {
  const noticias = todasNoticias();
  const meses = new Map<string, Noticia[]>();
  for (const n of noticias) {
    const mes = n.date.slice(0, 7);
    meses.set(mes, [...(meses.get(mes) ?? []), n]);
  }
  const ultima = noticias[0]?.date ?? new Date().toISOString().slice(0, 10);

  return (
    <>
      <UtilityBar edicao={{ iso: ultima, texto: formatarDataLonga(ultima) }} />
      <Masthead />
      <main className="main-content container">
        <div className="archive">
          <header className="archive__header">
            <h1 className="archive__title">Arquivo</h1>
            <p className="results-count">
              {noticias.length} {noticias.length === 1 ? "matéria publicada" : "matérias publicadas"}
            </p>
          </header>
          {noticias.length === 0 && <p className="archive__empty">Nenhuma matéria publicada ainda.</p>}
          {[...meses].map(([mes, lista]) => (
            <section key={mes} className="archive__month" aria-labelledby={`mes-${mes}`}>
              <h2 id={`mes-${mes}`} className="archive__month-title">
                {formatarMes(mes)}
              </h2>
              <ul className="archive__list">
                {lista.map((n) => (
                  <li key={n.slug} className="archive__item">
                    <time dateTime={n.date}>{formatarData(n.date)}</time>
                    <div>
                      <Link href={`/noticias/${n.slug}`} className="archive__link">
                        {n.title}
                      </Link>
                      <div className="archive__meta">
                        <span className="story-kicker">{n.category}</span>
                        <span className="story-badges">
                          <ImpactBadge noticia={n} />
                          <ConsequenceBadge noticia={n} />
                        </span>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </main>
    </>
  );
}
