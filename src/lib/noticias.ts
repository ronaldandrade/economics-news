import fs from "node:fs";
import path from "node:path";
import { CATEGORIAS, CONSEQUENCIAS, ESCOPOS, type Noticia } from "./tipos";

export * from "./tipos";

/**
 * Notícias guardadas como arquivos JSON em content/noticias/ (um por matéria).
 * O nome do arquivo segue AAAA-MM-DD_slug.json. O agente de notícias grava
 * novos arquivos e abre um PR; a Vercel publica no merge.
 */

const PASTA = path.join(process.cwd(), "content", "noticias");

function validar(n: Noticia, arquivo: string): Noticia {
  const erros: string[] = [];
  const texto = ["slug", "title", "subtitle", "author", "location", "kicker", "source", "sourceUrl"] as const;
  for (const campo of texto) {
    if (typeof n[campo] !== "string" || !n[campo].trim()) erros.push(`"${campo}" vazio`);
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(n.date ?? "")) erros.push(`"date" deve ser AAAA-MM-DD`);
  // "regional" era o valor antigo: a matéria precisa ser reclassificada à mão, não convertida automaticamente
  if (!ESCOPOS.includes(n.impactScope)) erros.push(`"impactScope" deve ser ${ESCOPOS.join(", ")} (recebido: ${n.impactScope})`);
  if (!CONSEQUENCIAS.includes(n.consequence)) erros.push(`"consequence" deve ser ${CONSEQUENCIAS.join(", ")} (recebido: ${n.consequence})`);
  if (n.consequence === "critica" && !n.consequenceBasis?.trim()) erros.push(`"consequence" crítica exige "consequenceBasis" com a evidência das fontes`);
  if (!CATEGORIAS.includes(n.category)) erros.push(`"category" desconhecida: ${n.category}`);
  if (!Array.isArray(n.body) || n.body.length === 0) erros.push(`"body" sem parágrafos`);
  if (!Array.isArray(n.affectedCountries)) erros.push(`"affectedCountries" deve ser uma lista`);
  if (!/^https:\/\//.test(n.sourceUrl ?? "")) erros.push(`"sourceUrl" deve começar com https://`);
  if (n.image && !/^https:\/\//.test(n.image)) erros.push(`"image" deve começar com https://`);
  for (const f of n.sources ?? []) {
    if (!f.name || !/^https:\/\//.test(f.url ?? "")) erros.push(`fonte inválida em "sources": ${JSON.stringify(f)}`);
  }
  if (!/^[a-z0-9-]+$/.test(n.slug ?? "")) erros.push(`"slug" só aceita a-z, 0-9 e hífen`);
  if (erros.length) throw new Error(`content/noticias/${arquivo}: ${erros.join("; ")}`);
  return { ...n, featured: Boolean(n.featured), keyPoints: n.keyPoints ?? [] };
}

let cache: Noticia[] | null = null;

/** Todas as notícias, da mais recente para a mais antiga. */
export function todasNoticias(): Noticia[] {
  if (cache) return cache;
  const arquivos = fs.readdirSync(PASTA).filter((a) => a.endsWith(".json"));
  const noticias = arquivos.map((arquivo) =>
    validar(JSON.parse(fs.readFileSync(path.join(PASTA, arquivo), "utf8")), arquivo)
  );
  const slugs = new Set<string>();
  for (const n of noticias) {
    if (slugs.has(n.slug)) throw new Error(`slug repetido em content/noticias: ${n.slug}`);
    slugs.add(n.slug);
  }
  // Mais recente primeiro; no mesmo dia, o destaque vem antes.
  cache = noticias.sort((a, b) => b.date.localeCompare(a.date) || Number(b.featured) - Number(a.featured));
  return cache;
}

export function noticiaPorSlug(slug: string): Noticia | undefined {
  return todasNoticias().find((n) => n.slug === slug);
}

/** Até duas matérias do mesmo escopo de impacto ou da mesma editoria. */
export function relacionadas(noticia: Noticia, limite = 2): Noticia[] {
  return todasNoticias()
    .filter((n) => n.slug !== noticia.slug && (n.impactScope === noticia.impactScope || n.category === noticia.category))
    .slice(0, limite);
}
