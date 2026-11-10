# CONT-PLAN-001 — CONTINUUM: da memória de registros à continuidade intelectual produtiva

**Versão:** 0.1.0  
**Data de referência:** 2026-11-10  
**Estado:** proposta constituinte e roteiro de engenharia; **não** decisão aceita nem implementação concluída  
**Natureza:** documento de trabalho para discussão e execução pela equipe  
**Estilo de entrega:** CAVEMAN FULL — sem atalhos conceituais, sem pressupor que integração técnica demonstre avanço intelectual  
**Referenciais:** REA · RIT · MPRR · Sempre pronto, sempre incompleto

---

## 0. ORDEM DIRETA À EQUIPE

**NÃO COMECEM POR EMBEDDINGS. NÃO COMECEM POR UMA TELA DE GRAFO. NÃO COMECEM POR UM NOVO EXPERIMENTO.**

Comecem pela capacidade que falta: **representar, recuperar e utilizar as transformações que ocorrem no desenvolvimento de uma investigação**.

Não basta encontrar a conversa, exibir o documento, recuperar o commit, ou resumir um histórico. O CONTINUUM precisa ser capaz de ajudar a compreender **o que mudou, diante de qual problema, com que razões declaradas, o que permaneceu em aberto e o que pode ser retomado ou reinterpretado**. Em seguida, deve poder **propor relações e movimentos intelectuais novos**, sem apresentá-los como fatos ou decisões.

**Resultado de produto procurado:** ao retornar a uma questão em desenvolvimento, a pessoa deve encontrar uma reconstrução crítica e rastreável do percurso, o que foi contestado, as razões disponíveis, tensões atuais e possibilidades de desenvolvimento — sem classificar manualmente cada frase nem navegar por tabelas de eventos.

A interpretação gerada é **hipótese revisável**, não extração infalível de intenções.

---

## 1. PROBLEMA CONSTITUINTE

### 1.1 O que existe, mas é insuficiente

O projeto já preserva eventos, snapshots documentais, versões de notas, questões, algumas relações declaradas e referências; possui recuperação lexical, acesso HTTP/MCP e integração local opcional com Ollama.

Essas capacidades são necessárias. **Não constituem, por si, continuidade intelectual produtiva.** A consulta externa realizada no CONT-EXP-003 evidenciou interoperabilidade e recuperação histórica; a experiência ainda podia ser descrita como *ler um texto em outra plataforma*.

A presença de uma base de dados consistente não equivale à presença de uma inteligência histórica. Um resumo produzido por LLM também não equivale automaticamente a uma contribuição intelectual.

### 1.2 O que percebemos agora

O material intelectualmente relevante está distribuído **também** nas interações pelas quais soluções foram propostas, confrontadas, abandonadas, recuperadas ou reelaboradas. O documento final preserva apenas parte da gênese. O commit comprova uma alteração em artefatos, não a razão intelectual completa de sua existência.

**Hipótese constituinte candidata:** a *transformação intelectual investigável*, situada em trajetórias históricas e relacionais, pode tornar-se uma unidade fundamental de trabalho do CONTINUUM, em diálogo com questões, fontes e artefatos.

**Não declarar esta hipótese demonstrada.** É orientação de desenho a examinar e revisar.

### 1.3 Formulação orientadora

> Como o CONTINUUM pode reconstruir e investigar a constituição e a transformação de questões, hipóteses, objeções, decisões e possibilidades, utilizando sua história para apoiar novos movimentos intelectuais, sem apagar incertezas nem fabricar conexões?

---

## 2. REGRAS NÃO NEGOCIÁVEIS

