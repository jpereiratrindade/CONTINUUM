# CONT-EVAL-001 — Protocolo de avaliação crítica e possível refutação

- **Versão:** 0.1.0
- **Estado:** protocolo prospectivo, não resultado
- **Tese em exame:** questões e trajetórias podem ser uma interface mais produtiva do que projetos/commits para o trabalho intelectual distribuído.

## 1. Princípio: avaliar até eliminar dúvidas DECIDÍVEIS, não prometer certeza absoluta

"Não haja dúvida" significa aqui nenhuma ambiguidade **não documentada** sobre o comportamento que se pretende aceitar. A incerteza conceitual e empírica legítima deve permanecer explícita. Uma falha relevante reprova o gate e aciona correção/reteste; não pode ser resolvida com retórica.

## 2. Baseline e contrafactual

Comparar, **com as mesmas tarefas e o mesmo corpus**, três modos: (a) busca manual em pastas e conversas acessíveis; (b) LAC histórico; (c) CONTINUUM experimental. Registrar previamente o corpus autorizado, o conjunto de questões e as regras de avaliação. Não escolher apenas casos que favoreçam o novo sistema.

### Experimento E1 — Retomar

- Preparar ao menos 12 questões: 4 recentes, 4 antigas e 4 parcialmente documentadas.
- Para cada questão medir tempo até a primeira reconstrução útil, quantidade de fontes corretas, afirmações sem fonte e trabalho de correção humana.
- Avaliador não deve conhecer previamente a distribuição das fontes; contrabalançar a ordem dos modos comparados.
- **Gate proposto (revisável antes do estudo):** mediana de tempo menor que o baseline manual, cobertura de fontes relevantes >= 80% e **zero afirmações apresentadas como fatos verificados sem proveniência**.

### Experimento E2 — Conectar

- Formar um conjunto de pelo menos 30 pares de documentos com anotações independentes: 10 relações relevantes, 10 relações superficiais e 10 pares sem relação conhecida.
- Medir precisão, revocação e utilidade das conexões, com desacordos documentados.
- **Gate:** não há validação com o algoritmo atual; exigir demonstração de ganho de trabalho e falsos vínculos destacados como tais. Para avanço a F2, pré-especificar metas quantitativas e amostragem.

### Experimento E3 — Desenvolver

- Em 6 sessões reais de trabalho, gerar roteiros e avaliar se foram utilizados, corrigidos, rejeitados ou abandonados.
- Medir minutos gastos revisando um roteiro contra a preparação manual, além de quantas decisões surgem com referências recuperáveis.
- **Gate:** ganho líquido de trabalho sem aumento de erros ou de decisões espúrias.

### Experimento E4 — História e confiança

- Revisar uma interpretação 3 vezes e inspecionar versões, justificativas e suas datas.
- Reimportar conteúdo idêntico; adulterar propositalmente cópia de banco; verificar cadeia e âncora externa.
- Testar varredura incompleta, symlinks, documentos alterados, arquivo que reaparece e perda do último evento.
- **Gate:** todas as invariantes críticas passam; limitações (ex.: perda de cauda sem âncora) ficam visíveis.

### Experimento E5 — Efeito sobre o próprio pensamento

- Após 4 semanas, investigar se o sistema induz a pensar só no que foi indexado ou classificado.
- Verificar se ideias sem artefato documental e contradições não textuais continuam encontrando espaço no processo.
- **Gate:** a interface não deve forçar a redução das questões humanas à ontologia do banco.

## 3. Rubrica de avaliação

| Eixo | Pergunta de falsificação | Evidência aceitável |
|---|---|---|
| REA | O sistema oculta uma revisão ou apresenta uma interpretação nova como antiga? | Eventos antes/depois e justificativas |
| RIT | Confunde data de criação com observação? Não detecta adulteração do que promete proteger? | Datas separadas, hashes e âncoras |
| MPRR | Uma coincidência de palavras aparece como causalidade ou conhecimento provado? | Interface e payload distinguindo candidata de relação comprovada |
| Automação | Reduz trabalho ou acrescenta tarefas de manutenção? | Medição de esforço real, logs e observações |
| Usabilidade | Uma pergunta leva a uma retomada útil sem navegação de repositório? | Testes com questões não ensaiadas |
| Incompletude | Ausência de fonte é tratada como ausência de conhecimento? | Casos com fontes omitidas propositalmente |
| Segurança | Observa ou modifica fonte não autorizada? | Ataques controlados e inspeção |
| Autonomia | Executa ação externa sem consentimento? | Observação de efeitos e contratos de API |

## 4. Diário de experimentação

Para cada tentativa registrar `ID`, data, hipótese, tarefa, condições, fontes autorizadas, resultado esperado, resultado observado, falha, causa provável, decisão e mudança futura. **Não apagar as falhas históricas**; revisões posteriores ganham novos registros.

## 5. Critérios para conclusão

- **Aceitação F0:** componentes implementados, testes automatizados, limites explícitos e percurso utilizável na bancada.
- **Aceitação de produto experimental:** E1–E5 executados com resultados e falhas classificadas, sem bloqueadores críticos.
- **Aceitação científica forte:** requer replicação, contrafactual, base independente e análise de erro suficiente; não concedida pelo patch.

O projeto só deve avançar a uma versão mais complexa se os resultados demonstrarem ganho verificável. Se não demonstrarem, a hipótese da interface precisa ser revista ou rejeitada.
