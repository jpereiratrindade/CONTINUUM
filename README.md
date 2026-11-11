# CONTINUUM — Laboratório Experimental de Continuidade Intelectual

**Versão:** 0.4.0 · **Estado:** bancada experimental · **Origem:** revisão crítica do LAC, sem substituí-lo.

> **Questão orientadora:** como sustentar a continuidade do trabalho intelectual entre documentos, ideias, decisões, instrumentos e projetos, preservando evidência, temporalidade, incompletude e capacidade de revisão?
>
> **Lema:** Simples, leve. Sempre pronto. Sempre incompleto.

Este é um **sistema executável de pesquisa**, não uma interface fictícia, um gerenciador de commits ou um sistema científico validado. A experiência começa por uma **ideia, questão ou fragmento**. O sistema recupera fontes autorizadas, reconstrói registros parciais, distingue declarações e observações, sugere **aproximações lexicais candidatas** e prepara um roteiro Markdown para continuar o trabalho.

Nenhum código do LAC precisa ser substituído ou apagado. O LAC permanece como registro e bancada histórica de engenharia; CONTINUUM testa uma hipótese diferente de interação.

## Executar

Com Python 3.11+ e SQLite com FTS5:

```bash
python3 -m unittest discover -s tests -v
./run.sh --port 8767 --scan-every 180
```

Abrir `http://127.0.0.1:8767`. O projeto usa apenas a biblioteca-padrão Python, sem instalação de dependências.

## Continuar criando

1. Em **Fontes observadas**, autorize uma pasta de trabalho. O observador lê `.md`, `.markdown`, `.tex` e `.txt` sem modificar os originais.
2. Em **Continuar**, comece com uma ideia, pergunta ou fragmento. Desenvolva o texto no mesmo espaço; ele é preservado automaticamente.
3. Abra as contribuições em **Ao redor desta ideia** quando forem úteis. Você pode ler a versão completa da fonte, trazer um trecho para o texto ou dispensá-lo.
4. A origem da última edição aparece junto ao texto. Propostas de assistentes ficam separadas: examine o trecho e escolha **Incorporar ao final** ou **Dispensar**. **Ver alterações** permite comparar o texto anterior e o posterior.
5. Feche e retorne: o percurso e seu texto permanecem disponíveis. MCP e navegador compartilham a mesma referência.

A observação periódica (180 segundos por padrão) prepara novos contextos quando as fontes mudam. Cada referência aponta para um snapshot preservado. Contribuições são aproximações lexicais candidatas; não são interpretações verificadas. [Experimento de convergência e automação](docs/06-CONVERGENCIA.md).

## API e MCP

```bash
# Consulta do espaço de referência, sem escrita:
python3 -m lab --db ./data/continuum.sqlite mcp

# Permitir contribuições de clientes locais:
python3 -m lab --db ./data/continuum.sqlite mcp --allow-writes
```

Para contribuições do assistente, use `propose_note`: ela preserva uma proposta sem alterar seu texto. `save_note` continua disponível para edições diretas solicitadas pelo usuário. A incorporação de propostas acontece no navegador.

Ferramentas `reference`, `propose_note`, `save_note`, `refresh_reference`, `review_contribution`, `document_version` e `export_reference` complementam as operações existentes. O texto de trabalho usa revisão explícita para impedir sobrescrita silenciosa entre clientes. Consulte [configuração e contratos](docs/04-API-MCP.md).

A interface compartilha a [identidade visual do LAC](docs/05-IDENTIDADE-VISUAL.md). A versão atual não lê automaticamente conversas de ChatGPT, e-mail, Word ou PDF; integrações futuras devem utilizar o espaço de referência por API/MCP e fontes autorizadas.

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

O endpoint `POST /api/explore` permite explorar hipóteses com o modelo local habilitado. As respostas são sempre **interpretações não verificadas**, e nunca alteram fatos, fontes, nós ou relações automaticamente. O serviço é acessado **somente** em `http://127.0.0.1:11434`. Nenhuma chamada externa é efetuada pelo CONTINUUM; o operador é responsável pela configuração e política de privacidade do serviço local.

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
  continuity.py  espaços de referência, notas e contexto automático
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

CONTINUUM é disponibilizado sob a **GNU General Public License v3.0** (`GPL-3.0-only`). Consulte o texto completo em [LICENSE](LICENSE).

O sistema permanece experimental. **Não inserir dados sensíveis** sem revisão específica dos controles de acesso e da retenção histórica.

Para os critérios de aceitação, falhas conhecidas e próximas decisões, ver os documentos versionados em `docs/`.

## Premissas de desenvolvimento

**Simples, leve. Sempre pronto. Sempre incompleto!**

[Significado e símbolos das premissas](docs/sister-principles/README.md).
