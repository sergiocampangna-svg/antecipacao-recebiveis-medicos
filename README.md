# Simulador de Antecipação de Recebíveis Médicos

Aplicação em Python com Streamlit, Plotly e Pandas para gerar uma visão executiva da simulação de antecipação de recebíveis médicos.

## O que a aplicação exibe

- Curva do QMM em vermelho.
- Curva de cobrança em laranja, acumulada em degraus.
- Curva do Direito Creditório (DC) em preto.
- Faixas de radar calculadas com 5 dias úteis antes e 5 dias úteis depois da data mensal de pagamento do hospital.
- Parcelas do médico com vencimento sempre no dia mensal de pagamento do hospital.
- Quadro de Premissas.
- Quadro de Parâmetros / Fórmulas.
- Comentários e marcos de datas abaixo do gráfico.
- Parametrização alternativa da operação: por quantidade de parcelas ou por prazo total.
- Tabela de liquidação por parcela, com status pago integralmente, pago parcialmente ou não pago.
- Recalculo automático de cobrança realizada, atraso, mora, saldo exigível e QMM ajustado opcional.

## Como rodar localmente

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Cenário inicial configurado

A tela abre com o cenário de teste solicitado:

- Data da antecipação: 18/04/2026
- Pagamento hospital: dia 20
- Taxa: 2,5% ao mês
- Prazo total: 90 dias
- Carência: 30 dias
- DC: R$ 100.000,00
- 2 parcelas de R$ 50.000,00
- Vencimentos das parcelas no cenário inicial: 20/06/2026 e 20/07/2026

## Regras implementadas

### Modo de definição da operação

A operação pode ser definida de duas formas:

- **Por parcelas:** o usuário informa a quantidade de parcelas e o sistema calcula os vencimentos nos próximos ciclos mensais do hospital. O prazo total real é calculado automaticamente pela diferença entre a última parcela e a data da antecipação.
- **Por prazo total:** o usuário informa o prazo em dias corridos e o sistema calcula quantas parcelas cabem nos ciclos mensais do hospital até a data limite.

Os dois campos não são usados como entradas livres ao mesmo tempo. O calendário mensal do hospital é sempre a referência operacional para reconciliar parcelas e prazo.

Exemplo com antecipação em 18/04/2026 e pagamento hospitalar no dia 20:

- Por 3 parcelas: 20/05/2026, 20/06/2026 e 20/07/2026, com prazo real de 93 dias.
- Por prazo total de 93 dias: 3 parcelas nas mesmas datas.

Se o prazo informado não comportar nenhum ciclo mensal, a aplicação mostra uma mensagem de erro amigável com o primeiro vencimento possível.

### Atraso, mora e pagamento parcial

Cada parcela mantém seu vencimento contratual original. Na tabela de liquidação, o usuário informa o status, a data de pagamento efetivo e o valor pago.

A cobrança esperada segue o cronograma contratual. A cobrança realizada considera apenas pagamentos efetivos. O gap de cobrança é:

```text
Gap = cobrança esperada - cobrança realizada
```

Quando há pagamento parcial ou não pagamento, o saldo remanescente vira atraso. A mora é calculada sobre o saldo vencido ou sobre a parcela em atraso, conforme parâmetro escolhido, respeitando os dias de tolerância. A baixa de pagamentos segue a ordem:

```text
juros/mora -> atraso acumulado -> parcela corrente -> excedente
```

O QMM ajustado pode ser ativado para aplicar haircut sobre atraso e/ou gap de cobrança.

O valor presente é calculado pela fórmula:

```text
VP = soma(Parcela_i / (1 + i)^(t_i / 30))
```

Onde `i` é a taxa mensal e `t_i` é o prazo em dias corridos entre a data da antecipação e o vencimento da parcela.

As parcelas sempre vencem no dia de pagamento mensal do hospital. A primeira parcela vence no primeiro pagamento hospitalar após o fim da carência; as demais seguem mensalmente no mesmo dia de pagamento. Isso permite que o fundo retenha o valor da parcela no fluxo recebido e repasse o excedente ao médico.

A curva do QMM inicia no valor presente creditado ao médico, permanece flat durante a carência, cresce linearmente entre marcos e assume, no primeiro dia de cada radar, o valor futuro projetado até o fim da janela. Durante o radar, o QMM permanece flat e limitado ao valor do DC.

O gráfico estende o eixo de datas até o fim da última janela de radar, mesmo quando essa janela ultrapassa o vencimento final da operação. Assim, a regra de radar ligado de 5 dias úteis antes até 5 dias úteis depois do pagamento mensal fica visível por completo.
