# Instruções para agentes de IA

Atualização: o saldo do cartão de crédito é sempre tratado como dívida (armazenado como valor negativo) para evitar contá-lo como
disponível.

## Escopo
Estas diretrizes cobrem todo o repositório. Mantenha README.md, AGENTS.MD e requirements.txt alinhados ao comportamento atual do aplicativo.

## Arquitetura
- A aplicação FastAPI inicia em `app/main.py` com as rotas das duas páginas (`/` para configuração de saldos e `/simulate` para simulação e eventos futuros).
- Código de infraestrutura e modelos vivem em `app/` (ex.: `db.py`, `models.py`, `simulation.py`, `utils.py`).
- Templates HTML estão em `templates/` e arquivos estáticos em `static/`.

## Modelo de dados (SQLite via SQLAlchemy)
- `accounts(id, name, type[corrente|caixinha], balance)`
- `credit_cards(id, name, due_day, open_amount)`
- `salary(id, amount, payday)`
- `vale_balances(id, vale_type[vale_refeicao|vale_alimentacao], balance)`
- `transactions(id, description, amount, date, target_type[account|credit_card|vale_refeicao|vale_alimentacao], account_id)`
- `transfers(id, description, amount, date, from_account_id, to_account_id)`

## Regras de negócio
- Salário: cai no dia informado ou no dia útil anterior (sábado/domingo volta até sexta).
- Vales: crédito fixo mensal (R$ 1236,40 refeição e R$ 974,16 alimentação) no penúltimo dia útil de cada mês. Saldos são isolados e não podem receber transferências.
- Simulação diária: parte dos saldos atuais, aplica eventos de salário/vales/pagamento da fatura e todas as transações e movimentações por dia.
- Transferências permitidas apenas entre conta corrente e caixinhas de CDB.

## Padrões para manutenção
- Ao adicionar novas colunas/visualizações na simulação, expanda `templates/simulate.html` mantendo as cores verde/vermelho para positivos/negativos e atualize `app/simulation.py` conforme a lógica.
- Sempre que alterar regras financeiras, reflita a mudança no README.md e descreva brevemente no início deste AGENTS.MD.
- Evite blocos try/except envolvendo imports.
- Use comentários pontuais em trechos críticos da lógica de cálculo, quando necessário.
- Mantenha arquivos binários fora do repositório (ex.: banco SQLite gerado em tempo de execução). Use `.gitignore` conforme já definido.
