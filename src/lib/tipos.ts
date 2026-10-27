// Tipos e formatação compartilhados entre servidor e navegador (sem acesso a arquivos).

export const CATEGORIAS = [
  "Macroeconomia",
  "Geopolítica & Fronteiras",
  "Energia & Recursos",
  "Comércio & Logística",
  "Tecnologia & Soberania",
] as const;

export type Categoria = (typeof CATEGORIAS)[number];

/**
 * Alcance geográfico da consequência, não dos países citados nem da sede das empresas.
 * - global: atinge mercados, preços ou cadeias em vários continentes.
 * - internacional: afeta diretamente a economia de dois ou mais países ou de um bloco (vizinhos ou não).
 * - nacional: o efeito descrito nas fontes fica concentrado num país.
 */
export const ESCOPOS = ["global", "internacional", "nacional"] as const;
export type Escopo = (typeof ESCOPOS)[number];

/**
 * Tamanho da consequência, independente do alcance.
 * - acompanhamento: proposta, anúncio ou efeito ainda incerto.
 * - relevante: efeito concreto e medido nas fontes sobre preços, fluxos ou regras de um mercado.
 * - critica: choque amplo já em curso, com números que mostram disrupção séria; exige consequenceBasis.
 */
export const CONSEQUENCIAS = ["acompanhamento", "relevante", "critica"] as const;
export type Consequencia = (typeof CONSEQUENCIAS)[number];

export const ROTULO_ESCOPO: Record<Escopo, string> = {
  global: "Impacto global",
  internacional: "Impacto entre países",
  nacional: "Impacto nacional",
};

export const ROTULO_CONSEQUENCIA: Record<Consequencia, string> = {
  acompanhamento: "Em acompanhamento",
  relevante: "Relevante",
  critica: "Crítica",
};

/** Links antigos usavam ?impacto=regional para o que hoje é "internacional". */
export function escopoDaUrl(valor: string | null): Escopo | "all" {
  if (valor === "regional") return "internacional";
  return (ESCOPOS as readonly string[]).includes(valor ?? "") ? (valor as Escopo) : "all";
}

export interface Noticia {
  slug: string;
  date: string;
  featured: boolean;
  corridorTag?: string;
  impactScope: Escopo;
  consequence: Consequencia;
  /** Evidência das fontes que sustenta a consequência; obrigatória quando é "critica". */
  consequenceBasis?: string;
  category: Categoria;
  kicker: string;
  title: string;
  subtitle: string;
  author: string;
  location: string;
  readTime: string;
  affectedCountries: string[];
  /** Vazio quando a fonte não tem imagem: o site mostra o SVG de reserva. */
  image?: string;
  imageCaption?: string;
  source: string;
  sourceUrl: string;
  /** Todas as fontes quando o resumo junta mais de uma (o agente preenche). */
  sources?: { name: string; title: string; url: string }[];
  /** true nos resumos escritos pelo agente de notícias. */
  generatedByAI?: boolean;
  keyPoints: string[];
  body: string[];
}

const formatoData = new Intl.DateTimeFormat("pt-BR", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const formatoDataLonga = new Intl.DateTimeFormat("pt-BR", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

export function formatarData(data: string): string {
  return formatoData.format(new Date(`${data}T12:00:00Z`)).replace(/\./g, "").replace(/ de /g, " ");
}

export function formatarDataLonga(data: string): string {
  const texto = formatoDataLonga.format(new Date(`${data}T12:00:00Z`));
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}
