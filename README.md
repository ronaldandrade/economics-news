# economics-news (MERIDIAN)

Site em Next.js que publica, em português, resumos de notícias reais de economia mundial, com imagem e link para a matéria original.

## Como rodar

```bash
git clone <url-do-repositorio> economics-news
cd economics-news
npm install
npm run dev        # http://localhost:3000
```

Para conferir antes de publicar:

```bash
npm run lint
npm run build      # gera todas as páginas estáticas e valida os JSON de content/noticias
npm start          # serve o build em http://localhost:3000
```

Na Vercel, importe o repositório e use as configurações padrão de Next.js. Ao ligar um domínio próprio, defina `NEXT_PUBLIC_SITE_URL` (ex.: `https://meridian.com.br`); sem ela, o sitemap e os metadados usam o domínio de produção da Vercel.

## Estrutura

```
content/noticias/            uma notícia por arquivo: AAAA-MM-DD_slug.json
src/app/layout.tsx           fontes, tema, rodapé e metadados globais
src/app/page.tsx             capa: manchete, radar regional e grade
src/app/noticias/[slug]/     página de cada matéria (estática, com Open Graph e JSON-LD)
src/app/sitemap.ts           sitemap.xml com todas as matérias
src/app/robots.ts            robots.txt
src/app/globals.css          estilos do site
src/components/NewsFeed.tsx  filtros, busca e cartões da capa (roda no navegador)
src/components/Editorial.tsx cabeçalho, rodapé, selos de impacto
src/components/NewsImage.tsx imagem da fonte com SVG de reserva se falhar
src/lib/noticias.ts          lê e valida os JSON (só no servidor/build)
src/lib/tipos.ts             tipo Noticia, editorias e formatação de datas
agente-noticias/             agente em Python que coleta e resume as notícias (ver o README dele)
```

## Como funciona

**Notícias em arquivos.** Cada matéria é um JSON em `content/noticias/`. No build, `src/lib/noticias.ts` lê todos, valida os campos obrigatórios e ordena do mais recente para o mais antigo. Um arquivo com campo faltando, data fora do formato, editoria desconhecida ou slug repetido **faz o build falhar** com o nome do arquivo e o problema, e o site no ar continua na versão anterior.

Campos de cada notícia:

| Campo | Obrigatório | Uso |
|---|---|---|
| `slug` | sim | endereço `/noticias/<slug>` (a-z, 0-9 e hífen) |
| `date` | sim | `AAAA-MM-DD`, ordena a capa |
| `featured` | não | `true` põe a matéria como manchete do dia |
| `inRadar`, `corridorTag` | não | aparece na coluna "Efeito Dominó Regional" |
| `impactScope` | sim | `global` ou `regional` (filtro de impacto) |
| `impactLabel`, `severity`, `kicker` | sim | selos e chapéu |
| `category` | sim | uma das editorias de `src/lib/tipos.ts` |
| `title`, `subtitle`, `body` | sim | título, linha fina e parágrafos |
| `keyPoints` | não | lista "Por que este evento importa" |
| `author`, `location`, `readTime` | sim | assinatura |
| `affectedCountries` | sim | chips de países |
| `image`, `imageCaption` | não | URL da imagem publicada pela fonte; sem ela aparece o SVG de reserva |
| `source`, `sourceUrl` | sim | nome e link da matéria original (`https://`) |
| `sources` | não | lista `{name, title, url}` quando o resumo junta várias fontes; a página mostra todas |
| `generatedByAI` | não | `true` mostra o aviso "Resumo produzido com auxílio de IA" |

**Publicar uma notícia nova** é adicionar um arquivo JSON e fazer o merge na `main`: a Vercel refaz o build e a matéria ganha página própria e entrada no sitemap. As antigas continuam no ar com o mesmo endereço.

**Agente de notícias.** `agente-noticias/` lê 11 feeds RSS, junta os fatos noticiados por pelo menos 2 veículos, escreve o resumo com a API da Anthropic e grava os JSON neste formato numa branch `noticias/AAAA-MM-DD`, abrindo um PR. Você revisa o preview da Vercel e faz o merge. Instalação, agendamento e custo estão em `agente-noticias/README.md`.

**Capa.** `page.tsx` carrega as 60 mais recentes e manda ao navegador só o necessário para os cartões e a busca. A manchete é a mais recente com `featured: true` (ou a mais recente de todas). Os filtros de impacto e editoria e a busca rodam no navegador. Os links do rodapé usam `/?impacto=global` e `/?impacto=regional`.

**Tema.** Um script curto no `<body>` aplica o tema salvo (ou o do sistema) antes da primeira pintura, então não há piscada ao carregar no modo escuro.

**Imagens.** Vêm direto dos sites das fontes, com `referrerpolicy="no-referrer"`. Não passam pelo `next/image` porque cada fonte usa um domínio diferente. Se uma imagem não carregar, aparece um SVG com a cor do escopo de impacto.

## Limitações

- O agente ainda não rodou com a API real: os testes usam um cliente de IA falso. Faça a primeira execução com `--seco`.
- As imagens dependem dos sites das fontes. Se uma fonte remover a imagem ou bloquear o uso externo, a matéria passa a mostrar o SVG de reserva.
- A busca procura só nas 60 matérias da capa.
- Sem testes automatizados para o site; a verificação é o `npm run build` (que valida o conteúdo) e o `npm run lint`.
