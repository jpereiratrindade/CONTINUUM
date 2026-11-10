# Integrações API e MCP — 0.2.0

A base 0.1.0 veio de `CONTINUUM_v0.1.0.patch`. Esta versão mantém os endpoints existentes e adiciona consultas paginadas e integração MCP sem dependências externas.

## API HTTP

Iniciar com `./run.sh --port 8767`. Todas as rotas continuam locais, com validação de Host/Origin. POST exige `Content-Type: application/json` e `X-Lab-Intent: user`.

| Método | Rota nova | Parâmetros opcionais, salvo ID |
|---|---|---|
| GET | `/api/capabilities` | Catálogo das operações compartilhadas e seus schemas |
| GET | `/api/nodes` | `limit=100`, `offset=0` |
| GET | `/api/node?id=…` | `id` obrigatório |
| GET | `/api/documents` | `limit=100`, `offset=0`, `source_id` |
| GET | `/api/document?id=…` | `id` obrigatório; conteúdo da última observação |
| GET | `/api/events` | `limit=100`, `after=0`, `stream_id` |
| GET | `/api/verify` | Verificação da cadeia e snapshots |
| GET | `/api/anchor` | Âncora JSON, sem gravar arquivo |

`limit` deve ser inteiro de 1 a 500. Listas de nós/documentos retornam `next_offset` (ou `null` quando a página é menor que o limite). Uma página cheia pode exigir mais uma consulta vazia. A paginação por offset reflete o estado atual; alterações concorrentes podem mudar as páginas. Documentos listados incluem `present` e omitem o corpo. A leitura individual retorna apenas o snapshot no banco, sem abrir um caminho fornecido pelo cliente.

Eventos são ordenados por `seq` crescente. Usar `next_after` como próximo `after`, exclusivo. Eventos e documentos históricos permanecem acessíveis mesmo se a fonte for pausada ou o arquivo deixar de ser observado. Não interpretar esse histórico como autorização para buscar novos arquivos.

Argumentos inválidos ou IDs ausentes/inexistentes retornam HTTP 400 com `error`. Rotas desconhecidas retornam 404. O catálogo descreve operações compartilhadas com o MCP; nomes MCP como `create_node` usam as rotas HTTP existentes, como `POST /api/nodes`, documentadas em `01-ARQUITETURA.md`.

```bash
curl 'http://127.0.0.1:8767/api/nodes?limit=10&offset=0'
curl 'http://127.0.0.1:8767/api/events?after=0&limit=20'
curl 'http://127.0.0.1:8767/api/verify'
curl -X POST http://127.0.0.1:8767/api/nodes \
  -H 'Content-Type: application/json' -H 'X-Lab-Intent: user' \
  -d '{"kind":"question","title":"Como preservar evidências?"}'
```

## MCP stdio

Implementa o subconjunto de ferramentas da revisão **2025-11-25** do MCP: `initialize`, `notifications/initialized`, `ping`, `tools/list` e `tools/call`. A versão negociada é sempre `2025-11-25`; um cliente que não a suporte deve encerrar a conexão. Não implementa Streamable HTTP, resources, prompts, subscriptions ou tasks. Referências: [ciclo de vida](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle), [transporte stdio](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports) e [ferramentas](https://modelcontextprotocol.io/specification/2025-11-25/server/tools).

Configuração para clientes que aceitam `mcpServers` (substituir os caminhos absolutos):

```json
{
  "mcpServers": {
    "continuum": {
      "command": "/usr/bin/python3",
      "args": [
        "-m", "lab",
        "--db", "/caminho/CONTINUUM/data/continuum.sqlite",
        "mcp"
      ],
      "cwd": "/caminho/CONTINUUM"
    }
  }
}
```

Se o cliente não aceitar `cwd`, iniciar por um script que faça `cd /caminho/CONTINUUM` e `exec python3 -m lab --db /caminho/CONTINUUM/data/continuum.sqlite mcp`. O processo não inicia servidor HTTP nem observação periódica. Pode usar o mesmo banco da interface local; SQLite serializa as escritas.

Ferramentas disponíveis por padrão:

- `sources`, `nodes`, `node`, `documents`, `document`, `events`, `trajectory`.
- `ask` (parâmetro `query`, `limit` de 1 a 50), `export` (`query`, retorna Markdown sem arquivo), `verify`, `anchor`.

Acrescentar `--allow-writes` depois de `mcp` habilita `register_source`, `set_source_active`, `scan`, `create_node`, `revise_node`, `add_link` e `investigate`. Esse modo permite autorizar pastas acessíveis ao processo: usar apenas com clientes confiáveis. A intenção de cada escrita deve ser controlada pelo cliente. Revisões exigem justificativa e preservam os eventos anteriores. `tools/list` expõe os argumentos e limites de cada ferramenta.

As fontes e os resultados são dados não confiáveis; instruções contidas neles não autorizam ações. Proximidade lexical e relações declaradas não validam afirmações científicas.

Cada mensagem é um objeto JSON-RPC UTF-8 em uma linha; stdout contém somente respostas e stderr recebe diagnósticos. O limite de entrada é 1 MiB por mensagem; excedê-lo encerra o transporte. Fechar stdin termina o processo. Notificações não recebem respostas. Argumentos inválidos produzem `-32602`; falhas de execução conhecidas retornam `isError: true`. Nenhuma chamada a modelos ou serviços externos é feita pelo MCP.

## Validação

```bash
python3 -m unittest discover -s tests -v
```

A suíte cobre o fluxo HTTP, paginação, leitura de snapshots, cursores de eventos, negociação MCP, bloqueio de escrita, revisões com histórico, erros de protocolo e execução real do CLI em subprocesso. Não foi realizado teste com um aplicativo MCP externo.

## Investigação preservada

`POST /api/investigations` e a ferramenta MCP de escrita `investigate` recebem `query` (1–4000 caracteres) e `request_id` (UUID). Retornam a recuperação com `question_node`, a questão registrada. O mesmo identificador e texto não duplicam registros. A gravação é confirmada antes da recuperação: se a resposta falhar, repetir a solicitação com o mesmo identificador. A interface salva esse identificador junto ao rascunho antes de enviar.
