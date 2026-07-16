# Automated Log Triager & Diagnostic Agent

[English](#english-version) | [Português](#versão-em-português)

📺 **[Watch the demo video](docs/demo.mp4)** · **[Assista ao vídeo de demonstração](docs/demo.mp4)**

---

## English Version

### Overview
The **Automated Log Triager & Diagnostic Agent** is a high-performance, asynchronous Python pipeline built to ingest critical transaction failure logs, enrich them using RAG (Retrieval-Augmented Generation) against a technical Known Errors manual, and use AI agents to diagnose and propose structured action plans for Site Reliability Engineering (SRE) and Infrastructure teams.

This project is built from scratch following **Clean Architecture**, **Domain-Driven Design (DDD)**, and **SOLID principles**.

### Live Demo
This project is deployed and publicly accessible - no local setup required to try it:
- **Dashboard:** [log-triager-api.onrender.com](https://log-triager-api.onrender.com/)
- **Swagger docs:** [log-triager-api.onrender.com/docs](https://log-triager-api.onrender.com/docs)

The API runs on Render's Free tier, so if nothing has hit it in a while, the first request can take up to a minute to wake up (see the Resilience Note below) - if the dashboard looks unresponsive at first, give it a moment. The vector DB (Chroma Cloud) is always-on managed infrastructure and is no longer part of that wait.

### Architecture & Tech Stack
- **API Framework:** FastAPI (100% Asynchronous)
- **Language:** Python 3.10+
- **Data Validation:** Pydantic v2
- **Testing:** Pytest
- **Containerization:** Docker & Docker Compose
- **Integrations:** ChromaDB via Chroma Cloud (RAG), LangChain (LLM Orchestration), Tenacity (retry/backoff)
- **LLM Engine:** Google Gemini (Generative AI)

#### System Design
The system enforces strict decoupling between the transport layer (FastAPI), business rules (Agents and Services), and external infrastructure (Vector DB and LLM APIs).

A critical component of this system is the **Data Masking Service**, which aggressively sanitizes Personally Identifiable Information (PII) and sensitive data (e.g., real IPs, emails, and transaction IDs) before payload delivery to the autonomous agents to ensure enterprise-grade security.

### How to Run Locally
> The project is already live (see Live Demo above) - the steps below are only needed if you want to run it locally for development.

#### Prerequisites
- Docker & Docker Compose
- Python 3.10+ (for local development/testing)

#### Quickstart (Docker)
1. Clone the repository and navigate to the project root.
2. Build and start the containerized environment:
   ```bash
   docker compose up --build -d
   ```
3. The real-time diagnostic dashboard will be available at: `http://localhost:8000/`
4. Interactive Swagger documentation: `http://localhost:8000/docs`

#### Running Tests Locally
To run the automated test suite (Pytest) validating domain models and masking logic:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest -v
```

### Deployment
This project is containerized and ready for PaaS platforms like **Render** or **Railway**.
To deploy, connect your GitHub repository to the platform and configure the deploy script to use the included `Dockerfile`. Ensure all environment variables (`GOOGLE_API_KEY`, `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE`) are set in the platform settings. The vector DB is provisioned separately at [trychroma.com](https://www.trychroma.com) (Chroma Cloud) - it isn't part of the app's own deploy.

#### Security Note: ChromaDB Authentication (resolved)

This deployment originally self-hosted ChromaDB on Render's Free instance type, reachable at a public `.onrender.com` URL (Free instances can't receive private-network traffic). We tried protecting that public endpoint with Chroma's built-in static token authentication, but verified with `curl` that requests without a token, or with a wrong one, still returned `200 OK` - the auth provider wasn't being enforced. That turned out to be a known, then-open upstream bug in the official Docker image: [chroma-core/chroma#4288](https://github.com/chroma-core/chroma/issues/4288).

That gap is what motivated moving off self-hosted ChromaDB entirely, onto **Chroma Cloud**. Chroma Cloud authenticates every request with a real API key server-side - there's no broken env-var-based auth provider to work around, because there's no self-hosted auth provider in the picture at all.

#### Resilience Note: Cold Starts and the ChromaDB Client

The API still runs on Render's **Free** tier, which spins down after ~15 minutes of inactivity - that part hasn't changed, and a first request after idle time can still take up to a minute. What has changed is that ChromaDB is no longer a second service hibernating on its own, independent schedule: it's Chroma Cloud, always-on managed infrastructure, with persistent storage (the `known_errors` collection is no longer wiped on every restart the way it was on the old disk-less self-hosted container). `ensure_seeded()` (`app/core/seed_data.py`) still runs before every triage request as a cheap safety net - it's now effectively a no-op after the first-ever seed, rather than something load-bearing on every ChromaDB restart.

The `chromadb` Python client itself still has two behaviors worth documenting, because they're properties of the library, not of any particular host:

- **No client-side request timeout.** `chromadb`'s HTTP-based clients (including `CloudClient`) hardcode their internal `httpx` client with `timeout=None` - confirmed by reading `api/fastapi.py` in the package. A single request can, in principle, hang indefinitely. `VectorStore._connect_and_get_collection()` (`app/services/vector_db.py`) runs each connection attempt in a daemon thread bounded by a hard wall-clock timeout (`threading.Event.wait(timeout=...)`), so a stuck attempt is abandoned instead of hanging the retry loop.
- **A 4-request handshake per connection attempt.** Constructing a `chromadb` `Client` runs `get_user_identity()`, then a tenant lookup and a database lookup, and `get_or_create_collection()` adds a fourth request - all sequential, on every attempt. This is inherent to the chromadb 1.x client and happens against any host. Against the old Render-hosted ChromaDB mid-cold-start, a single leg of that handshake measured ~12s, which is what originally forced a 25s per-attempt timeout and wide retry backoff (5-30s between attempts). Against Chroma Cloud's always-on infrastructure, the same handshake should complete in well under a second, so the timeout and backoff were recalibrated down (10s per attempt, 2-10s between retries) - generous for a slow network, but no longer sized for a cold boot that doesn't happen anymore.
- **429s are still not retried.** Retrying a rate-limit response immediately just adds more requests to an already-throttled window - this is exactly what caused production 429s against Render/Cloudflare's free-tier edge before the check existed (`_worth_retrying()` in `vector_db.py`). Chroma Cloud has its own usage-based rate limits, so this defense stays in place even though the host changed.
- **The dashboard has an on-demand "Retry Knowledge Base Connection" button.** When a report fails with `error_type: "dependency_unavailable"`, the FAILED card shows a button instead of just the error text (see `renderWakeControl()` in `app/templates/index.html`). Clicking it pings `/health`, which exercises the same retrying connection logic the pipeline uses; on success, the `VectorStore` singleton caches the live connection server-side, so the next triage submission skips the reconnect dance and goes through fast.

For a production deployment, the fix that removes the API's own cold start is moving it off the Free tier so it stops spinning down - the vector DB side of this problem is already solved by Chroma Cloud.

### Future Improvements
- Search diagnosed reports (`/api/v1/reports`) by `transaction_id`, `error_code`, or free-text keyword instead of only returning the latest ones.
- Search Known Error Manual entries (`/api/v1/knowledge-base`) by `error_code` or free-text keyword, complementing the existing full-list endpoint.

---
📺 **[Watch the demo video](docs/demo.mp4)** ·

---

## Versão em Português

### Visão Geral
O **Automated Log Triager & Diagnostic Agent** é um pipeline Python assíncrono de alta performance construído para ingerir logs críticos de falhas de transação, enriquecê-los usando RAG (Retrieval-Augmented Generation) baseado em um manual técnico de erros conhecidos, e utilizar Agentes de IA autônomos para diagnosticar e gerar planos de ação estruturados para equipes de SRE (Site Reliability Engineering) e Infraestrutura.

Este projeto foi desenvolvido do zero seguindo **Clean Architecture**, **Domain-Driven Design (DDD)** e os **princípios SOLID**.

### Demo ao Vivo
Este projeto está implantado e é acessível publicamente - não é preciso rodar nada localmente pra testar:
- **Dashboard:** [log-triager-api.onrender.com](https://log-triager-api.onrender.com/)
- **Documentação Swagger:** [log-triager-api.onrender.com/docs](https://log-triager-api.onrender.com/docs)

A API roda no plano Free do Render, então se ninguém acessou por um tempo, a primeira requisição pode levar até um minuto pra acordar (veja a Nota de Resiliência abaixo) - se o dashboard parecer sem resposta no início, dê um tempo. O banco vetorial (Chroma Cloud) é infraestrutura gerenciada sempre ativa e não faz mais parte dessa espera.

### Arquitetura & Stack Tecnológica
- **Framework de API:** FastAPI (100% Assíncrono)
- **Linguagem:** Python 3.10+
- **Validação de Dados:** Pydantic v2
- **Testes:** Pytest
- **Containerização:** Docker & Docker Compose
- **Integrações:** ChromaDB via Chroma Cloud (RAG), LangChain (Orquestração de LLM), Tenacity (retry/backoff)
- **Motor de IA:** Google Gemini (Generative AI)

#### Design do Sistema
O sistema impõe um desacoplamento estrito entre a camada de transporte (FastAPI), as regras de negócio (Agentes e Serviços) e a infraestrutura externa (Banco Vetorial e APIs de LLM).

Um componente crítico deste sistema é o **Data Masking Service** (Serviço de Mascaramento de Dados), que sanitiza agressivamente Informações de Identificação Pessoal (PII) e dados sensíveis (ex: IPs reais, e-mails e IDs de transação) antes da entrega do payload para os agentes autônomos, garantindo segurança de nível empresarial.

### Como Rodar Localmente
> O projeto já está no ar (veja Demo ao Vivo acima) - os passos abaixo só são necessários se você quiser rodar localmente para desenvolvimento.

#### Pré-requisitos
- Docker & Docker Compose
- Python 3.10+ (para desenvolvimento/testes locais)

#### Início Rápido (Docker)
1. Clone o repositório e navegue até a raiz do projeto.
2. Construa e inicie o ambiente containerizado:
   ```bash
   docker compose up --build -d
   ```
3. O Dashboard de diagnóstico em tempo real estará disponível em: `http://localhost:8000/`
4. Documentação interativa do Swagger: `http://localhost:8000/docs`

#### Rodando Testes Localmente
Para rodar a suíte de testes automatizados (Pytest) validando os modelos de domínio e a lógica de mascaramento:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest -v
```

### Deploy
Este projeto é containerizado e está pronto para plataformas PaaS como **Render** ou **Railway**.
Para fazer o deploy, conecte seu repositório GitHub à plataforma e configure o script de deploy para usar o `Dockerfile` incluso. Certifique-se de que todas as variáveis de ambiente (`GOOGLE_API_KEY`, `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE`) estejam configuradas no painel da plataforma. O banco vetorial é provisionado separadamente em [trychroma.com](https://www.trychroma.com) (Chroma Cloud) - não faz parte do deploy do próprio app.

#### Nota de Segurança: Autenticação do ChromaDB (resolvida)

Esta implantação originalmente hospedava o ChromaDB por conta própria no plano Free do Render, acessível por uma URL pública `.onrender.com` (instâncias Free não recebem tráfego de rede privada). Tentamos proteger esse endpoint público com a autenticação por token estático nativa do Chroma, mas confirmamos via `curl` que requisições sem token, ou com um token errado, continuavam retornando `200 OK` - o provider de autenticação não estava sendo aplicado. Isso era um bug conhecido, então aberto, na imagem Docker oficial: [chroma-core/chroma#4288](https://github.com/chroma-core/chroma/issues/4288).

Essa lacuna foi um dos motivos pra sair do ChromaDB self-hosted e migrar pro **Chroma Cloud**. O Chroma Cloud autentica cada requisição com uma API key de verdade no lado do servidor - não existe mais um provider de autenticação quebrado baseado em env var pra contornar, porque não existe mais um provider de autenticação self-hosted no meio do caminho.

#### Nota de Resiliência: Cold Starts e o Cliente ChromaDB

A API ainda roda no plano **Free** do Render, que hiberna após ~15 minutos de inatividade - isso não mudou, e a primeira requisição depois de um tempo parado ainda pode levar até um minuto. O que mudou é que o ChromaDB deixou de ser um segundo serviço hibernando na sua própria agenda independente: agora é o Chroma Cloud, infraestrutura gerenciada sempre ativa, com armazenamento persistente (a collection `known_errors` não é mais apagada a cada restart, como acontecia no antigo container self-hosted sem disco). O `ensure_seeded()` (`app/core/seed_data.py`) continua rodando antes de cada requisição de triagem como uma rede de segurança barata - hoje é efetivamente um no-op depois do primeiro seed, em vez de algo essencial a cada restart do ChromaDB.

O cliente Python `chromadb` em si ainda tem dois comportamentos que vale documentar, porque são propriedades da biblioteca, não de um host específico:

- **Sem timeout de requisição no lado do cliente.** Os clientes HTTP do `chromadb` (incluindo o `CloudClient`) fixam internamente o cliente `httpx` com `timeout=None` - confirmado lendo `api/fastapi.py` dentro do pacote. Em tese, uma requisição pode travar indefinidamente. `VectorStore._connect_and_get_collection()` (`app/services/vector_db.py`) roda cada tentativa de conexão numa thread daemon limitada por um timeout rígido de relógio (`threading.Event.wait(timeout=...)`), então uma tentativa travada é abandonada em vez de travar o loop de retry.
- **Um handshake de 4 requisições por tentativa de conexão.** Construir um `Client` do `chromadb` roda `get_user_identity()`, depois uma busca de tenant e uma busca de database, e `get_or_create_collection()` soma uma quarta requisição - tudo sequencial, em toda tentativa. Isso é inerente ao cliente chromadb 1.x e acontece contra qualquer host. Contra o antigo ChromaDB hospedado no Render em pleno cold start, uma única perna desse handshake media ~12s, o que originalmente forçou um timeout de 25s por tentativa e um backoff largo (5-30s entre tentativas). Contra a infraestrutura sempre ativa do Chroma Cloud, o mesmo handshake deve completar bem abaixo de um segundo, então o timeout e o backoff foram recalibrados pra baixo (10s por tentativa, 2-10s entre retries) - ainda folgado pra uma rede lenta, mas não mais dimensionado pra um cold boot que não acontece mais.
- **429 continua sem ser repetido automaticamente.** Repetir uma resposta de rate limit na hora só adiciona mais requisições a uma janela já limitada - foi exatamente isso que causou os 429 em produção contra a borda Free do Render/Cloudflare antes dessa checagem existir (`_worth_retrying()` em `vector_db.py`). O Chroma Cloud tem seus próprios limites de uso, então essa defesa continua valendo mesmo com a troca de host.
- **O dashboard tem um botão "Retry Knowledge Base Connection" sob demanda.** Quando um relatório falha com `error_type: "dependency_unavailable"`, o card FAILED mostra um botão em vez de só o texto do erro (veja `renderWakeControl()` em `app/templates/index.html`). Clicar nele bate em `/health`, que exercita a mesma lógica de conexão com retry que o pipeline usa; em caso de sucesso, o singleton `VectorStore` guarda a conexão viva no lado do servidor, então a próxima submissão de triagem pula toda a dança de reconexão e vai rápido.

Para uma implantação em produção, a correção que elimina o cold start da própria API é tirá-la do plano Free pra parar de hibernar - o lado do banco vetorial desse problema já está resolvido pelo Chroma Cloud.

### Melhorias Futuras
- Buscar relatórios diagnosticados (`/api/v1/reports`) por `transaction_id`, `error_code` ou palavra-chave livre, em vez de retornar apenas os mais recentes.
- Buscar entradas do Manual de Erros Conhecidos (`/api/v1/knowledge-base`) por `error_code` ou palavra-chave livre, complementando o endpoint de listagem completa já existente.

---
**[Assista ao vídeo de demonstração](docs/demo.mp4)**
