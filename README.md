# CONTINUUM — Laboratório Experimental de Continuidade Intelectual

**Versão:** 0.2.0 · **Estado:** bancada experimental · **Origem:** revisão crítica do LAC, sem substituí-lo.

> **Questão orientadora:** como sustentar a continuidade do trabalho intelectual entre documentos, ideias, decisões, instrumentos e projetos, preservando evidência, temporalidade, incompletude e capacidade de revisão?
>
> **Lema:** Simples, leve. Sempre pronto. Sempre incompleto.

Este é um **sistema executável de pesquisa**, não uma interface fictícia, um gerenciador de commits ou um sistema científico validado. A experiência começa por uma **questão**. O sistema recupera fontes autorizadas, reconstrói registros parciais, distingue declarações e observações, sugere **aproximações lexicais candidatas** e prepara um roteiro Markdown para continuar o trabalho.

Nenhum código do LAC precisa ser substituído ou apagado. O LAC permanece como registro e bancada histórica de engenharia; CONTINUUM testa uma hipótese diferente de interação.

## Executar

Com Python 3.11+ e SQLite com FTS5:

```bash
python3 -m unittest discover -s tests -v
./run.sh --port 8767 --scan-every 180
```

Abrir `http://127.0.0.1:8767`. O projeto usa apenas a biblioteca-padrão Python, sem instalação de dependências.

## API e MCP

A versão 0.2.0 amplia a API HTTP e adiciona MCP via stdio, com 11 ferramentas de leitura e 7 de escrita opcionais. Veja [configuração, endpoints e exemplos](docs/04-API-MCP.md).

```bash
# MCP: o cliente envia JSON-RPC por stdin e recebe respostas em stdout.
python3 -m lab --db ./data/continuum.sqlite mcp

# Habilitar também autorização de fontes, varredura, criação e revisão.
python3 -m lab --db ./data/continuum.sqlite mcp --allow-writes
```

A interface compartilha a [identidade visual do LAC](docs/05-IDENTIDADE-VISUAL.md). Perguntas submetidas por **Investigar** são preservadas em Trajetórias; o último rascunho é restaurado neste navegador.

## Percurso de experimentação (primeiros 15 minutos)

1. Abrir **Fontes observadas** e autorizar **somente uma pasta que se deseja observar**, preferencialmente com arquivos `.md`, `.tex` ou `.txt` de pesquisa. Usar **Observar fontes agora** para conferir o resultado.
2. Em **Explorar questões**, escrever uma questão substantiva (ex.: `Como a idempotência se relaciona à integridade temporal?`). Examinar as referências e suas limitações, não apenas as palavras coincidentes.
3. Em **Trajetórias**, iniciar uma questão e registrar um contexto inicial. Abrir sua história, revisar a compreensão e justificar a mudança. Verificar que o histórico anterior continua acessível.
4. Experimentar **Criar roteiro**. Um novo arquivo `.md` aparecerá no workspace independente (`./workspace/` por padrão). O comando **Exportar MD** gera texto Markdown sem gravar no workspace.
5. Executar `python3 -m lab --db ./data/continuum.sqlite verify` para verificar a cadeia e os snapshots.

As fontes podem ser **pausadas ou reativadas** pela interface. Pausar interrompe a observação futura, mas **não apaga conteúdo histórico**. O observador periódico processa **somente raízes cadastradas e ativas**. Ele ignora links simbólicos, diretórios técnicos, arquivos acima de 1 MiB e extensões fora do conjunto permitido. Limite de 3.000 arquivos elegíveis por raiz; varreduras incompletas não devem ser interpretadas como desaparecimento definitivo.

## Operação CLI

```bash
python3 -m lab --db ./data/continuum.sqlite register "$HOME/Documentos/laboratorio" --label "Laboratório"
python3 -m lab --db ./data/continuum.sqlite scan
python3 -m lab --db ./data/continuum.sqlite verify
python3 -m lab --db ./data/continuum.sqlite anchor --out "$HOME/CONTINUUM_anchor_01.json"
python3 -m lab --db ./data/continuum.sqlite verify-anchor "$HOME/CONTINUUM_anchor_01.json"
```

