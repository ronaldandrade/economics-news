# agente-noticias

Agente que lê vários sites de notícias, encontra os acontecimentos de economia mundial que **aparecem em mais de um site**, escreve um resumo em português juntando o que cada fonte diz e publica no site MERIDIAN (a pasta acima, `economics-news`) como JSON em `content/noticias/`.

```
fontes.json ──► 1. coletar ──► 2. agrupar ──► 3. resumir ──► 4. verificar ──► 5. publicar
 (RSS)          manchetes      mesmo fato     texto novo     números e      JSON do site (PR)
                das últimas    em ≥ 2 sites   com fontes     estilo         ou API do site
                24 h           (pt e en)      atribuídas         │          (MDX ou API)
                                                                 └─ falhou 2× ─► saida/revisar/
```

## Como funciona cada etapa

| Etapa | Arquivo | Quem decide | O que faz |
|---|---|---|---|
| Coletar | `coletar.py` | código | Lê os feeds RSS de `fontes.json`, fica com as manchetes da janela (`janela_horas`), remove duplicatas e parâmetros de rastreio (`utm_*`) dos links e guarda a maior imagem que o feed oferece. Descompacta feeds em gzip. Um feed fora do ar não derruba os outros. |
| Agrupar | `agrupar.py` | IA + código | O modelo recebe todas as manchetes numeradas e junta as que tratam do **mesmo fato**, inclusive entre português e inglês. Cada grupo recebe um `alcance_economico` (`global`, `internacional`, `nacional` ou `nao_economico`) e o canal pelo qual atinge outros países. O código então confere: **descarta o que não for `global` nem `internacional`** (política, eleições, esportes, celebridades e medidas só internas), descarta números de itens inventados, impede item em dois grupos e **exige `min_fontes` veículos diferentes** (fontes com o mesmo `grupo`, como BBC Business e BBC News Brasil, contam como um). Os grupos são ordenados por número de veículos, depois relevância, depois recência. |
| Não repetir | `estado.py` | IA + código | `dados/estado.json` guarda o que foi publicado nos últimos `dias_memoria` dias. Um grupo é descartado se metade dos links já foi publicada ou se o modelo marca que é o mesmo acontecimento sem fato novo. |
| Resumir | `extrair.py`, `resumir.py` | IA | Baixa o texto e o `og:image` de cada artigo (com `trafilatura`; se der paywall, usa o resumo e a imagem do feed) e pede um resumo original, com números atribuídos às fontes, um campo de divergências e a classificação do site: alcance (`global`/`internacional`/`nacional`) e consequência (`acompanhamento`/`relevante`/`critica`) como campos separados, editoria, chapéu, local e países. Consequência crítica exige `base_consequencia` com números das fontes, e o `verificar.py` confere esses números. |
| Verificar | `verificar.py` | código | **Todo número do resumo precisa aparecer em alguma fonte** (aceita 4.5 = 4,5 e 1,200 = 1.200). Também barra travessão, "vale ressaltar", "papel fundamental" e outros padrões da skill `humanizar`. Se falhar, o modelo recebe a lista de problemas e tenta de novo; se falhar outra vez, o post vai para `saida/revisar/` e **não é publicado**. |
| Publicar | `publicar.py` | código | Grava `content/noticias/AAAA-MM-DD_slug.json` no formato do site (com imagem, fontes e a marca `generatedByAI`) e abre um PR. O acontecimento mais repetido da execução vira manchete (`featured`). Também sabe gravar `.mdx` ou enviar para uma API. |

A IA nunca decide sozinha o que é verdade: as regras que importam (mínimo de fontes, números com fonte, não repetir) são verificadas em código.

## Instalação

O agente fica dentro do repositório do site e publica nele (`"repositorio": ".."`).

```bash
cd ~/projetos/economics-news/agente-noticias
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp config.exemplo.json config.json
mkdir -p ~/.config/agente-noticias
install -m 600 /dev/null ~/.config/agente-noticias/env
echo 'ANTHROPIC_API_KEY=sk-ant-...' > ~/.config/agente-noticias/env
```

Teste os feeds (em 26/10/2026 as 11 responderam; remova as que passarem a falhar):

```bash
.venv/bin/python -m agente_noticias verificar-feeds
```

Primeira execução, sem publicar nada:

```bash
set -a; . ~/.config/agente-noticias/env; set +a
.venv/bin/python -m agente_noticias executar --seco
```

Leia os JSON em `saida/seco/`. Para ver como ficam no site, copie um para `../content/noticias/` e rode `npm run dev` na pasta do site (apague a cópia depois). Rode umas 3 ou 4 vezes em dias diferentes antes de ligar a publicação.

## Configuração (`config.json`)

