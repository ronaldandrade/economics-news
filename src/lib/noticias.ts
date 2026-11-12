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
  // A regex sozinha aceita 2026-13-45, que quebra a formatação de data no build com um erro sem o nome do arquivo
  if (!/^\d{4}-\d{2}-\d{2}$/.test(n.date ?? "") || Number.isNaN(Date.parse(`${n.date}T12:00:00Z`))) erros.push(`"date" deve ser uma data AAAA-MM-DD válida`);
  if (typeof n.readTime !== "string") erros.push(`"readTime" deve ser texto`);
  // "regional" era o valor antigo: a matéria precisa ser reclassificada à mão, não convertida automaticamente
  if (!ESCOPOS.includes(n.impactScope)) erros.push(`"impactScope" deve ser ${ESCOPOS.join(", ")} (recebido: ${n.impactScope})`);
  if (!CONSEQUENCIAS.includes(n.consequence)) erros.push(`"consequence" deve ser ${CONSEQUENCIAS.join(", ")} (recebido: ${n.consequence})`);
  if (n.consequence === "critica" && !n.consequenceBasis?.trim()) erros.push(`"consequence" crítica exige "consequenceBasis" com a evidência das fontes`);
  if (!CATEGORIAS.includes(n.category)) erros.push(`"category" desconhecida: ${n.category}`);
  if (!Array.isArray(n.body) || n.body.length === 0) erros.push(`"body" sem parágrafos`);
  if (n.keyPoints !== undefined && !Array.isArray(n.keyPoints)) erros.push(`"keyPoints" deve ser uma lista`);
  if (n.sources !== undefined && !Array.isArray(n.sources)) erros.push(`"sources" deve ser uma lista`);
  if (!Array.isArray(n.affectedCountries)) erros.push(`"affectedCountries" deve ser uma lista`);
  if (!/^https:\/\//.test(n.sourceUrl ?? "")) erros.push(`"sourceUrl" deve começar com https://`);
  if (n.image && !/^https:\/\//.test(n.image)) erros.push(`"image" deve começar com https://`);
  for (const f of Array.isArray(n.sources) ? n.sources : []) {
    if (!f?.name || !/^https:\/\//.test(f.url ?? "")) erros.push(`fonte inválida em "sources": ${JSON.stringify(f)}`);
  }
  if (!/^[a-z0-9-]+$/.test(n.slug ?? "")) erros.push(`"slug" só aceita a-z, 0-9 e hífen`);
  if (erros.length) throw new Error(`content/noticias/${arquivo}: ${erros.join("; ")}`);
  return { ...n, featured: Boolean(n.featured), keyPoints: n.keyPoints ?? [] };
}

let cache: { lista: Noticia[]; porSlug: Map<string, Noticia> } | null = null;

function carregar() {
  // Em desenvolvimento os arquivos são relidos a cada pedido, para uma matéria nova aparecer sem reiniciar o servidor.
  if (cache && process.env.NODE_ENV === "production") return cache;
  const arquivos = fs.readdirSync(PASTA).filter((a) => a.endsWith(".json"));
  const noticias = arquivos.map((arquivo) =>
    validar(JSON.parse(fs.readFileSync(path.join(PASTA, arquivo), "utf8")), arquivo)
  );
  const porSlug = new Map<string, Noticia>();
  for (const n of noticias) {
    if (porSlug.has(n.slug)) throw new Error(`slug repetido em content/noticias: ${n.slug}`);
    porSlug.set(n.slug, n);
  }
  // Mais recente primeiro; no mesmo dia, o destaque vem antes. O slug desempata, porque a ordem
  // de readdir muda de uma máquina para outra e a capa sairia diferente no build local e na Vercel.
  noticias.sort((a, b) => b.date.localeCompare(a.date) || Number(b.featured) - Number(a.featured) || a.slug.localeCompare(b.slug));
  cache = { lista: noticias, porSlug };
  return cache;
}

/** Todas as notícias, da mais recente para a mais antiga. */
export function todasNoticias(): Noticia[] {
  return carregar().lista;
}

export function noticiaPorSlug(slug: string): Noticia | undefined {
  return carregar().porSlug.get(slug);
}

/** Até duas matérias do mesmo escopo de impacto ou da mesma editoria. */
export function relacionadas(noticia: Noticia, limite = 2): Noticia[] {
  return todasNoticias()
    .filter((n) => n.slug !== noticia.slug && (n.impactScope === noticia.impactScope || n.category === noticia.category))
    .slice(0, limite);
}
