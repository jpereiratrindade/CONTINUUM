# CONT-ADR-TRANSFORMACOES — Transformação Intelectual Investigável e Memória Reflexiva

- **Versão:** 0.1.0
- **Data de referência:** 2026-11-10
- **Estado:** decisão arquitetural experimental (Bloco A do `CONT-PLAN-001`)
- **Referenciais:** REA · RIT · MPRR · Sempre pronto, sempre incompleto

---

## 1. Hipótese Constituinte e Não-Alegações

### 1.1 Hipótese constituinte candidata
A continuidade intelectual não consiste somente na preservação e recuperação de artefatos produzidos (documentos, notas, decisões finais), mas na capacidade de **reconstruir, consultar e reutilizar os processos de transformação** pelos quais questões, propostas, objeções, condições e reformulações se constituem ao longo do tempo.

### 1.2 O que este ADR NÃO alega
1. **Não alega acesso a intenções mentais:** uma reconstrução interpretativa sobre um diálogo ou documento é uma hipótese situada sobre o texto observado (`status: candidate`), nunca um diagnóstico psicológico ou prova de intenção subjetiva.
2. **Não alega causalidade automática por sucessão temporal:** o fato de o turno `t002` suceder `t001` não comprova que `t002` foi causado por `t001` (`INV-T04`).
3. **Não converte rejeição contextual em proibição universal:** uma objeção registrada contra uma proposta vale dentro de um escopo e sob condições específicas (`INV-T07`, `INV-T15`).

---

## 2. Separação Estrita dos Três Planos Epistêmicos

| Plano | Natureza | Exemplos de Objetos | Regra de Mutabilidade |
| :--- | :--- | :--- | :--- |
| **Plano A — Registros Originais** | Evidência de ocorrência ou declaração | `SourceRecord` (diálogo importado, documento), `SourceSpan` (turno/trecho com offsets verificáveis), `events` | Imutável quanto ao conteúdo observado; identificado por `version_hash` (`SHA-256`). |
| **Plano B — Reconstruções Interpretativas** | Hipóteses geradas pelo motor ou declaradas em revisão | `IntellectualMove` (`proposal`, `objection`, `reformulation`, `question`, `qualification`, `decision`, `suspension`), `Transformation`, `CandidateRelation`, `InterpretiveProposal` | Sempre datado com `interpreted_at`, identificado por `method`, `model_digest` e `pipeline_version`. Revisões criam novos eventos sem apagar interpretações anteriores (`INV-T06`, `INV-T13`). |
| **Plano C — Conhecimento de Trabalho** | Estado revisável de condução da investigação | `QuestionThread` (`nodes`), `ConstraintOrObjection` ativa no escopo, `HumanDisposition`, síntese de retomada ("Em que ponto estávamos?") | Projeção reconstruível a partir do journal; atualizada por disposições humanas explícitas ou novas evidências. |

---

## 3. Objetos Mínimos e Vocabulário Relacional Versionado (`v1`)

### 3.1 Tipos de Movimento Intelectual (`MOVE_KINDS`)
- `question`: formulação ou abertura de interrogação investigável.
- `proposal`: proposição de arquitetura, abordagem, hipótese ou solução.
- `objection`: contestação explícita de uma proposta, premissa ou resultado.
- `qualification`: condição limitante, ressalva de escopo ou requisito não atendido.
- `reformulation`: reelaboração do problema ou da proposta em resposta a uma objeção ou tensão.
- `decision`: escolha deliberada com escopo e justificativa.
- `suspension`: adiamento explícito ou pausa de uma linha de investigação.
- `observation`: constatação empírica ou resultado de experimento/teste.

### 3.2 Vocabulário de Relações entre Movimentos (`TRANSFORMATION_RELATIONS`)
Além das relações estruturais básicas (`relates_to`, `supports`, `contradicts`, `evolves_into`, `depends_on`), o modelo de transformações adota:
- `responds_to`: retoma ou responde diretamente a uma formulação anterior;
- `objects_to`: contesta uma proposição ou condição;
- `reformulates`: reelabora uma formulação anterior diante de crítica ou nova evidência;
- `constrains`: impõe condição limitante ou requisito ao movimento alvo;
- `challenges`: introduz tensão argumentativa ou contraprova;
- `revives`: reabre proposta anteriormente suspensa ou rejeitada quando mudam as condições;
- `alternates_with`: registra caminho alternativo concorrente;
- `analogous_to`: aponta isomorfismo ou analogia estrutural entre trajetórias distintas;
- `informs`: fornece subsídio empírico ou conceitual para outro movimento.

