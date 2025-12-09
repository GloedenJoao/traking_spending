# Tracking Spending

Aplicação web em Python/FastAPI para acompanhar gastos do mês e simular saldos diários de contas, vales e cartão de crédito em um tema escuro moderno.

## Tecnologias
- Python 3.10+
- FastAPI + Jinja2
- SQLite com SQLAlchemy
- Uvicorn para servir a aplicação
- Tema escuro com CSS leve

## Como executar
1. Crie e ative um ambiente virtual (opcional, porém recomendado):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Rode o servidor de desenvolvimento:
   ```bash
   uvicorn app.main:app --reload
   ```
4. Acesse em [http://localhost:8000](http://localhost:8000).

## Visão funcional
- **Página 1 (/**): cadastre e edite saldos da conta corrente e caixinhas de CDB, configure o cartão de crédito (nome, vencimento, fatura aberta), defina salário (valor e dia de recebimento) e visualize/ajuste os saldos dos vales refeição e alimentação. Créditos mensais dos vales são aplicados no penúltimo dia útil.
- **Página 2 (/simulate)**: registre transações futuras (conta/carteira, vales ou fatura do cartão), agende transferências entre conta corrente e caixinhas, veja a lista consolidada de eventos futuros (transações, salário ajustado para dia útil anterior, créditos de vales e pagamento da fatura) e acompanhe a tabela diária projetada (por padrão 60 dias, ajustável).

## Lógica de simulação
- Parte dos saldos atuais definidos na Página 1.
- Processa eventos dia a dia: transações cadastradas, transferências permitidas apenas entre conta corrente e caixinhas, crédito de salário (movido para dia útil anterior se cair em final de semana), crédito fixo dos vales no penúltimo dia útil do mês e pagamento da fatura do cartão na data de vencimento (reduzindo a conta corrente e zerando a fatura aberta).
- Valores positivos são destacados em verde e negativos/dívidas em vermelho na tabela.

## Atualizações
Sempre que ajustar regras de negócio ou dependências, atualize este README, o arquivo `AGENTS.MD` com as instruções técnicas e `requirements.txt` com novas bibliotecas. O arquivo SQLite gerado em execução fica ignorado (`.gitignore`) para evitar inclusão de binários no repositório.
