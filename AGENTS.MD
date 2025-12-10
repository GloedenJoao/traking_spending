# Instruções para agentes de IA

Atualização: o saldo do cartão de crédito é sempre tratado como dívida (armazenado como valor negativo) para evitar contá-lo com o disponível.

## Escopo
Estas diretrizes cobrem todo o repositório. Mantenha README.md, AGENTS.MD e requirements.txt alinhados ao comportamento atual do aplicativo e às regras financeiras.

## Arquitetura de referência
- A aplicação FastAPI inicia em `app/main.py` com as rotas das duas páginas (`/` para configuração de saldos e `/simulate` para simulação e eventos futuros).
- Código de infraestrutura e modelos vive em `app/` (ex.: `db.py`, `models.py`, `simulation.py`, `utils.py`).
- Templates HTML estão em `templates/` e arquivos estáticos em `static/`.
- O SQLite `data.db` é criado automaticamente; mantenha-o fora do controle de versão (já ignorado pelo `.gitignore`).

## Modelo de dados (SQLite via SQLAlchemy)
- `accounts(id, name, type[corrente|caixinha], balance)`
- `credit_cards(id, name, due_day, open_amount)`
- `salary(id, amount, payday)`
- `vale_balances(id, vale_type[vale_refeicao|vale_alimentacao], balance)`
- `transactions(id, description, amount, date, target_type[account|credit_card|vale_refeicao|vale_alimentacao], account_id)`
- `transfers(id, description, amount, date, from_account_id, to_account_id)`
- `future_events(id, date, description, amount, target, source)`

## Regras de negócio resumidas
- Salário cai no dia informado ou no dia útil anterior (sábado/domingo antecipam para a sexta-feira anterior).
- Vales: crédito fixo mensal (R$ 1236,40 refeição e R$ 974,16 alimentação) no penúltimo dia útil de cada mês; saldos de vales são isolados e não recebem transferências.
- Fatura do cartão: sempre negativa; pagamento ocorre no vencimento configurado debitando a conta corrente pelo valor absoluto da dívida e zerando a fatura.
- Simulação diária parte dos saldos atuais e aplica eventos de salário, vales, pagamento da fatura, transações e movimentações por dia.
- Transferências são permitidas apenas entre conta corrente e caixinhas de CDB.

## Padrões para manutenção
- Ao adicionar novas colunas/visualizações na simulação, expanda `templates/simulate.html` mantendo cores verde/vermelho para positivos/negativos e ajuste `app/simulation.py` conforme a lógica.
- Regras financeiras alteradas devem ser refletidas neste arquivo e no README.md.
- Atualize `requirements.txt` apenas quando introduzir dependências novas; não use blocos `try/except` envolvendo imports.
- Use comentários pontuais em trechos críticos da lógica de cálculo, quando necessário.
- Evite adicionar binários ao repositório (ex.: banco SQLite gerado em tempo de execução).
