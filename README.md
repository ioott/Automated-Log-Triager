# Automated Log Triager & Diagnostic Agent

[English](#english-version) | [Português](#versão-em-português)

📺 **[Watch the demo video](docs/demo.mp4)** · **[Assista ao vídeo de demonstração](docs/demo.mp4)**

---

## English Version

### Overview
The **Automated Log Triager & Diagnostic Agent** is a high-performance, asynchronous Python pipeline built to ingest critical transaction failure logs, enrich them using RAG (Retrieval-Augmented Generation) against a technical Known Errors manual, and use AI agents to diagnose and propose structured action plans for Site Reliability Engineering (SRE) and Infrastructure teams.

This project is built from scratch following **Clean Architecture**, **Domain-Driven Design (DDD)**, and **SOLID principles**.

### Architecture & Tech Stack
- **API Framework:** FastAPI (100% Asynchronous)
- **Language:** Python 3.10+
- **Data Validation:** Pydantic v2
- **Testing:** Pytest
- **Containerization:** Docker & Docker Compose
- **Integrations:** ChromaDB (RAG), LangChain (LLM Orchestration), Tenacity (retry/backoff)
- **LLM Engine:** Google Gemini (Generative AI)

#### System Design
The system enforces strict decoupling between the transport layer (FastAPI), business rules (Agents and Services), and external infrastructure (Vector DB and LLM APIs).

A critical component of this system is the **Data Masking Service**, which aggressively sanitizes Personally Identifiable Information (PII) and sensitive data (e.g., real IPs, emails, and transaction IDs) before payload delivery to the autonomous agents to ensure enterprise-grade security.

### How to Run Locally

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
To deploy, connect your GitHub repository to the platform and configure the deploy script to use the included `Dockerfile`. Ensure all environment variables (e.g., `GOOGLE_API_KEY`) are set in the platform settings.


#### Security Note: ChromaDB Authentication

In this deployment, the ChromaDB service runs on Render's **Free** instance type and is reachable at its public `.onrender.com` URL (Free instances cannot receive private-network traffic, so Render's internal networking isn't an option without upgrading to a paid plan).

We initially tried to protect that public endpoint with Chroma's built-in static token authentication (`CHROMA_SERVER_AUTHN_PROVIDER` / `CHROMA_SERVER_AUTHN_CREDENTIALS`), documented at [docs.trychroma.com](https://docs.trychroma.com). After deploying, we verified with `curl` that requests **without** a token and with a **wrong** token both still returned `200 OK` - the auth provider was not being enforced. This turned out to be a known, currently open upstream bug in the official Docker image: [chroma-core/chroma#4288](https://github.com/chroma-core/chroma/issues/4288). Pinning to a specific stable tag (`1.5.9`, instead of `latest`) did not change the outcome.

Given that, we made a deliberate call: keep the Free tier and the public URL, without relying on a broken auth mechanism to create a false sense of security. The `known_errors` collection stores the Known Error Manual (technical remediation entries), not customer or transaction data, so the exposure is judged acceptable for a portfolio deployment.

**For a production deployment**, the recommended fix is to move ChromaDB to Render's **Starter** plan (or higher) and use its private network URL instead of the public one - private-network traffic never touches the public internet, so this sidesteps the broken env-var auth entirely. See [Render's private network docs](https://render.com/docs/private-network) for details.

#### Resilience Note: ChromaDB Cold Starts

Both services here run on Render's **Free** tier, which spins down after ~15 minutes of inactivity and has no persistent disk. That combination surfaces in two ways worth documenting:

- **The knowledge base gets wiped on every ChromaDB restart.** Since there's no persistent disk, the `known_errors` collection is empty every time the ChromaDB container comes back up - independently of whether the API process itself restarted. `ensure_seeded()` (`app/core/seed_data.py`) re-checks and re-populates the collection both on API startup and before every triage request, so a freshly-restarted ChromaDB instance gets transparently reseeded instead of silently returning "no match" from RAG.
- **Cold starts can take longer than they look like they should.** Waking a sleeping Free instance means Render provisioning a container (~30-50s) *plus* Chroma re-downloading and initializing its default embedding model from scratch, since nothing persists across restarts - in practice this can run well past a minute. `VectorStore._get_collection()` retries the connection with exponential backoff (up to 8 attempts, 2-15s apart, via `tenacity`) instead of failing on the first attempt, so a single triage request can ride out a cold start instead of every request in that window failing outright. If ChromaDB is still unreachable after that retry budget, the failure is classified as `dependency_unavailable` and surfaced on the dashboard as a plain-language "try again shortly" message instead of a raw exception string (see `classify_error()` in `app/core/exceptions.py`).

For a production deployment, the fix that actually removes this class of issue is moving both services off the Free tier so they stop spinning down.

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

### Arquitetura & Stack Tecnológica
- **Framework de API:** FastAPI (100% Assíncrono)
- **Linguagem:** Python 3.10+
- **Validação de Dados:** Pydantic v2
- **Testes:** Pytest
- **Containerização:** Docker & Docker Compose
- **Integrações:** ChromaDB (RAG), LangChain (Orquestração de LLM), Tenacity (retry/backoff)
- **Motor de IA:** Google Gemini (Generative AI)

#### Design do Sistema
O sistema impõe um desacoplamento estrito entre a camada de transporte (FastAPI), as regras de negócio (Agentes e Serviços) e a infraestrutura externa (Banco Vetorial e APIs de LLM).

Um componente crítico deste sistema é o **Data Masking Service** (Serviço de Mascaramento de Dados), que sanitiza agressivamente Informações de Identificação Pessoal (PII) e dados sensíveis (ex: IPs reais, e-mails e IDs de transação) antes da entrega do payload para os agentes autônomos, garantindo segurança de nível empresarial.

### Como Rodar Localmente

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
Para fazer o deploy, conecte seu repositório GitHub à plataforma e configure o script de deploy para usar o `Dockerfile` incluso. Certifique-se de que todas as variáveis de ambiente (ex: `GOOGLE_API_KEY`) estejam configuradas no painel da plataforma.


#### Nota de Seguranca: Autenticacao do ChromaDB

Nesta implantacao, o servico do ChromaDB roda no plano **Free** do Render e e acessado pela sua URL publica `.onrender.com` (instancias Free nao conseguem receber trafego pela rede privada, entao a rede interna do Render nao e uma opcao sem migrar para um plano pago).

Inicialmente tentamos proteger esse endpoint publico com a autenticacao por token estatico nativa do Chroma (`CHROMA_SERVER_AUTHN_PROVIDER` / `CHROMA_SERVER_AUTHN_CREDENTIALS`), documentada em [docs.trychroma.com](https://docs.trychroma.com). Depois do deploy, confirmamos via `curl` que requisicoes **sem** token e com um token **errado** continuavam retornando `200 OK` - o provider de autenticacao nao estava sendo aplicado. Isso e um bug conhecido e atualmente aberto na imagem Docker oficial: [chroma-core/chroma#4288](https://github.com/chroma-core/chroma/issues/4288). Fixar uma tag estavel especifica (`1.5.9`, em vez de `latest`) nao mudou o resultado.

Diante disso, tomamos uma decisao deliberada: manter o plano Free e a URL publica, sem depender de um mecanismo de autenticacao quebrado que criaria uma falsa sensacao de seguranca. A collection `known_errors` guarda o Manual de Erros Conhecidos (entradas tecnicas de remediacao), nao dados de clientes ou de transacoes, entao a exposicao foi julgada aceitavel para uma implantacao de portfolio.

**Para uma implantacao em producao**, a correcao recomendada e migrar o ChromaDB para o plano **Starter** do Render (ou superior) e usar a URL de rede privada em vez da publica - trafego de rede privada nunca passa pela internet publica, entao isso contorna completamente o bug de autenticacao por env var. Veja a [documentacao de rede privada do Render](https://render.com/docs/private-network) para mais detalhes.

#### Nota de Resiliência: Cold Starts do ChromaDB

Os dois serviços aqui rodam no plano **Free** do Render, que hiberna após ~15 minutos de inatividade e não tem disco persistente. Essa combinação aparece de duas formas que vale documentar:

- **A base de conhecimento é apagada a cada restart do ChromaDB.** Como não há disco persistente, a collection `known_errors` fica vazia toda vez que o container do ChromaDB volta - independente de o processo da API ter reiniciado ou não. O `ensure_seeded()` (`app/core/seed_data.py`) reverifica e repopula a collection tanto no startup da API quanto antes de cada requisição de triagem, então uma instância do ChromaDB recém-reiniciada é re-semeada de forma transparente em vez de simplesmente devolver "sem correspondência" no RAG.
- **Cold starts podem demorar mais do que parecem.** Acordar uma instância Free adormecida significa o Render provisionar um container (~30-50s) *mais* o Chroma rebaixar e inicializar do zero seu modelo de embedding padrão, já que nada persiste entre reinícios - na prática isso pode passar bem de um minuto. `VectorStore._get_collection()` tenta reconectar com backoff exponencial (até 8 tentativas, de 2 a 15s entre elas, via `tenacity`) em vez de falhar na primeira tentativa, então uma única requisição de triagem consegue sobreviver a um cold start em vez de toda requisição naquela janela falhar direto. Se o ChromaDB continuar inacessível depois desse orçamento de tentativas, a falha é classificada como `dependency_unavailable` e exibida no dashboard como uma mensagem em linguagem simples pedindo pra tentar de novo, em vez do texto cru da exceção (veja `classify_error()` em `app/core/exceptions.py`).

Para uma implantação em produção, a correção que de fato elimina essa classe de problema é tirar os dois serviços do plano Free, pra pararem de hibernar.

### Melhorias Futuras
- Buscar relatórios diagnosticados (`/api/v1/reports`) por `transaction_id`, `error_code` ou palavra-chave livre, em vez de retornar apenas os mais recentes.
- Buscar entradas do Manual de Erros Conhecidos (`/api/v1/knowledge-base`) por `error_code` ou palavra-chave livre, complementando o endpoint de listagem completa já existente.

---
**[Assista ao vídeo de demonstração](docs/demo.mp4)**
