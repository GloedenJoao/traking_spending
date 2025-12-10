# Tracking Spending

Aplicação web em Python/FastAPI para acompanhar gastos do mês e simular saldos diários de contas, vales e cartão de crédito. O tema escuro facilita a leitura de valores positivos (verde) e negativos/dívidas (vermelho) na projeção diária.

## Stack e organização
- **Backend**: FastAPI com templates Jinja2 (`app/main.py`), regras financeiras em `app/simulation.py` e utilidades em `app/utils.py`.
- **Persistência**: SQLite (`app/db.py`) via SQLAlchemy; o arquivo `data.db` é criado automaticamente na raiz.
- **Front-end**: HTML em `templates/` e estilos/JS em `static/`.
- **Ambiente**: Python 3.10+ com Uvicorn para desenvolvimento.

## Como executar
1. (Opcional) Crie e ative um ambiente virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
3. Inicialize o servidor (recarrega em mudanças de código):
   ```bash
   uvicorn app.main:app --reload
   ```
4. Acesse [http://localhost:8000](http://localhost:8000). O banco SQLite é criado automaticamente na primeira execução com valores iniciais.

## Fluxo funcional
- **Página inicial (/**):
  - Configure saldo da conta corrente e crie/edite caixinhas de CDB.
  - Ajuste o cartão de crédito (nome, dia de vencimento e fatura aberta). A fatura é sempre armazenada como valor negativo para representar dívida.
  - Defina salário mensal (valor e dia). O depósito é adiantado para o dia útil anterior se cair em fim de semana.
  - Consulte e ajuste saldos dos vales refeição e alimentação. Créditos mensais são aplicados no penúltimo dia útil.

- **Página de simulação (/simulate)**:
  - Cadastre transações futuras em datas únicas ou intervalos (contas, vales ou fatura do cartão).
  - Programe transferências entre conta corrente e caixinhas usando o mesmo esquema de datas.
  - Visualize a lista consolidada de eventos gerados (salário ajustado, créditos de vales, pagamento da fatura e itens cadastrados).
  - Veja a projeção diária (60 dias por padrão, ajustável via formulário) com saldos de contas, vales e fatura.

## Regras principais da simulação
- A simulação parte dos saldos atuais gravados na Página inicial.
- A cada dia aplica eventos mensais gerados automaticamente:
  - Salário creditado na conta corrente, movido para o dia útil anterior em caso de fim de semana.
  - Créditos fixos dos vales refeição (R$ 1236,40) e alimentação (R$ 974,16) no penúltimo dia útil do mês.
  - Pagamento da fatura do cartão na data de vencimento configurada, debitando a conta corrente pelo valor absoluto da dívida e zerando a fatura.
- Transações e transferências cadastradas são aplicadas nas datas informadas; transferências são permitidas apenas entre conta corrente e caixinhas.
- O saldo do cartão é sempre mantido como negativo para impedir que apareça como recurso disponível.

## Manutenção
- Regras financeiras alteradas devem ser refletidas nesta documentação e em `AGENTS.MD`.
- Novas dependências devem ser adicionadas em `requirements.txt`.
- O arquivo SQLite (`data.db`) é artefato de execução e já está listado no `.gitignore`.
