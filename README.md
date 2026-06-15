# Automated Log Triager & Diagnostic Agent

## Overview
The **Automated Log Triager & Diagnostic Agent** is a high-performance, asynchronous Python pipeline built to ingest critical transaction failure logs, enrich them using RAG (Retrieval-Augmented Generation) against a technical Known Errors manual, and use AI agents to diagnose and propose structured action plans for Site Reliability Engineering (SRE) and Infrastructure teams.

This project is built from scratch following **Clean Architecture**, **Domain-Driven Design (DDD)**, and **SOLID principles**.

## Architecture & Tech Stack
- **API Framework:** FastAPI (100% Asynchronous)
- **Language:** Python 3.10+
- **Data Validation:** Pydantic v2
- **Testing:** Pytest
- **Containerization:** Docker & Docker Compose
- **Upcoming Integrations:** ChromaDB/PGVector (RAG), CrewAI/LangChain (AI Agents)

### System Design
The system enforces strict decoupling between the transport layer (FastAPI), business rules (Agents and Services), and external infrastructure (Vector DB and LLM APIs). 

A critical component of this system is the **Data Masking Service**, which aggressively sanitizes Personally Identifiable Information (PII) and sensitive data (e.g., real IPs, transaction IDs) before payload delivery to the LLM to ensure enterprise-grade security.

## How to Run Locally

### Prerequisites
- Docker & Docker Compose
- Python 3.10+ (for local development/testing)

### Quickstart (Docker)
1. Clone the repository and navigate to the project root.
2. Build and start the containerized environment:
   ```bash
   docker-compose up --build -d
   ```
3. The API will be available at: `http://localhost:8000`
4. Interactive Swagger documentation: `http://localhost:8000/docs`

### Running Tests Locally
To run the automated test suite (Pytest) validating domain models and schemas:
```bash
pip install -r requirements.txt
pytest -v
```

## Deployment
This project is containerized and ready for PaaS platforms like **Render** or **Railway**. 
To deploy, connect your GitHub repository to the platform and configure the deploy script to use the included `Dockerfile`. Ensure all environment variables (e.g., `LLM_API_KEY`) are set in the platform's dashboard.

---
*Placeholder: [Watch the Demonstration Video Here]*
