# Automated Log Triager & Diagnostic Agent

[English](#english-versoin) | [Português](#versão-em-português)

---

<a name="english"></a>
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
- **Integrations:** ChromaDB (RAG), CrewAI (AI Agents)

#### System Design
The system enforces strict decoupling between the transport layer (FastAPI), business rules (Agents and Services), and external infrastructure (Vector DB and LLM APIs).

A critical component of this system is the **Data Masking Service**, which aggressively sanitizes Personally Identifiable Information (PII) and sensitive data (e.g., real IPs, emails, and transaction IDs) before payload delivery to the LLM to ensure enterprise-grade security.

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
3. The API will be available at: `http://localhost:8000`
4. Interactive Swagger documentation: `http://localhost:8000/docs`

#### Running Tests Locally
To run the automated test suite (Pytest) validating domain models and masking logic:
```bash
pip install -r requirements.txt
PYTHONPATH=. pytest -v
```

### Deployment
This project is containerized and ready for PaaS platforms like **Render** or **Railway**.
To deploy, connect your GitHub repository to the platform and configure the deploy script to use the included `Dockerfile`. Ensure all environment variables (e.g., `OPENAI_API_KEY`) are set in the platform settings.

---

<a name="português"></a>
## Versão em Português

### Visão Geral
O **Automated Log Triager & Diagnostic Agent** é um pipeline Python assíncrono de alta performance construído para ingerir logs críticos de falhas de transação, enriquecê-los usando RAG (Retrieval-Augmented Generation) baseado em um manual técnico de erros conhecidos, e utilizar agentes de IA para diagnosticar e gerar planos de ação estruturados para equipes de SRE (Site Reliability Engineering) e Infraestrutura.

Este projeto foi desenvolvido do zero seguindo **Clean Architecture**, **Domain-Driven Design (DDD)** e os **princípios SOLID**.

### Arquitetura & Stack Tecnológica
- **Framework de API:** FastAPI (100% Assíncrono)
- **Linguagem:** Python 3.10+
- **Validação de Dados:** Pydantic v2
- **Testes:** Pytest
- **Containerização:** Docker & Docker Compose
- **Integrações:** ChromaDB (RAG), CrewAI (Agentes de IA)

#### Design do Sistema
O sistema impõe um desacoplamento estrito entre a camada de transporte (FastAPI), as regras de negócio (Agentes e Serviços) e a infraestrutura externa (Banco Vetorial e APIs de LLM).

Um componente crítico deste sistema é o **Data Masking Service** (Serviço de Mascaramento de Dados), que sanitiza agressivamente Informações de Identificação Pessoal (PII) e dados sensíveis (ex: IPs reais, e-mails e IDs de transação) antes da entrega do payload para o LLM, garantindo segurança de nível empresarial.

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
3. A API estará disponível em: `http://localhost:8000`
4. Documentação interativa do Swagger: `http://localhost:8000/docs`

#### Rodando Testes Localmente
Para rodar a suíte de testes automatizados (Pytest) validando os modelos de domínio e a lógica de mascaramento:
```bash
pip install -r requirements.txt
PYTHONPATH=. pytest -v
```

### Deploy
Este projeto é containerizado e está pronto para plataformas PaaS como **Render** ou **Railway**.
Para fazer o deploy, conecte seu repositório GitHub à plataforma e configure o script de deploy para usar o `Dockerfile` incluso. Certifique-se de que todas as variáveis de ambiente (ex: `OPENAI_API_KEY`) estejam configuradas no painel da plataforma.

---
*Placeholder: [Assista ao Vídeo de Demonstração Aqui]*
