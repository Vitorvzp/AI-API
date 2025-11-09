# Backend - API Flask

Este é o projeto de backend, implementado com Flask, SQLModel e a API Gemini.

## Estrutura

- `app.py`: Contém a lógica principal da API, incluindo as rotas `/api/chat`, `/dashboard` e `/health`.
- `models.py`: Define os modelos de dados para o banco de dados (User e Conversation).
- `database.db`: Arquivo do banco de dados SQLite.
- `requirements.txt`: Lista de dependências Python.
- `.env`: Arquivo para variáveis de ambiente (TOKEN, DISCORD_WEBHOOK_URL).
- `faq.json`: Arquivo de dados estáticos que pode ser servido pela API.

## Configuração e Execução

1.  **Variáveis de Ambiente**: Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:
    ```env
    TOKEN="SUA_CHAVE_API_GEMINI"
    DISCORD_WEBHOOK_URL="SUA_URL_WEBHOOK_DISCORD" # Opcional
    ```

2.  **Instalação de Dependências**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Execução**:
    ```bash
    python app.py
    ```
    A API estará disponível em `http://0.0.0.0:5000`.

## Rotas da API

- `POST /api/chat`: Envia uma mensagem para a IA e recebe uma resposta.
- `GET /dashboard`: Dashboard HTML simples para visualizar conversas (acesso direto, não é uma API REST).
- `GET /health`: Verifica o status da API.

## Observação sobre o `faq.json`

O arquivo `faq.json` foi movido para o backend. Para que o frontend o acesse, você precisará criar uma nova rota na API (ex: `/api/faq`) para servir este conteúdo.

**Exemplo de Rota para `faq.json` em `app.py`:**

```python
@app.route("/api/faq")
def get_faq():
    try:
        with open("faq.json", "r", encoding="utf-8") as f:
            faq_data = json.load(f)
        return jsonify(faq_data)
    except FileNotFoundError:
        return jsonify({"error": "FAQ not found"}), 404
```

Você deve adicionar esta rota ao `app.py` do backend.