1. **A fonte permanece fonte.** Uma conversa, nota ou código observado não pode ser substituído pelo resumo do modelo.
2. **O histórico não é uma sentença de verdade.** Ele demonstra o que foi registrado/observado, não que as afirmações registradas sejam corretas.
3. **Interpretação posterior não pode ser retrodatada.** Distinguir `occurred_at`, `recorded_at`, `interpreted_at` e, quando possível, `valid_from`.
4. **Objeção é dado intelectual de primeira ordem.** Não sumir com razões de rejeição quando a solução for retomada.
5. **A cronologia não prova causalidade.** A resposta B após a pergunta A não garante que A tenha causado B; registrar evidências e estatuto da relação.
6. **Não inferir estados mentais como fatos.** Crença, intenção, motivação e aprendizagem atribuídas a pessoas só podem ser descritas como interpretações, salvo declaração explícita pertinente.
7. **Automação exploratória, sem autoridade epistêmica irrestrita.** O sistema pode procurar, relacionar, formular, contrastar, priorizar e sugerir; não transforma automaticamente uma hipótese em decisão ou conclusão científica validada.
8. **Não exigir anotação humana de cada turno.** Captura e processamento podem ser automatizados; revisão humana entra por relevância, risco e decisão substantiva.
9. **Não deixar o índice definir a realidade.** Ausência de achados em fontes observadas significa *ausência de evidência recuperada no escopo disponível*.
10. **Nenhum fluxo automático deve escrever ou alterar fontes externas.** Escritas derivadas em workspace próprio e sob contrato específico; ações externas requerem autorização própria.
11. **Ingestão de conversas somente com escopo e autorização explícitos.** Nem todo histórico está disponível, nem toda conversa pode ser apropriada, armazenada ou enviada a um modelo.
12. **Incompletude visível.** Permitir uma trajetória parcial, sem obrigar a preencher uma ontologia total.
13: **Integridade não impede governança de privacidade.** Histórico append-only exige política específica para dados pessoais: minimização, exclusão do índice e procedimento de remoção/expurgo quando aplicável. Não prometer simultaneamente imutabilidade absoluta e exclusão efetiva sem resolver essa tensão.
14. **Git e SQLite permanecem infraestrutura.** Decisão de produto não pode ser guiada pelo que é mais fácil tabular ou versionar.

---

## 3. MODELO CONCEITUAL — O QUE O LABORATÓRIO PRECISA RECONHECER

### 3.1 Três planos que não podem ser confundidos

**PLANO A — REGISTROS ORIGINAIS (evidência de ocorrência/declaração).** Conteúdo e metadados de diálogos, documentos, decisões explícitas, eventos e artefatos. Hashes, versões e citações localizáveis.

**PLANO B — RECONSTRUÇÕES INTERPRETATIVAS (hipóteses do motor).** Passagens candidatas identificadas como formulação, proposta, crítica, resposta, reformulação, tensão, alternativa, condição ou revisão. Sempre com trechos de sustentação e método/versão de interpretação.

**PLANO C — CONHECIMENTO DE TRABALHO (resultados revisáveis).** Trajetórias constituídas, questões abertas, razões preservadas, padrões candidatos, restrições, alertas sobre soluções já criticadas, oportunidades e próximos movimentos.

Nunca sobrescrever o Plano A quando B ou C mudarem. B e C podem ser reconstruídos, invalidados, contraditos e versionados.

### 3.2 Objetos mínimos (sem ontologia total)

- `SourceRecord`: documento, diálogo, evento, referência ou versão observada e autorizada.
- `SourceSpan`: trecho ancorado em posição verificável e versão da fonte; sem inferência.
- `QuestionThread`: questão ou intenção que atravessa conversas, projetos e documentos.
- `IntellectualMove`: candidato a movimento intelectual situado (propor, objetar, qualificar, reformular, decidir, suspender, reabrir, experimentar, distinguir etc.).
- `Transformation`: relação contextualizada entre formulações/posições em momentos distintos; **pode ter bifurcações e múltiplas razões**.
- `CandidateRelation`: hipótese de relação semântica, temporal, estrutural ou argumentativa, com evidências e contraprovas.
- `ConstraintOrObjection`: razão explícita de insuficiência, condição ou limitação, com escopo e possível validade temporal.
- `InterpretiveProposal`: síntese, analogia, tensão ou oportunidade proposta pelo motor, com versão e rastreabilidade.
- `HumanDisposition`: aceitação, rejeição, correção ou adiamento e, se fornecida, justificativa contextual.

