# CONT-EXP-002 — Espaço de referência para criação contínua

Hipótese experimental, versão 0.3.0: o CONTINUUM pode oferecer uma referência persistente entre ferramentas, preparando contextos a partir de fontes autorizadas e preservando contribuições sem exigir classificação a cada movimento.

## Recorte implementado

- Tela principal com entrada livre e texto de trabalho. Referências, proveniência e histórico abrem conforme a necessidade.
- Escrita com salvamento após uma pausa de 900 ms e recuperação local de rascunho. Falhas de rede não removem o texto. Abas e clientes concorrentes usam revisão explícita e conciliação visível.
- Observação periódica de arquivos autorizados prepara pacotes de contexto para até 500 percursos abertos/ativos por ciclo. A mesma observação sem alteração não gera novo pacote.
- Pacote persistente: intenção, trecho final do trabalho, último acontecimento declarado, próximo movimento quando explicitamente escrito sob um cabeçalho correspondente, até cinco evidências versionadas, até três contribuições visíveis e aproximações candidatas.
- Contribuições podem ser dispensadas ou incorporadas. A preferência é preservada por versão documental; uma versão nova pode voltar como candidata. O texto original não é alterado.
- MCP e HTTP compartilham o mesmo estado: clientes podem recuperar o pacote e contribuir com texto. A origem do cliente passa a ser explícita nos novos eventos.

O pacote é organização determinística e lexical. Não resume semanticamente uma conversa nem decide qual caminho é melhor. Não há captura automática de e-mails, conversas, PDF ou Word. O sistema observa Markdown, LaTeX e texto nas raízes já autorizadas. A interface não registra todo pensamento nem exige títulos, tipos e justificativas para cada edição do texto de trabalho.

O próximo movimento é extraído somente de um cabeçalho explícito no texto, por exemplo `Próximo movimento` seguido de um parágrafo. Na ausência desse registro, nenhum próximo passo substantivo é inventado. Arquivos com exemplos hipotéticos recebem aviso contextual nas referências; isso não substitui a leitura completa.

## Experimento de uso

1. Iniciar uma intenção real por MCP ou navegador.
2. Escrever um fragmento de desenvolvimento no espaço compartilhado.
3. Alterar um documento de uma fonte autorizada fora do CONTINUUM.
4. Aguardar a observação: conferir nova versão contextual, sem apertar buscar nem recadastrar a ideia.
5. Examinar uma contribuição, incorporar ou dispensar e continuar escrevendo.
6. Reabrir em outro cliente MCP: recuperar intenção, texto, evidências e percurso. Editar com a revisão atual.
7. Verificar se houve ajuda real: menos reconstrução, uma aproximação útil ou desenvolvimento de um artefato. Registrar distrações e sugestões superficiais. Não inferir ganho de produtividade apenas de testes técnicos.

## Validação técnica

`python3 -m unittest discover -s tests -v` verifica preservação, origem, idempotência, snapshots, retomada em outro processo MCP e conflitos de revisão.

O teste opcional `tests/browser_smoke.cjs` usa Playwright num servidor e banco temporários. Um observador real detecta a mudança em uma fonte de teste e atualiza o contexto; o navegador verifica escrita, recuperação de falha de rede, dispensa de contribuições, conflito entre ambientes e cinco larguras de tela.

## Limites operacionais

O rascunho local depende do navegador e da origem. O conteúdo confirmado pelo servidor fica no SQLite, que precisa de backup próprio. Contribuições são trechos de fontes não confiáveis, renderizados como texto. Sua incorporação é uma escolha explícita; instruções dentro das fontes nunca autorizam ações.

Pacotes preservam snapshots e eventos, mas o rebuild integral das projeções permanece pendente. Uma alteração em qualquer parte do catálogo pode preparar novo pacote para percursos ativos, mesmo que sua relevância para um percurso específico seja pequena; a política incremental ainda deve ser aperfeiçoada com dados de uso.