Cada vínculo de transformação registra obrigatoriamente:
- `relation`, `state` (`candidate`, `endorsed`, `rejected`, `superseded`), `basis`, `evidence_refs` (lista de `SourceSpan`), `alternative_reading` (leitura alternativa explícita para evitar narrativa linear forçada), `relation_scope`, `interpretation_run_id` e `recorded_at`.

---

## 4. Mapa de Incompatibilidades com a Modelagem Atual (`v0.3.0`) e Estratégia de Migração

1. **`nodes` e `links` (`lab/core.py`):**
   - *Limitação atual:* `nodes` representa apenas macro-elementos declarados manualmente pelo usuário (`question`, `idea`, `hypothesis`, `decision`, `experiment`, `opportunity`); `links` exige justificativa manual e só possui 5 tipos de relação, sem âncoras de trecho (`SourceSpan`) nem `alternative_reading`.
   - *Resolução:* Manter `nodes` e `links` intactos para compatibilidade com a API/MCP existentes, e introduzir as projeções do Plano A/B/C (`dialogues`, `dialogue_turns`, `source_spans`, `intellectual_moves`, `move_transformations`, `move_dispositions`) alimentadas por novos eventos no journal append-only (`dialogue_imported`, `moves_extracted`, `move_rectified`, `move_disposition_recorded`).
2. **`continuity_packages` (`lab/continuity.py`):**
   - *Limitação atual:* `build()` produz apenas correspondência lexical de documentos e ignora a cadeia de transformações (`proposta -> objeção -> reformulação -> dúvida aberta`) e as restrições ativas no escopo da questão.
   - *Resolução:* Enriquecer a consulta de trajetória e de retomada com a **Reconstrução Crítica de Transformações** (`critical_trajectory`), respondendo diretamente:
     1. *Qual proposta foi questionada?*
     2. *O que foi objetado e sob quais condições?*
     3. *O que mudou depois (reformulação)?*
     4. *Qual dúvida ou tensão permaneceu em aberto?*
     5. *Há propostas atuais que repetem uma insuficiência já objetada neste escopo (`INV-T15`)?*

---

## 5. Política de Fontes Autorizadas, Retenção e Privacidade

1. **Consentimento e Escopo Explícito (`INV-T11`):**
   - Nenhuma conversa externa é capturada silenciosamente. A importação de diálogos ocorre exclusivamente por ação explícita em escopo declarado (ex.: `authorized:continuum-research`), preservando o hash `SHA-256` dos bytes ingeridos.
2. **Preservação de Temporalidade Autêntica (`INV-T03`):**
   - Quando um diálogo importado não possuir timestamp por turno, `occurred_at` permanece `null` (jamais preenchido falsamente com `imported_at`).
3. **Isolamento contra Prompt Injection (`INV-T10`):**
   - Conteúdos de diálogos e documentos observados são tratados estritamente como dados não confiáveis do Plano A e jamais podem instruir a execução de ferramentas ou mutações de estado.
4. **Revogação e Expurgo Auditável (`INV-T08`, Regra 13):**
   - Fontes ou diálogos pausados/revogados cessam imediatamente de participar de novas reconstruções ou índices derivados.

---

## 6. Percurso de Uso em Linguagem Comum: O que a pessoa consegue fazer que antes não conseguia?

- **Antes (v0.3.0):** A pessoa abria uma questão no CONTINUUM (no navegador ou no ChatGPT via MCP) e via apenas o próprio texto que havia digitado e uma lista de arquivos Markdown que compartilhavam palavras soltas. Se tivesse discutido três abordagens diferentes em uma conversa, rejeitado duas por motivos fundamentais e reformulado o problema, essa história desaparecia; ao pedir uma sugestão na semana seguinte, o sistema corria o risco de sugerir exatamente a abordagem já descartada.
- **Agora (com Transformações e Memória Reflexiva):**
  1. A pessoa pode **importar um diálogo autorizado** vinculado a uma questão em andamento, sem precisar classificar frase por frase.
  2. O CONTINUUM ancora cada turno em `SourceSpan` verificáveis e reconstrói a cadeia **`proposta -> objeção -> reformulação -> tensão aberta`**, mostrando o trecho exato de origem e ao menos uma leitura alternativa.
  3. Ao retomar a questão (ou ao propor um novo caminho), a pessoa vê imediatamente **o que mudou, quais objeções já foram levantadas naquele escopo e quais dúvidas seguem abertas**.
  4. Se uma nova proposta reincidir nos mesmos termos/pressupostos de uma proposta já objetada naquele escopo, o CONTINUUM emite um **alerta reflexivo de objeção prévia (`INV-T15`)**, citando o turno exato da objeção anterior para que a pessoa decida se a restrição ainda vale ou se as condições mudaram.