### 3.3 Diferenciar relações

Adotar vocabulário expansível e versionado:
- `responds_to` — responde ou retoma uma formulação;
- `objects_to` — contesta uma proposição ou uma condição;
- `reformulates` — cria nova formulação com vínculo histórico explícito ou candidato;
- `constrains` — enuncia condição limitante;
- `supports` / `challenges` — apresenta apoio ou tensão argumentativa;
- `revives` — traz de volta proposta antes abandonada ou suspensa;
- `alternates_with` — registra possibilidades concorrentes;
- `analogous_to` — analogia interpretativa, não identidade;
- `depends_on` — dependência proposta ou declarada;
- `informs` — possível contribuição para uma questão ou solução.

---

## 4. CASO DE REFERÊNCIA (NÃO O PRIMEIRO EXPERIMENTO)

**Percurso conhecido:** LAC/CONTINUUM, 8–10 de novembro de 2026.

1. Problema inicial: organizar e retomar trabalho distribuído.
2. Primeiras respostas: repositórios, commits, documentos, painéis.
3. Objeção: `commit é ferramenta e não fim`.
4. Objeção: uma máquina de escrever/planilha melhorada não resolve o propósito.
5. Avanço operacional: acesso MCP ao mesmo registro em outro cliente.
6. Objeção: `como está é como ler um texto em outra plataforma`.
7. Reformulação: recuperar não é interpretar ou desenvolver.
8. Nova proposta: RAG, vetores e análise contrastiva.
9. Nova objeção: mesmo a análise de conteúdo perde a história de como as ideias mudaram.
10. Formulação candidata: investigar transformações intelectuais e o papel histórico das objeções.

---

## 5. INVARIANTES DE ACEITE DE ENGENHARIA (INV-T01 A INV-T15)

- **INV-T01**: nenhuma interpretação altera o texto original do diálogo ou documento.
- **INV-T02**: toda interpretação candidata possui ao menos um trecho localizável e versão verificável; caso contrário, é apresentada como hipótese sem lastro e não participa de síntese fundamentada.
- **INV-T03**: a interpretação informa modelo/método, versão e momento da análise.
- **INV-T04**: relação entre turnos nunca se confirma apenas por proximidade temporal.
- **INV-T05**: importação repetida de material idêntico não duplica turnos, movimentos ou notificações.
- **INV-T06**: revisão de interpretação não apaga a anterior; retirada por privacidade segue política distinta e explícita.
- **INV-T07**: objeções rejeitadas/incorporadas/retomadas preservam contexto e não se tornam política universal.
- **INV-T08**: fonte pausada/revogada não pode originar novos processamentos após a revogação; índices e caches derivados devem obedecer à política de acesso e retenção.
- **INV-T09**: o sistema reconhece `sem evidência suficiente` como saída válida e não penalizada.
- **INV-T10**: fontes não confiáveis não podem instruir o LLM a executar ferramentas ou ampliar permissões.
- **INV-T11**: o sistema não afirma ter lido conversas ou projetos que não foram efetivamente autorizados e importados.
- **INV-T12**: interpretação candidata não é promovida a declaração humana nem conclusão científica por repetição de chamadas.
- **INV-T13**: cada camada interpretativa pode ser reconstituída ou invalidada sem adulterar o journal.
- **INV-T14**: interface deve permitir chegar à fonte exata da objeção e ver pelo menos uma leitura alternativa quando a relação for controversa.
- **INV-T15**: o histórico deve poder impedir *operacionalmente* a repetição automática de proposta já rejeitada no mesmo escopo, sem impedir sua retomada fundamentada em outro contexto.
