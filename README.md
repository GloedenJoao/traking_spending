# Simulador de gastos mensais

Aplicação web em FastAPI para acompanhar saldos atuais e simular dia a dia o comportamento de contas e fatura do cartão considerando transações futuras, transferências, salário e vencimento da fatura.

## Tecnologias utilizadas
- Python
- FastAPI
- SQLite via SQLAlchemy
- Templates Jinja2 e CSS estático

## Como instalar e executar
1. Crie e ative um ambiente virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Rode o servidor FastAPI com Uvicorn:
   ```bash
   uvicorn app.main:app --reload
   ```
4. Acesse no navegador: `http://127.0.0.1:8000/`

## Visão funcional
- **Página 1 – Saldos atuais (`/`)**
  - Informe o saldo da conta corrente.
  - Cadastre e edite caixinhas de CDB com seus saldos.
  - Defina dados do cartão (nome, vencimento, valor atual da fatura).
  - Cadastre o salário e o dia do crédito (antecipado para o último dia útil se cair no fim de semana). O salário é creditado na conta corrente.
- **Página 2 – Simulação (`/simulation`)**
  - Cadastre transações futuras em contas ou no cartão.
  - Registre transferências entre contas em datas específicas.
  - Ajuste o horizonte em dias para a tabela (padrão 60 dias a partir de hoje).
  - Veja a tabela diária com saldos projetados por conta e valor da fatura. Valores positivos ficam em verde e negativos em vermelho.
  - Consulte a lista de eventos futuros considerados (salário, vencimento de fatura, transações e transferências cadastradas).

## Lógica de simulação (resumo)
- Parte dos saldos atuais cadastrados.
- Para cada dia no período, aplica em ordem: crédito de salário (com ajuste de dia útil), transações futuras, transferências entre contas e pagamento da fatura na data de vencimento.
- Transações no cartão aumentam o valor da fatura; no vencimento a fatura é debitada da conta corrente e zerada.

## Atualizações
Sempre que alterar comportamento, rotas ou modelos de dados, atualize este README.md e o arquivo AGENTS.MD para refletir as mudanças.
