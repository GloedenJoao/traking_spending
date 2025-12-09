# Instruções para agentes de IA

## Visão geral
- O projeto é um webapp FastAPI para simular saldos diários de contas e cartão de crédito.
- Estrutura principal:
  - `app/main.py`: ponto de entrada da aplicação e registro de rotas.
  - `app/database.py`: configuração do banco SQLite e sessão do SQLAlchemy.
  - `app/models.py`: modelos ORM para contas, cartão, salário, transações e transferências.
  - `app/services.py`: regras de negócio e lógica de simulação diária.
  - `app/templates/`: templates Jinja2 para as páginas HTML.
  - `app/static/`: arquivos CSS/JS.
- Rotas principais: `/` (Página 1 – cadastro de valores) e `/simulation` (Página 2 – simulação).

## Modelo de dados
- Tabelas principais (campos relevantes):
  - `accounts`: `id` (PK), `name` (str), `type` (str: `checking` ou `cdb`), `balance` (float).
  - `cards`: `id` (PK), `name` (str), `due_day` (int), `current_invoice` (float).
  - `salaries`: `id` (PK), `amount` (float), `pay_day` (int).
  - `transactions`: `id` (PK), `description` (str), `amount` (float), `date` (date), `target_type` (str: `account` ou `card`), `account_id` (FK), `card_id` (FK).
  - `transfers`: `id` (PK), `description` (str), `amount` (float), `date` (date), `source_account_id` (FK), `target_account_id` (FK).

## Regras de negócio
- Salário: é creditado na conta corrente no dia configurado; se cair em fim de semana, antecipa para o dia útil anterior.
- Simulação diária: inicia com os saldos atuais, percorre dia a dia aplicando, em ordem, salário, transações, transferências e pagamento da fatura.
- Cartão: transações com `target_type=card` somam ao `current_invoice`; no dia de vencimento, o valor da fatura é debitado da conta corrente e a fatura é zerada.

## Manutenção
- Ao alterar modelos ou regras de cálculo, atualize README.md e este AGENTS.MD.
- Preferir comentários breves em pontos de lógica crítica (ex.: cálculo de dias úteis, processamento de eventos da simulação).
- Para novas colunas ou tipos de contas, expanda `models.py` e ajuste `services.py` para refletir na simulação e nas tabelas renderizadas.
- Novas páginas ou gráficos devem seguir a organização atual de templates e rotas.