| Campo | Padrão | Efeito |
|---|---|---|
| `janela_horas` | 24 | idade máxima das manchetes |
| `min_fontes` | 2 | quantos sites diferentes precisam noticiar o fato |
| `max_posts` | 3 | posts por execução |
| `extrair_texto` | true | baixa o artigo inteiro para o resumo (mais qualidade, mais tokens) |
| `dias_memoria` | 5 | por quantos dias um evento publicado bloqueia repetição |
| `modelos.agrupar` / `modelos.resumir` | `claude-haiku-5-5` | troque `resumir` por `claude-sonnet-5-5` para textos melhores, a ~10× o custo |

### Publicar no site MERIDIAN (padrão)

```json
"publicacao": {
  "tipo": "site_json",
  "repositorio": "..",
  "pasta": "content/noticias",
  "git": "pr",
  "branch_base": "main"
}
```

Caminho relativo em `repositorio` é contado a partir da pasta do agente. Cada post vira um JSON validado pelo build do site; se o slug já existir, ganha o sufixo `-2`. `git` aceita:
- `"pr"`: cria a branch `noticias/AAAA-MM-DD` a partir de `origin/main`, commita os JSON, faz push, abre um PR com `gh` e **devolve o repositório à branch em que estava**. A Vercel gera o preview e **você faz o merge**. Recomendado.
- `"commit"`: commita e faz push direto na branch atual. Se for a `main`, publica sem revisão.
- `"nenhum"`: só grava os arquivos.

O repositório precisa estar sem alterações pendentes em arquivos versionados na hora da execução (o agente recusa e não publica), e o `gh` precisa estar logado (`gh auth login`).

### Publicar como MDX (blog Next.js)

Use `"tipo": "arquivo"` com `"pasta": "src/content/posts"`, `"separador_slug": "_"` e `"frontmatter_extra"`. Grava frontmatter + resumo + "Em resumo" + divergências + fontes. As opções de `git` são as mesmas.

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

Cada fonte tem `nome`, `idioma` (`pt` ou `en`), `url` do feed RSS e, opcionalmente, `grupo`: fontes do mesmo veículo com o mesmo `grupo` contam como uma só no critério de `min_fontes`. Quanto mais fontes de países diferentes, melhor o critério "repetido entre sites" separa o que é importante do que é pauta de um veículo só. Feeds de seção (economia) rendem mais que feeds gerais.

## Rodar à mão (uma vez por dia)

Depois da instalação, um comando faz tudo:

```bash
~/projetos/economics-news/agente-noticias/rodar.sh          # coleta, resume e abre o PR
~/projetos/economics-news/agente-noticias/rodar.sh --seco   # só grava em saida/seco
```

O script carrega a chave de `~/.config/agente-noticias/env` e avisa se faltar o `.venv`, o `config.json` ou a chave. No fim aparece o link do PR: abra, confira o preview da Vercel e faça o merge.

Se passar mais de um dia sem rodar, aumente `janela_horas` no `config.json` (48 para dois dias), senão as notícias do dia pulado ficam de fora.

## Agendar (2× por dia, opcional)

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

Os 17 testes rodam sem internet e sem chave de API: usam feeds de exemplo em `tests/fixtures/` (com uma fonte quebrada de propósito) e um cliente de IA falso. Cobrem coleta (imagem do feed, gzip), agrupamento por veículo, a checagem de números, a nova tentativa, o envio para revisão, o JSON no formato do site, a publicação por PR num repositório Git local (MDX e JSON, com slug repetido) e o bloqueio de repetição na segunda execução.

## Limitações

- **Agrupamento por IA pode errar.** Dois fatos parecidos (duas decisões de juros no mesmo dia) podem cair juntos. O relatório em `logs/` mostra cada grupo e suas fontes.
- **A checagem de números não pega atribuição errada.** Se a fonte A diz 4,5% e o resumo atribui o número à fonte B, passa. Por isso o modo `pr` é o padrão.
- **Paywall.** Sites fechados entregam só o resumo do feed; o texto do post fica mais raso para esse acontecimento.
- **Direitos autorais.** O agente escreve um texto próprio e linka as fontes, com no máximo uma citação curta. Não altere o prompt para reproduzir os artigos.
- **Feeds mudam.** Rode `verificar-feeds` quando uma fonte parar de aparecer nos relatórios. Feeds sem data (como o da Nikkei Asia) ficam de fora, porque o filtro de janela deixaria passar matérias antigas.
- **Imagens.** Vêm do `og:image` da fonte ou do feed; algumas (Guardian) trazem a marca do veículo no canto. Sem imagem, o site mostra o SVG de reserva.
- **Classificação.** Alcance, editoria e países são escolhidos pela IA a partir das fontes; o código só confere o formato. Revise no PR.
- **Sem chamada real testada.** Os testes usam um cliente falso; a primeira execução com a API deve ser em `--seco`.