A âncora deve ser guardada **fora da pasta do banco**, idealmente com backup independente. Sem âncora externa, a remoção fraudulenta do último evento pode não ser detectável apenas pela cadeia interna; SHA-256 não autentica autoria nem verdade científica.

### LLM local opcional

Somente se houver Ollama instalado e o usuário desejar conduzir um experimento interpretativo:

```bash
./run.sh --port 8767 --scan-every 180 --ollama-model qwen2.5:14b
```

A opção **Explorar hipóteses com modelo local** ficará disponível. As respostas são sempre **interpretações não verificadas**, e nunca alteram fatos, fontes, nós ou relações automaticamente. O serviço é acessado **somente** em `http://127.0.0.1:11434`. Nenhuma chamada externa é efetuada pelo CONTINUUM; o operador é responsável pela configuração e política de privacidade do serviço local.

## O que funciona nesta versão

| Percurso | Capacidade efetiva | Limite explícito |
|---|---|---|
| Retomar | Busca FTS5 por termos, snippets com caminho e data de observação | Não substitui compreensão contextual nem lê PDFs |
| Conectar | Correspondências entre documentos de raízes distintas por termos em comum | **Candidata lexical**, sem inferência causal |
| Desenvolver | Roteiro Markdown com fontes, lacunas e próximos passos | Esboço automatizado, requer revisão |
| Acompanhar | Questões, ideias, hipóteses, decisões e experimentos com revisões auditáveis | Requer declaração humana inicial |
| Observar | Varredura periódica de pastas autorizadas; conteúdo versionado em SQLite | Sem integração automática com chats, apps ou Git |
| Preservar | Diário append-only + hash-chain e snapshots históricos imutáveis | Integridade relativa ao armazenamento; âncoras opcionais |
| Investigar com LLM | Síntese exploratória de trechos recuperados via Ollama | Opcional, não verificada e sujeita a erro do modelo |

**Fora do escopo F0:** descoberta semântica confiável, integração de conversas privadas, sincronização entre dispositivos, ações autônomas em sistemas externos, extração de PDFs, gestão multiusuário, backup automático, autenticação para acesso em rede e avaliação científica concluída.

## Estrutura

```text
lab/
  core.py         diário de acontecimentos, fontes, snapshots, trajetórias e vínculos
  retrieval.py    busca lexical, conexões candidatas e roteiro Markdown
  server.py       interface HTTP local, APIs, adaptações e Ollama opcional
  __main__.py     aplicação CLI
web/
  index.html      interface orientada por questão / trajetória / fonte / avaliação
  style.css
  app.js
tests/
  test_lab.py     testes de invariantes e interface HTTP
docs/
  00-CONTRATO.md
  01-ARQUITETURA.md
  02-PROTOCOLO-AVALIACAO.md
  03-RESULTADO-AVALIACAO.md
```

## Regras de uso científico

- **REA:** toda interpretação revista gera evento e justificativa; nunca alterar o evento original.
- **RIT:** distinguir data atribuída ao acontecimento e data de registro, preservar integridade e snapshots.
- **MPRR:** proximidade lexical não prova mecanismo, oportunidade realizada nem causalidade.
- **Sempre pronto / sempre incompleto:** funcionar com uma fonte, e reconhecer ausência de evidência como ausência de evidência **observada**, não ausência de existência.
- **Autonomia responsável:** observar automaticamente fontes **autorizadas**; nunca escrever nelas. A geração de roteiro exige ação explícita e grava em workspace separado.

## Licença e responsabilidade

Código de bancada disponibilizado aqui para pesquisa e avaliação técnica. Antes de distribuição externa, definir licenciamento institucional, política de privacidade, backup e modelo de ameaças. **Não inserir dados sensíveis** sem revisão específica dos controles de acesso e da retenção histórica.

Para os critérios de aceitação, falhas conhecidas e próximas decisões, ver os documentos versionados em `docs/`.
