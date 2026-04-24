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

O valor presente é calculado pela fórmula:

```text
VP = soma(Parcela_i / (1 + i)^(t_i / 30))
```

Onde `i` é a taxa mensal e `t_i` é o prazo em dias corridos entre a data da antecipação e o vencimento da parcela.

As parcelas sempre vencem no dia de pagamento mensal do hospital. A última parcela é alinhada ao primeiro pagamento hospitalar em ou após a data de referência do prazo total; as parcelas anteriores retornam mês a mês no mesmo dia de pagamento. Isso permite que o fundo retenha o valor da parcela no fluxo recebido e repasse o excedente ao médico.

A curva do QMM inicia no valor presente creditado ao médico, permanece flat durante a carência, cresce linearmente entre marcos e assume, no primeiro dia de cada radar, o valor futuro projetado até o fim da janela. Durante o radar, o QMM permanece flat e limitado ao valor do DC.

O gráfico estende o eixo de datas até o fim da última janela de radar, mesmo quando essa janela ultrapassa o vencimento final da operação. Assim, a regra de radar ligado de 5 dias úteis antes até 5 dias úteis depois do pagamento mensal fica visível por completo.
