# CONT-EVAL-RESULT-001 — Auditoria inicial da bancada

- **Versão examinada:** 0.1.0
- **Data de referência:** 2026-11-09
- **Estado:** avaliação automatizada inicial; *não substitui estudo empírico*

## Critérios e situação

| Critério | Situação | Evidência / pendência |
|---|---|---|
| Projeto independente do LAC | Implementado | Código autocontido e diretórios separados |
| Interface por questão | Implementado | Busca, retomada, trajetórias, relações e roteiro |
| Observação autorizada | Testado | Registro de raiz, pausa/retomada, e varredura apenas das fontes ativas |
| Reobservação idempotente | Testado | Evento não duplicado ao reler mesmo conteúdo |
| Preservação das revisões | Testado | Event journal imutável + snapshots de bytes originais |
| Integridade relativa ao DB | Testado | Hash encadeado e validação de snapshots |
| Perda da cauda protegida | Condicional | Âncora externa é necessária; sem ela não há detecção garantida |
| Separação hipótese / evidência | Estruturalmente implementada | API e interface rotulam propostas automáticas como candidatas; requer teste humano |
| Recuperação de linguagem natural | Parcial | FTS5 é recuperação lexical, não interpretação semântica |
| Conexões entre projetos | Parcial | Conexões entre arquivos de raízes distintas; não há grafo semântico validado |
| Redução real de esforço | Não avaliada | Exige comparação E1/E3 com tarefas reais |
| Descoberta útil e falsos vínculos | Não avaliada | Exige corpus anotado E2 |
| Segurança local F0 | Testes iniciais | Host/Origin, cabeçalho de intenção, path whitelist, tamanho, symlinks |
| Segurança para deployment externo | Reprovado por escopo | Sem autenticação nem modelo multiusuário: **não expor na rede** |
| LLM local | Disponível opcionalmente | Integração requer Ollama instalado; não valida semântica |
| Reconstrução integral das projeções | Não implementada | Versões/eventos são preservados; rebuild integral pendente |
| Acompanhamento automático de conversas | Não implementado | Exige autorização, conectores e política de privacidade |

## Veredicto provisório

**Apto à experimentação local controlada; não apto a uso como autoridade científica ou memória completa.**

A implementação demonstra que uma interface orientada por questões pode ser executada sobre trilha temporal preservada. Não demonstra, ainda, que essa experiência é superior ao LAC, que descobre oportunidades substantivas, ou que produz melhor conhecimento científico. Essas são hipóteses a avaliar; declarar sua conclusão seria violar REA e MPRR.

## Próximos critérios de parada

O ciclo de avaliação segue até que toda falha crítica da F0 esteja corrigida, cada limite restante tenha comportamento e risco explícitos, e E1–E5 apresentem resultados suficientes para aceitar, corrigir ou rejeitar as hipóteses. **Não exigir desaparecimento de toda incerteza:** rigor demanda registrar as incertezas irredutíveis e escolher experimentos para reduzi-las.
