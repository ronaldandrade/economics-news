# agente-noticias

Agente que lê vários sites de notícias, encontra os acontecimentos de economia mundial que **aparecem em mais de um site**, escreve um resumo em português juntando o que cada fonte diz e publica no seu site.

```
fontes.json ──► 1. coletar ──► 2. agrupar ──► 3. resumir ──► 4. verificar ──► 5. publicar
 (RSS)          manchetes      mesmo fato     texto novo     números e      MDX no repo (PR)
                das últimas    em ≥ 2 sites   com fontes     estilo         ou API do site
                24 h           (pt e en)      atribuídas         │
                                                                 └─ falhou 2× ─► saida/revisar/
```

## Como funciona cada etapa

| Etapa | Arquivo | Quem decide | O que faz |
|---|---|---|---|
| Coletar | `coletar.py` | código | Lê os feeds RSS de `fontes.json`, fica com as manchetes da janela (`janela_horas`), remove duplicatas e parâmetros de rastreio (`utm_*`) dos links. Um feed fora do ar não derruba os outros. |
| Agrupar | `agrupar.py` | IA + código | O modelo recebe todas as manchetes numeradas e junta as que tratam do **mesmo fato**, inclusive entre português e inglês, descartando o que não é economia mundial. O código então confere: descarta números de itens inventados, impede item em dois grupos e **exige `min_fontes` sites diferentes**. Os grupos são ordenados por número de sites, depois relevância, depois recência. |
| Não repetir | `estado.py` | IA + código | `dados/estado.json` guarda o que foi publicado nos últimos `dias_memoria` dias. Um grupo é descartado se metade dos links já foi publicada ou se o modelo marca que é o mesmo acontecimento sem fato novo. |
| Resumir | `extrair.py`, `resumir.py` | IA | Baixa o texto de cada artigo (com `trafilatura`; se der paywall, usa o resumo do feed) e pede um resumo original, com números atribuídos às fontes e um campo de divergências. |
| Verificar | `verificar.py` | código | **Todo número do resumo precisa aparecer em alguma fonte** (aceita 4.5 = 4,5 e 1,200 = 1.200). Também barra travessão, "vale ressaltar", "papel fundamental" e outros padrões da skill `humanizar`. Se falhar, o modelo recebe a lista de problemas e tenta de novo; se falhar outra vez, o post vai para `saida/revisar/` e **não é publicado**. |
| Publicar | `publicar.py` | código | Grava o `.mdx` (frontmatter + resumo + "Em resumo" + divergências + lista de fontes com links) ou envia para a API do site. |

A IA nunca decide sozinha o que é verdade: as regras que importam (mínimo de fontes, números com fonte, não repetir) são verificadas em código.

## Instalação

```bash
cd ~
# copie a pasta agente-noticias para ~/agente-noticias
cd ~/agente-noticias
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config.exemplo.json config.json
mkdir -p ~/.config/agente-noticias
install -m 600 /dev/null ~/.config/agente-noticias/env
echo 'ANTHROPIC_API_KEY=sk-ant-...' > ~/.config/agente-noticias/env
```

Teste os feeds (as URLs de `fontes.json` não puderam ser testadas daqui; remova as que falharem):

```bash
.venv/bin/python -m agente_noticias verificar-feeds
```

Primeira execução, sem publicar nada:

```bash
set -a; . ~/.config/agente-noticias/env; set +a
.venv/bin/python -m agente_noticias executar --seco
```

Leia os arquivos em `saida/seco/`. Rode umas 3 ou 4 vezes em dias diferentes antes de ligar a publicação.

## Configuração (`config.json`)

| Campo | Padrão | Efeito |
|---|---|---|
| `janela_horas` | 24 | idade máxima das manchetes |
| `min_fontes` | 2 | quantos sites diferentes precisam noticiar o fato |
| `max_posts` | 3 | posts por execução |
| `extrair_texto` | true | baixa o artigo inteiro para o resumo (mais qualidade, mais tokens) |
| `dias_memoria` | 5 | por quantos dias um evento publicado bloqueia repetição |
| `modelos.agrupar` / `modelos.resumir` | `claude-haiku-5-5` | troque `resumir` por `claude-sonnet-5-5` para textos melhores, a ~10× o custo |

