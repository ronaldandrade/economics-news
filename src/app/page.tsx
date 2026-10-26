import { Suspense } from "react";
import { UtilityBar } from "@/components/Editorial";
import { NewsFeed, NewsFeedComParametros, type NoticiaResumo } from "@/components/NewsFeed";
import { formatarData, formatarDataLonga, todasNoticias } from "@/lib/noticias";

// Quantas matérias a home carrega; as mais antigas seguem acessíveis pela URL e pelo sitemap.
const LIMITE_HOME = 60;

export default function Home() {
  const noticias = todasNoticias().slice(0, LIMITE_HOME);
  // O navegador só recebe o necessário para os cartões e a busca, não o texto inteiro.
  const resumos: NoticiaResumo[] = noticias.map(({ keyPoints, body, ...n }) => ({
    ...n,
    dataFormatada: formatarData(n.date),
    textoBusca: [n.title, n.subtitle, n.kicker, n.category, n.location, ...n.affectedCountries, ...keyPoints, ...body]
      .join(" ")
      .toLowerCase(),
  }));
  const ultima = noticias[0]?.date ?? new Date().toISOString().slice(0, 10);

  return (
    <>
      <UtilityBar edicao={{ iso: ultima, texto: formatarDataLonga(ultima) }} />
      {/* O fallback é a home completa sem filtro, então o HTML estático já traz todas as matérias */}
      <Suspense fallback={<NewsFeed noticias={resumos} />}>
        <NewsFeedComParametros noticias={resumos} />
      </Suspense>
    </>
  );
}
