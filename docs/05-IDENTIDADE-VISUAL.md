# Identidade visual compartilhada com o LAC

Referência: [LAC-LABORATORIO](https://github.com/jpereiratrindade/LAC-LABORATORIO), arquivos `web/style.css` e `web/assets/lac-symbol.svg` da branch `main`, consultados em 9 de novembro de 2026.

- CSS de referência: blob `f9e0dee2397dbf6df8202385c2cfc3671672f14b`.
- Símbolo de laço reutilizado do LAC: blob `07aacf067b4c248060ea639d016148889fc70bd9`.
- Origem e licença do símbolo: repositório LAC-LABORATORIO, [LICENSE](https://github.com/jpereiratrindade/LAC-LABORATORIO/blob/main/LICENSE).

O CONTINUUM usa a mesma paleta: marinho `#061c34`, ciano `#3cc7e7`, âmbar `#ffc06a`, fundo `#eff4fa` e ação verde `#087b56`. Compartilha o cabeçalho horizontal, o símbolo de laço, a navegação lateral, os cartões claros e a pilha tipográfica local Inter/system-ui. O nome CONTINUUM e seu percurso por questões, trajetórias e fontes permanecem próprios.

Os SVGs ficam em `web/assets/continuum-symbol.svg`, `web/assets/continuum-icons.svg` e `web/favicon.svg`. A marca usa o mesmo laço de trajetórias ciano e âmbar do LAC, conforme solicitado; os ícones funcionais são próprios do CONTINUUM. O conjunto contém dez ícones: questão, trajetória, fontes, laboratório, exportação, roteiro, observação, avanço, relação e integridade.

Marca e ícones essenciais são incorporados ao HTML para evitar espaços vazios por falhas de requisição. Os arquivos também são servidos por entradas explícitas no mapa de arquivos estáticos, sem acesso genérico ao filesystem. Nenhuma fonte, imagem ou script externo é carregado pela interface.

## Preservação de perguntas

O campo Explorar questões mantém o último rascunho no `localStorage` da origem atual. Recarregar ou reabrir a mesma origem restaura o texto, sem executar uma investigação automaticamente. Se o armazenamento estiver bloqueado ou cheio, a interface informa a falha.

Ao submeter, a interface usa `POST /api/investigations` com `query` e um UUID `request_id`. O núcleo registra uma questão com o texto completo no corpo e título de até 240 caracteres antes de recuperar o contexto. A questão permanece em Trajetórias e fica acessível pelo MCP. Repetir o mesmo identificador e texto reutiliza o registro, mesmo após revisão da trajetória; reutilizá-lo com outro texto falha. Consultas `GET /api/ask` continuam sem efeitos de escrita.

A recuperação de rascunho depende do mesmo navegador e origem (protocolo, host e porta); o registro submetido reside no SQLite. Perguntas consultadas antes dessa correção não foram automaticamente registradas no banco.

## Verificação no navegador

O teste opcional `tests/browser_smoke.cjs` usa Playwright e cria seu próprio servidor/banco temporário. Valida navegação, SVGs, rascunhos, submissão, falhas de rede e reenvio após perda da resposta, além de cinco larguras de tela. Instalar Playwright em um diretório de desenvolvimento separado e executar com `NODE_PATH` apontando para seu `node_modules`; `CONTINUUM_SCREENSHOTS` define a pasta opcional das capturas. O aplicativo continua sem dependências externas.