### Publicar no blog (Next.js + MDX, como o `portfolio-math`)

```json
"publicacao": {
  "tipo": "arquivo",
  "repositorio": "~/projetos/economics-news",
  "pasta": "src/content/posts",
  "git": "pr",
  "separador_slug": "_",
  "frontmatter_extra": {"author": "Ronald Andrade", "difficulty": "beginner"},
  "aviso_ia": true
}
```

`git` aceita:
- `"pr"`: cria a branch `noticias/AAAA-MM-DD`, commita, faz push e abre um PR com `gh`. A Vercel gera o preview e **você faz o merge**. Recomendado.
- `"commit"`: commita e faz push direto na branch atual. Se for a `main`, publica sem revisão.
- `"nenhum"`: só grava os arquivos.

O repositório precisa estar sem alterações pendentes, e o `gh` precisa estar logado (`gh auth login`). O MDX gerado passa no validador do blog (`validar_post.mjs`).

### Publicar em outro site (API)

```json
"publicacao": {
  "tipo": "http",
  "url": "https://seusite.com.br/api/noticias",
  "variavel_token": "NOTICIAS_TOKEN"
}
```

Envia um `POST` JSON com `titulo`, `descricao`, `conteudo_markdown`, `pontos`, `tags`, `fontes`, `data` e `categoria`, e o cabeçalho `Authorization: Bearer <token>`. O token vai no mesmo arquivo `env`.

### Fontes (`fontes.json`)

Cada fonte tem `nome`, `idioma` (`pt` ou `en`) e `url` do feed RSS. Quanto mais fontes de países diferentes, melhor o critério "repetido entre sites" separa o que é importante do que é pauta de um veículo só. Feeds de seção (economia) rendem mais que feeds gerais.

## Agendar (2× por dia)

```bash
mkdir -p ~/.config/systemd/user
cp systemd/agente-noticias.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now agente-noticias.timer
systemctl --user list-timers agente-noticias.timer
journalctl --user -u agente-noticias -n 50
```

Para rodar com o notebook desligado, deixe o timer no desktop.

## Custo

Com Haiku 5.5 e 11 fontes, cada execução usa cerca de 20 a 40 mil tokens: menos de US$ 0,02. Cada execução grava em `logs/` um relatório com as manchetes por fonte, os grupos formados, os descartados (e por quê), os posts e o custo estimado. Os preços em `precos_por_milhao` são estimativas; o valor real fica no Console da Anthropic.

## Testes

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest -q tests
```

Os testes rodam sem internet e sem chave de API: usam feeds de exemplo em `tests/fixtures/` (com uma fonte quebrada de propósito) e um cliente de IA falso. Cobrem coleta, agrupamento, a checagem de números, a nova tentativa, o envio para revisão, a publicação por PR num repositório Git local e o bloqueio de repetição na segunda execução.

## Limitações

- **Agrupamento por IA pode errar.** Dois fatos parecidos (duas decisões de juros no mesmo dia) podem cair juntos. O relatório em `logs/` mostra cada grupo e suas fontes.
- **A checagem de números não pega atribuição errada.** Se a fonte A diz 4,5% e o resumo atribui o número à fonte B, passa. Por isso o modo `pr` é o padrão.
- **Paywall.** Sites fechados entregam só o resumo do feed; o texto do post fica mais raso para esse acontecimento.
- **Direitos autorais.** O agente escreve um texto próprio e linka as fontes, com no máximo uma citação curta. Não altere o prompt para reproduzir os artigos.
- **Feeds mudam.** Rode `verificar-feeds` quando uma fonte parar de aparecer nos relatórios.
