// Endereço público do site, usado em metadados, sitemap e robots.
// Defina NEXT_PUBLIC_SITE_URL ao ligar um domínio próprio; na Vercel o domínio de produção já vem preenchido.
export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ??
  (process.env.VERCEL_PROJECT_PRODUCTION_URL ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}` : "http://localhost:3000");

export const SITE_NOME = "MERIDIAN";
export const SITE_DESCRICAO =
  "Portal de notícias econômicas e geopolíticas em português, com foco em eventos de impacto global e transfronteiriço e link para as fontes originais.";
