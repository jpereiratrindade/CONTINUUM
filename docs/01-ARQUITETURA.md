# CONT-ADR-001 — Arquitetura experimental e contratos

**Versão:** 0.1.0 · **Estado:** Accepted-for-experiment (não arquitetura definitiva)

## 1. Escolhas revisáveis

- Python 3.11+ / biblioteca-padrão: velocidade de experimentação e inspeção.
- SQLite + FTS5: armazenamento local, transações, busca lexical e migração futura possível.
- Servidor HTTP em loopback com HTML/CSS/JS sem dependências externas: experiência navegável em Linux e dispositivos locais (sem exposição externa).
- LLM local apenas como adaptador **opcional** e **não autoritativo**.
- Sem automação externa: escrita só em workspace dedicado e mediante ação explícita; varredura periódica é leitura autorizada.

Essas são decisões técnicas instrumentais; não constituintes da hipótese científica.

## 2. Fluxo de responsabilidade

```text
Diretórios autorizados (.md/.tex/.txt)
      |  hash + bytes + fragmentação
      v
Observador com limites de tamanho
      |                       ___________________________
      v                      |                           |
Journal append-only <-------| trajetória / decisão humana|
      |                      |___________________________|
      |                             |
      v                             v
Snapshots imutáveis          Projeção de nós e relações
      |                             |
      +--------------+--------------+
                     |
               Busca FTS5
                     |
             Retomada contextual
                /           \
      Conexões candidatas   Roteiro Markdown
                \           /
             Interface investigativa
                     |
         (opcional) interpretação LLM
```

O journal e os snapshots são **históricos**. `documents`, `nodes`, `links`, `chunks` e `chunks_fts` são **projeções operacionais**; mutáveis, reconstituíveis apenas parcialmente no F0 (não há comando de rebuild completo). A reconstrução integral das projeções requer uma evolução testada da semântica de todos os tipos de evento.

## 3. Contratos de evidência

| Canal | Estado de evidência | Afirmação que o sistema pode fazer |
|---|---|---|
| Arquivo observado | `observed` | Estes bytes foram lidos nesse instante e têm este hash |
| Questão e revisão | `declared` | Uma pessoa registrou esta formulação/revisão |
| Relação declarada | `declared` + `candidate` / `endorsed` / `rejected` | Uma pessoa registrou ou rejeitou um vínculo |
| Semelhança de documentos | `candidate`, base `lexical_overlap` | O algoritmo encontrou termos em comum |
| Roteiro novo | `generated` | O programa criou um arquivo derivado de uma consulta |
| Resposta LLM | `unverified_llm_suggestion` | Um modelo propôs texto interpretativo, sem validação |

A data da observação de um arquivo **não** é a data da sua criação nem prova que uma ideia surgiu naquele instante.

## 4. Modelo de estado

- `events`: seq, event_id, stream_id, kind, payload, source_type, source_ref, occurred_at, recorded_at, evidence_state, previous_hash, event_hash.
- `document_versions`: evento, id do documento, bytes originais, hash e momento observado. Append-only.
- `sources`: diretórios explicitamente autorizados.
- `documents`: projeção atual de textos observados e presença no último exame válido.
- `chunks` + `chunks_fts`: índice de recuperação dos textos atuais.
- `nodes`: identificadores estáveis para questões, ideias, hipóteses, decisões, experimentos, oportunidades.
- `links`: relações declaradas, com estado e justificativa.

Alterar o status de um nó produz `node_revised`, com `before`, `after` e `reason`, antes de atualizar a projeção. Criar um vínculo não atribui validação científica.

## 5. APIs F0

| Método | Caminho | Operação |
|---|---|---|
| GET | `/api/dashboard` | Métricas, questões recentes, trilha, integridade |
| GET | `/api/ask?q=…` | Recuperação lexical + relações candidatas |
| GET | `/api/export?q=…` | Roteiro Markdown sem persistência de arquivo |
| GET | `/api/trajectory?id=…` | Histórico e links de um nó |
| GET | `/api/sources`, `/api/health` | Fontes e status local |
| POST | `/api/sources` | Autorizar diretório existente |
| POST | `/api/sources/active` | Pausar ou reativar fonte autorizada, preservando o histórico |
| POST | `/api/scan` | Observar fontes autorizadas |
| POST | `/api/nodes` | Declarar novo elemento |
| POST | `/api/nodes/revise` | Revisar com justificativa |
| POST | `/api/links` | Declarar vínculo |
| POST | `/api/draft` | Criar roteiro em workspace separado |
| POST | `/api/explore` | Reflexão opcional via Ollama local |

POST exige JSON, `X-Lab-Intent: user`, Host/Origin local e limite de 64 KiB. A aplicação **não** provê autenticação de rede; exige execução no próprio computador, sem proxy, túnel nem exposição em rede. Não há mecanismo de proteção contra processos maliciosos rodando sob a mesma conta do usuário.

## 6. Limites deliberados

- FTS5 recupera termos; não reconstrói conceitos, argumentos nem referências cruzadas profundas.
- Documentos PDF/DOCX, imagens, conversas e mensagens não são processados; extensões suportadas: Markdown, TXT, TeX.
- Não há backup automático, retenção seletiva ou exclusão segura de dados históricos.
- Projeções atuais não possuem rebuild histórico completo.
- Caminhos e conteúdo dos arquivos ficam no banco local; **não adequado a material confidencial sem tratamento específico**.
- A falta de confirmação técnica do estado de um documento não autoriza concluir que foi apagado pelo autor.
- O algoritmo lexical pode produzir falsos positivos e ignorar relações importantes sem vocabulário compartilhado.
- As respostas Ollama podem alucinar, inclusive citações; o usuário deve confrontá-las com os IDs e fontes retornados pelo buscador.

## 7. Evoluções apenas mediante evidência de necessidade

F1 — Reconstituição auditável de projeções, exportação de linhagem completa, testes de ergonomia e desempenho com corpus real.

F2 — Recuperação híbrida (lexical + representação semântica) com corpus de avaliação e taxa de falsos vínculos; modelos locais opcionais e referências verificadas.

F3 — Ingestão documental incremental, contratos com outros ambientes (EVIDA/IdeaWalker/TESSITURA), orquestração de ações autorizadas e políticas explícitas de privacidade e reversibilidade.

A ordem de evolução pode ser revisada diante de resultados experimentais. Não há compromisso de implementar todas as fases.
