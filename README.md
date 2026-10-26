# AI-API

> **Escopo deste rascunho:** este PR inclui somente código, documentação e testes. As remoções de arquivos privados do índice foram preparadas apenas no commit local e não estão incluídas aqui, para evitar sua exposição no diff. Os arquivos legados continuam rastreados nesta branch remota e no histórico até uma etapa específica.

Backend Flask para o chat do portfólio, com geração de respostas via Gemini,
histórico em SQLite e um painel administrativo de conversas.

```text
AI-API / Flask · SQLModel · Gemini
```

## Desenvolvimento local

Crie um ambiente virtual e instale as dependências:

```bash
python -m venv .venv
# Ative o ambiente virtual conforme seu sistema operacional.
python -m pip install -r requirements.txt
python app.py
```

O servidor local escuta a porta `5000` por padrão; `PORT` pode substituí-la.
O processo cria `database.db` no diretório de execução quando necessário.

Configure variáveis no ambiente ou em um `.env` local ignorado pelo Git:

| Variável | Uso |
| --- | --- |
| `TOKEN` | Chave da API Gemini. Sem cliente disponível, `/api/chat` retorna `503`. |
| `FRONTEND_URL` | Origem do frontend aceita pelo CORS; revise a política antes de produção. |
| `DISCORD_WEBHOOK_URL` | Opcional. Quando configurada, o chat encaminha mensagens, respostas e IP ao webhook. |
| `PING_URL` | Destino do self-ping a cada cinco minutos; padrão `http://localhost:5000/ping`. |
| `DASHBOARD_TOKEN` | Segredo administrativo independente. Ausente, vazio ou composto só por espaços mantém `/dashboard` desativado (`404`). |

Não adicione `.env`, bancos, conversas ou tokens ao controle de versão.
A remoção desses arquivos da versão atual não apaga versões anteriores do
histórico; avaliação de exposição e eventual rotação são etapas separadas.

## Rotas

| Método e rota | Comportamento |
| --- | --- |
| `POST /api/chat` | Recebe JSON com `message` e devolve `reply`; persiste mensagem, resposta e usuário associado ao IP. |
| `GET /api/faq` | Serve o `faq.json` local; retorna `404` se o arquivo estiver ausente. |
| `GET /health` | Informa status e horário do processo. |
| `GET /ping` | Retorna `pong`. |
| `GET /dashboard` | Painel administrativo protegido; aceita filtro opcional `ip`. |

## Acesso ao dashboard

Quando houver `DASHBOARD_TOKEN` configurado, cada requisição deve enviar:

```http
Authorization: Bearer <segredo-administrativo>
```

Cabeçalho ausente ou inválido retorna `401`, antes de consultar conversas ou
IPs. O token é comparado com `hmac.compare_digest`. Parâmetros de URL e cookies
não autenticam o painel; mantenha o segredo fora de URLs, código do frontend e
logs. Use HTTPS fora do ambiente local.

Use um cliente que envie o cabeçalho em todas as requisições, inclusive ao
aplicar `?ip=...`. Uma navegação comum do navegador ou o envio do formulário
sem o cabeçalho retorna `401`; este projeto não implementa sessão de login.

Mensagens, respostas e IPs são renderizados por um template HTML com escape
automático. As respostas do painel usam `Cache-Control: no-store` e uma política
de conteúdo que impede scripts e incorporação em frames.

## Testes isolados

```bash
python -m unittest discover -s tests -v
```

Os testes usam registros sintéticos e SQLite em memória. A importação da
aplicação nos testes substitui o carregamento de `.env`, a criação do cliente
Gemini e o início da thread de self-ping. Nenhum serviço externo ou banco
existente é necessário.

## Estrutura

- `app.py`: rotas, integração Gemini e self-ping.
- `models.py`: modelos `User` e `Conversation`.
- `templates/dashboard.html`: painel com escape automático de conteúdo.
- `tests/test_dashboard.py`: regressões de autorização e HTML.
- `faq.json`: conteúdo estático da FAQ.
- `requirements.txt`: dependências Python.

## Limites de implantação

O `render.yaml` versionado referencia `requirements_clean_v2.txt` e uma pasta
`src`, ausentes neste checkout, e declara `GEMINI_API_KEY`, enquanto `app.py`
consulta `TOKEN`. Esse arquivo precisa de revisão antes de ser usado como
instrução de implantação. Esta correção não altera configuração de produção,
credenciais ou permissões. O painel desativado por padrão só terá efeito após
revisão e implantação do código.
