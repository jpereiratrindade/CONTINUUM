# CONT-000 — Contrato constituinte

- **Versão:** 0.1.0
- **Data de referência:** 2026-11-09
- **Estado:** hipótese executável; não validada empiricamente
- **Tipo:** decisão de pesquisa e engenharia

## 1. Problema

O percurso de uma investigação atravessa conversas, textos, versões, decisões, dúvidas, ferramentas e projetos. Um inventário de documentos ou commits não reconstrói por si só a continuidade intelectual. O trabalho se perde, torna-se difícil de retomar e suas conexões potenciais ficam invisíveis.

## 2. Hipótese experimental

Uma interface **orientada por questões e trajetórias**, sobre memória histórica auditável, pode reduzir o esforço de retomada e favorecer a identificação de relações investigáveis **sem converter associações em fatos**.

A hipótese não é presumida verdadeira. O sistema existe para permitir sua refutação.

## 3. Fronteira histórica: LAC

O LAC cumpriu o papel de bancada de observação, idempotência e preservação de acontecimentos. Não se exige compatibilidade binária, reutilização compulsória do seu código nem atualização do repositório original. O novo experimento pode aproveitar seus princípios, não sua interface como restrição.

## 4. Unidade de experiência

**Questão:** situação interrogativa que pode atravessar fontes e projetos; não possui propriedade exclusiva de um documento.

**Trajetória:** sucessão histórica de formulações, decisões, revisões, experimentos e relações a respeito de um elemento. Possui identificador persistente e versões interpretativas recuperáveis.

**Fonte:** registro autorizado com proveniência; não é prova de veracidade por si.

**Candidata relacional:** hipótese de associação com base explícita (no F0, coincidência lexical interfontes), jamais uma causa automaticamente descoberta.

**Roteiro de continuidade:** artefato derivado de resultados recuperados, que distingue fontes, lacunas, questões e próximos testes.

## 5. Compromissos invariantes

- **INV-01**: nenhum diretório observado sem cadastro humano explícito.
- **INV-02**: reobservação de conteúdo inalterado não acrescenta novo evento histórico.
- **INV-03**: eventos são append-only; alterações são novas entradas e preservam o anterior.
- **INV-04**: o modelo registra `occurred_at` e `recorded_at` separadamente.
- **INV-05**: o hash de cada acontecimento incorpora o anterior; versões documentais guardam bytes originais e hash verificável.
- **INV-06**: resultados de busca retornam fonte e origem; um trecho não pode reivindicar ser a totalidade de um documento.
- **INV-07**: toda relação automática é rotulada como candidata, com base lexical e limitação explícitas.
- **INV-08**: revisão humana requer justificativa; sem reescrita histórica.
- **INV-09**: escrita automatizada jamais altera arquivos observados; roteiros são novos arquivos em workspace próprio.
- **INV-10**: ausência de resultados é apresentada como lacuna do corpus observado.
- **INV-11**: integração LLM não recebe autorização para mutação ou chamada de ferramentas.
- **INV-12**: interface HTTP é exclusivamente local, com controle de origem e intenção para escrita.

## 6. Critérios de não substituição

CONTINUUM não assume responsabilidades de domínio de TESSITURA, IdeaWalker, EVIDA, MÉTIS, ELO/OS ou outras aplicações. Integrações futuras deverão ser consumos de evidência com proveniência e contratos testáveis, nunca uma apropriação silenciosa do significado dos seus objetos.

## 7. Critério de aceitação

A versão F0 só é considerada **apta a experimentação controlada** após testes reprodutíveis de integridade, segurança e fluxo ponta a ponta. **Aptidão científica** depende de avaliação com um corpus real, comparativo e casos de falsos vínculos. Testes de software não substituem esse julgamento.

## 8. Tensão deliberada

Automação sem fricção é desejável; autonomia epistêmica irrestrita não. O sistema pode observar e preparar, mas declarações de verdade, validação causal e decisões substantivas permanecem responsabilidades explícitas de pessoas ou de protocolos científicos verificáveis.
