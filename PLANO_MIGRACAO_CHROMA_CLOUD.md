# Plano: migrar ChromaDB (Render self-hosted) → Chroma Cloud

Decisão tomada: manter o RAG como serviço externo separado (não embutir busca vetorial no processo da API — é intencional para a narrativa de portfólio) e trocar o host do ChromaDB, do serviço self-hosted no Render Free para o **Chroma Cloud** (oferta gerenciada oficial da Trychroma). A API continua no Render Free.

## Por que isso resolve o problema de verdade, e não só troca de host

O diagnóstico do resumo anterior tinha duas causas distintas misturadas: (1) o serviço ChromaDB no Render Free hiberna e não tem disco persistente, e (2) o cliente Python `chromadb` 1.x tem comportamento problemático por conta própria — `httpx.Client(timeout=None)` fixo (confirmado lendo `chromadb/api/fastapi.py` na versão atual do pacote) e um handshake de 4 requisições sequenciais toda vez que o processo da API constrói um `Client` novo: `get_user_identity()`, `get_tenant()`, `get_database()` (essas três dentro de `Client.__init__` → `_validate_tenant_database()`) e depois `get_or_create_collection()`. Esse handshake de 4 requests é **inerente à classe `Client` do chromadb 1.x** — acontece em qualquer host, Render ou Chroma Cloud, self-hosted ou gerenciado. Não dá pra eliminar trocando de host.

O que muda com o Chroma Cloud é o que essas 4 requisições encontram do outro lado: hoje, contra uma instância Render Free ainda "acordando", cada perna do handshake mede ~12s; é isso que forçou o timeout de 25s por tentativa e o backoff de até 3 tentativas. Contra infraestrutura de produção sempre ativa do Chroma Cloud, a mesma sequência de 4 requests deve rodar em dezenas de milissegundos, não minutos. Ou seja: o fix não é "menos requisições", é "as mesmas requisições, contra algo que não está hibernando" — isso colapsa o motivo de existir um timeout generoso e retries agressivos, que foi exatamente o que gerou a cascata de 429 documentada no resumo anterior.

O bug do `timeout=None` continua existindo no cliente (é código da lib, não do host), então o workaround de rodar a tentativa numa thread com timeout de parede continua sendo a defesa certa — só que recalibrado para uma latência normal de rede, não para um cold boot de mais de um minuto.

## Sobre OCI (pergunta em aberto, respondida rápido)

Você perguntou se dava pra rodar mais um serviço grátis no OCI. Dá, com ressalva: desde a mudança de junho/2026, o pool Always Free de Ampere A1 caiu de 4 OCPU/24GB para **2 OCPU/12GB total, compartilhado entre todas as instâncias Ampere da conta** — então uma segunda instância só cabe dentro do que sobrar do que a primeira já está usando. Separado disso, a OCI também dá 2 VMs AMD `VM.Standard.E2.1.Micro` sempre grátis, com pool próprio, independente do orçamento Ampere. Como você decidiu ir de Chroma Cloud, isso fica só como informação pra depois, não entra no plano abaixo.

## Escopo da migração

