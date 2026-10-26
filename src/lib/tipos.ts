// Tipos e formatação compartilhados entre servidor e navegador (sem acesso a arquivos).

export const CATEGORIAS = [
  "Macroeconomia",
  "Geopolítica & Fronteiras",
  "Energia & Recursos",
  "Comércio & Logística",
  "Tecnologia & Soberania",
] as const;

export type Categoria = (typeof CATEGORIAS)[number];
export type Escopo = "global" | "regional";

export interface Noticia {
  slug: string;
  date: string;
  featured: boolean;
  inRadar?: boolean;
  corridorTag?: string;
  impactScope: Escopo;
  impactLabel: string;
  severity: string;
  category: Categoria;
  kicker: string;
  title: string;
  subtitle: string;
  author: string;
  location: string;
  readTime: string;
  affectedCountries: string[];
  image: string;
  imageCaption?: string;
  source: string;
  sourceUrl: string;
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