### O que muda
- Host do ChromaDB: serviço `log-triager-chromadb` no Render → Chroma Cloud (gerenciado, fora do Render).
- Cliente Python: `chromadb.HttpClient(host, port, ssl)` → `chromadb.CloudClient(...)`.
- Autenticação: token estático quebrado do Render (bug upstream documentado no README, [chroma-core/chroma#4288](https://github.com/chroma-core/chroma/issues/4288)) → API key nativa do Chroma Cloud, que de fato é validada.
- Variáveis de ambiente: `VECTOR_DB_URL` sai; entram `CHROMA_API_KEY`, `CHROMA_TENANT`, `CHROMA_DATABASE`.
- Constantes de timeout/retry em `vector_db.py`: recalibradas para latência de rede normal, não para cold start.

### O que NÃO muda
- Arquitetura de dois serviços (API + banco vetorial como serviço externo) — intencional, mantém a narrativa de RAG "de verdade" pro portfólio.
- API continua no Render Free (ainda hiberna sozinha — isso é aceitável e coberto pela recomendação C do resumo anterior: liderar a demo com o vídeo).
- `ensure_seeded()` e o fluxo de auto-seed — a coleção `known_errors` continua sendo repovoada automaticamente quando vazia, então não há migração manual de dados.

## Passos técnicos

**1. Conta e credenciais Chroma Cloud**
Criar conta em trychroma.com, criar um tenant e pelo menos um database (ex.: `log-triager-prod`). Considerar um segundo database `log-triager-dev` no mesmo tenant/conta para desenvolvimento local — o free tier cobre até 1M embeddings, então rodar dois databases pros 10 documentos do Manual custa zero. Gerar a API key e guardar fora do repo.

**2. `requirements.txt`**
Conferir que a versão de `chromadb` já instalada (`>=1.0.0,<2.0.0`) expõe `chromadb.CloudClient` — expõe, é API estável na 1.x atual. Não deve ser necessário mudar o pin, mas vale rodar `pip install` e testar o import antes de mexer no resto.

**3. `app/core/config.py`**
Remover `VECTOR_DB_URL`. Adicionar `CHROMA_API_KEY: str`, `CHROMA_TENANT: str`, `CHROMA_DATABASE: str = "log-triager-prod"` (ou o nome escolhido).

**4. `app/services/vector_db.py`**
Substituir `_connect_and_get_collection_once()` inteiro: sai o `urlparse`/`HttpClient(host, port, ssl)`, entra `chromadb.CloudClient(api_key=settings.CHROMA_API_KEY, tenant=settings.CHROMA_TENANT, database=settings.CHROMA_DATABASE)`. O restante do fluxo (`get_or_create_collection`, wrapper de thread+timeout, retry com backoff, filtro de 429) é mantido — mas com as constantes recalibradas:
- `_CONNECT_ATTEMPT_TIMEOUT_SECONDS`: baixar de 25s para algo como 10s (ainda folgado pra uma rede lenta, mas sem estar dimensionado pra cold boot).
- `stop_after_attempt` / `wait_exponential`: manter 3 tentativas, mas encurtar o backoff (ex.: 2–10s em vez de 5–30s) — o cenário que justificava esperar dezenas de segundos entre tentativas (instância "acordando") deixa de existir.
- Manter o `_worth_retrying` que não repete em cima de 429 — Chroma Cloud também tem rate limit por uso, então esse cuidado continua válido.
- Atualizar os comentários/docstrings que hoje explicam os números em função do Render (estão desatualizados assim que o host muda).

**5. `.env.example` e `.env`**
Trocar `VECTOR_DB_URL=http://chromadb:8000` por `CHROMA_API_KEY=`, `CHROMA_TENANT=`, `CHROMA_DATABASE=`.

**6. `docker-compose.yml`**
Recomendo apontar o dev local também pro Chroma Cloud (usando o database separado do passo 1), e remover o serviço `chromadb` do compose junto com o volume `chromadb_data` e `chroma_model_cache` — elimina a necessidade de rodar um container Chroma local pra testar. Se quiser manter a opção de trabalhar 100% offline, dá pra deixar o serviço `chromadb` comentado no compose como fallback, mas não como default.

**7. Render**
Nas env vars do serviço `log-triager-api`: remover `VECTOR_DB_URL`, adicionar `CHROMA_API_KEY` (como secret), `CHROMA_TENANT`, `CHROMA_DATABASE`. Só depois de validar que tudo funciona (passo 9), deletar o serviço `log-triager-chromadb` do Render.

**8. `app/templates/index.html`**
O botão "Wake up ChromaDB" e a lógica de `wakeChromaDB()` partiam do pressuposto de que o ChromaDB também hiberna. Com Chroma Cloud isso deixa de ser verdade — só a API no Render ainda hiberna. Ajustar a copy (ex.: "Wake up API" ou remover o botão e deixar o cold start da API se resolver sozinho no primeiro request, já que sem o ChromaDB hibernando o tempo de wake-up cai bastante). Decisão de UX a confirmar antes de implementar — pode valer manter o botão renomeado como rede de segurança genérica em vez de removê-lo.

**9. `README.md`**
- Seção "Security Note: ChromaDB Authentication": pode ser reescrita como resolvida — Chroma Cloud autentica de verdade via API key, o bug upstream do Render deixa de ser relevante.
- Seção "Resilience Note: ChromaDB Cold Starts": reescrever descrevendo que só a API hiberna agora (não há mais hibernação cruzada de dois serviços), e que o handshake de 4 requests do cliente ainda existe mas roda contra infra sempre ativa.
- Seção "Deployment": atualizar para mencionar Chroma Cloud em vez de "mover pro Starter do Render".
- Tabela de stack: trocar "ChromaDB" por "ChromaDB (Chroma Cloud)" ou similar.
- Versão em português do README precisa do mesmo tratamento (o arquivo tem as duas versões lado a lado).

**10. Testes**
`tests/conftest.py` já mocka o módulo `chromadb` inteiro antes de qualquer import — `CloudClient` sendo só mais um atributo do mock, não deveria quebrar nada. Rodar a suíte depois de cada mudança (`PYTHONPATH=. pytest -v`) pra confirmar. Se `VectorStore.__init__` ou `_connect_and_get_collection_once` passar a validar presença de `CHROMA_API_KEY`/`CHROMA_TENANT`/`CHROMA_DATABASE` nas settings, vale um teste unitário novo cobrindo o caso de configuração ausente.

## Ordem de execução recomendada (pra não gerar downtime perceptível)

1. Criar conta, tenant e database(s) no Chroma Cloud; testar `CloudClient` localmente (fora do Docker, com as env vars novas) antes de tocar em qualquer coisa do Render.
2. Aplicar as mudanças de código (passos 2–6 acima) e rodar a suíte de testes local.
3. Testar localmente end-to-end: subir a API local apontando pro Chroma Cloud, confirmar `/health` e uma triagem real.
4. Configurar as novas env vars no serviço `log-triager-api` do Render e fazer o deploy.
5. Confirmar em produção: `/health` respondendo rápido, uma triagem real completando, e a coleção `known_errors` sendo auto-seedada corretamente.
6. Só depois de confirmado, deletar o serviço `log-triager-chromadb` do Render.
7. Atualizar o README (passo 9) e commitar.

## Riscos a monitorar

O free tier do Chroma Cloud cobre até 1M embeddings e vem com $5 de crédito inicial, com cobrança por uso depois disso — pra 10 documentos estáticos, o volume real é irrisório perto desse limite, então a expectativa é ficar dentro do free tier indefinidamente. Ainda assim, vale configurar um alerta de billing na conta Chroma Cloud como precaução, já que é uma conta nova.

## Não incluído neste plano (deliberadamente)

Embutir a busca vetorial no processo da API (opção A do resumo anterior) — descartado a pedido, porque o objetivo do projeto pra processos seletivos depende de demonstrar RAG com um vetor DB de verdade, não uma implementação simplificada em memória.
