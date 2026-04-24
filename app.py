from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


BRL_PREFIX = "R$ "
QMM_COLOR = "#c1121f"
COBRANCA_COLOR = "#f28c28"
DC_COLOR = "#111111"
RADAR_COLOR = "rgba(33, 94, 150, 0.13)"
GRID_COLOR = "#e8edf3"


@dataclass(frozen=True)
class Installment:
    number: int
    due_date: date
    amount: float
    days_from_advance: int
    present_value: float


@dataclass(frozen=True)
class RadarWindow:
    month_label: str
    payment_date: date
    start_date: date
    end_date: date
    qmm_value: float


def format_brl(value: float) -> str:
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{BRL_PREFIX}{formatted}"


def format_pct(value: float) -> str:
    return f"{value:.2f}%".replace(".", ",")


def format_date_pt(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def month_payment_date(reference: date, hospital_payment_day: int) -> date:
    max_day = monthrange(reference.year, reference.month)[1]
    return date(reference.year, reference.month, min(hospital_payment_day, max_day))


def next_hospital_payment_date(reference: date, hospital_payment_day: int) -> date:
    candidate = month_payment_date(reference, hospital_payment_day)
    if candidate <= reference:
        candidate = month_payment_date(add_months(reference, 1), hospital_payment_day)
    return candidate


def first_installment_cycle_date(
    advance_date: date,
    hospital_payment_day: int,
    grace_days: int,
) -> date:
    grace_end = advance_date + timedelta(days=grace_days)
    candidate = month_payment_date(grace_end, hospital_payment_day)
    if candidate < grace_end:
        candidate = month_payment_date(add_months(grace_end, 1), hospital_payment_day)
    return candidate


def generate_hospital_cycles(
    advance_date: date,
    hospital_payment_day: int,
    grace_days: int,
    limit_date: date | None = None,
    count: int | None = None,
) -> list[date]:
    cycles: list[date] = []
    current = first_installment_cycle_date(advance_date, hospital_payment_day, grace_days)

    while True:
        if count is not None and len(cycles) >= count:
            break
        if limit_date is not None and current > limit_date:
            break

        cycles.append(current)
        current = month_payment_date(add_months(current, 1), hospital_payment_day)

    return cycles


def calculate_installment_dates_by_count(
    advance_date: date,
    hospital_payment_day: int,
    grace_days: int,
    installment_count: int,
) -> list[date]:
    if installment_count < 1:
        raise ValueError("Informe pelo menos 1 parcela.")

    # As parcelas coincidem com os ciclos de pagamento do hospital, pois o fundo
    # liquida a antecipação ao reter a parcela no fluxo recebido.
    return generate_hospital_cycles(
        advance_date=advance_date,
        hospital_payment_day=hospital_payment_day,
        grace_days=grace_days,
        count=installment_count,
    )


def calculate_installment_dates_by_term(
    advance_date: date,
    hospital_payment_day: int,
    grace_days: int,
    total_term_days: int,
) -> list[date]:
    if total_term_days < 1:
        raise ValueError("Informe um prazo total maior que zero.")

    limit_date = advance_date + timedelta(days=total_term_days)
    installment_dates = generate_hospital_cycles(
        advance_date=advance_date,
        hospital_payment_day=hospital_payment_day,
        grace_days=grace_days,
        limit_date=limit_date,
    )
    if not installment_dates:
        first_due_date = first_installment_cycle_date(advance_date, hospital_payment_day, grace_days)
        first_due_term = (first_due_date - advance_date).days
        raise ValueError(
            "O prazo informado não comporta nenhuma parcela. "
            f"O primeiro vencimento possível é {format_date_pt(first_due_date)} "
            f"({first_due_term} dias corridos após a antecipação)."
        )

    return installment_dates


def calculate_real_total_term(advance_date: date, installment_dates: list[date]) -> int:
    return (max(installment_dates) - advance_date).days


def add_business_days(value: date, business_days: int) -> date:
    step = 1 if business_days >= 0 else -1
    remaining = abs(business_days)
    current = value
    while remaining:
        current += timedelta(days=step)
        if current.weekday() < 5:
            remaining -= 1
    return current


def calculate_payment_dates(
    reference_date: date,
    final_date: date,
    hospital_payment_day: int,
) -> list[date]:
    first_payment = month_payment_date(reference_date, hospital_payment_day)
    if first_payment < reference_date:
        first_payment = month_payment_date(add_months(reference_date, 1), hospital_payment_day)
    payments: list[date] = []
    current = first_payment
    while add_business_days(current, -5) <= final_date:
        payments.append(current)
        current = month_payment_date(add_months(current, 1), hospital_payment_day)
    return payments


def calculate_present_value(
    advance_date: date,
    installment_dates: list[date],
    installment_amount: float,
    monthly_rate: float,
) -> tuple[float, list[Installment]]:
    installments: list[Installment] = []
    for index, due_date in enumerate(installment_dates, start=1):
        days_from_advance = max((due_date - advance_date).days, 0)
        present_value = installment_amount / ((1 + monthly_rate) ** (days_from_advance / 30))
        installments.append(
            Installment(
                number=index,
                due_date=due_date,
                amount=installment_amount,
                days_from_advance=days_from_advance,
                present_value=present_value,
            )
        )
    return sum(item.present_value for item in installments), installments


def projected_qmm_value(
    target_date: date,
    advance_date: date,
    final_date: date,
    present_value: float,
    dc_value: float,
    grace_days: int,
) -> float:
    grace_end = advance_date + timedelta(days=grace_days)
    if target_date <= grace_end:
        return min(present_value, dc_value)

    growth_days = max((final_date - grace_end).days, 1)
    elapsed_days = max((target_date - grace_end).days, 0)
    linear_value = present_value + (dc_value - present_value) * min(elapsed_days / growth_days, 1)
    return min(max(linear_value, present_value), dc_value)


def calculate_radar_windows(
    payment_dates: list[date],
    advance_date: date,
    final_date: date,
    present_value: float,
    dc_value: float,
    grace_days: int,
) -> list[RadarWindow]:
    radars: list[RadarWindow] = []
    for payment_date in payment_dates:
        start_date = add_business_days(payment_date, -5)
        end_date = add_business_days(payment_date, 5)
        if end_date < advance_date or start_date > final_date:
            continue

        qmm_value = projected_qmm_value(
            end_date,
            advance_date,
            final_date,
            present_value,
            dc_value,
            grace_days,
        )
        radars.append(
            RadarWindow(
                month_label=payment_date.strftime("%m/%Y"),
                payment_date=payment_date,
                start_date=start_date,
                end_date=end_date,
                qmm_value=min(qmm_value, dc_value),
            )
        )
    return radars


def build_collection_curve(
    dates: pd.DatetimeIndex,
    installments: list[Installment],
) -> pd.DataFrame:
    rows = []
    for current in dates.date:
        accumulated = sum(item.amount for item in installments if current >= item.due_date)
        rows.append({"date": current, "cobranca": accumulated})
    return pd.DataFrame(rows)


def active_radar(current: date, radars: list[RadarWindow]) -> RadarWindow | None:
    for radar in radars:
        if radar.start_date <= current <= radar.end_date:
            return radar
    return None


def next_radar_after(current: date, radars: list[RadarWindow]) -> RadarWindow | None:
    future_radars = [radar for radar in radars if radar.start_date > current]
    return min(future_radars, key=lambda radar: radar.start_date, default=None)


def build_qmm_curve(
    dates: pd.DatetimeIndex,
    advance_date: date,
    final_date: date,
    present_value: float,
    dc_value: float,
    grace_days: int,
    radars: list[RadarWindow],
) -> pd.DataFrame:
    rows = []
    grace_end = advance_date + timedelta(days=grace_days)

    for current in dates.date:
        radar = active_radar(current, radars)
        if radar:
            qmm = radar.qmm_value
        elif current <= grace_end:
            qmm = present_value
        else:
            upcoming_radar = next_radar_after(current, radars)
            segment_start = grace_end
            segment_start_value = present_value

            previous_radars = [item for item in radars if item.end_date < current]
            if previous_radars:
                last_radar = max(previous_radars, key=lambda item: item.end_date)
                segment_start = last_radar.end_date
                segment_start_value = last_radar.qmm_value

            if upcoming_radar:
                segment_end = upcoming_radar.start_date
                segment_end_value = upcoming_radar.qmm_value
            else:
                segment_end = final_date
                segment_end_value = dc_value

            segment_days = max((segment_end - segment_start).days, 1)
            elapsed_days = max((current - segment_start).days, 0)
            qmm = segment_start_value + (segment_end_value - segment_start_value) * min(
                elapsed_days / segment_days,
                1,
            )

        rows.append({"date": current, "qmm": min(qmm, dc_value)})

    return pd.DataFrame(rows)


def build_projection(
    advance_date: date,
    hospital_payment_day: int,
    operation_mode: str,
    monthly_rate_pct: float,
    grace_days: int,
    dc_value: float,
    total_term_days: int | None = None,
    installment_count: int | None = None,
    installment_amount: float | None = None,
    split_automatically: bool = True,
) -> dict[str, object]:
    monthly_rate = monthly_rate_pct / 100

    if operation_mode == "Por parcelas":
        if installment_count is None:
            raise ValueError("Informe a quantidade de parcelas.")
        installment_dates = calculate_installment_dates_by_count(
            advance_date=advance_date,
            hospital_payment_day=hospital_payment_day,
            grace_days=grace_days,
            installment_count=installment_count,
        )
        real_total_term_days = calculate_real_total_term(advance_date, installment_dates)
        input_total_term_days = None
        calculated_installment_count = len(installment_dates)
        contractual_final_date = max(installment_dates)
    elif operation_mode == "Por prazo total":
        if total_term_days is None:
            raise ValueError("Informe o prazo total da operação.")
        installment_dates = calculate_installment_dates_by_term(
            advance_date=advance_date,
            hospital_payment_day=hospital_payment_day,
            grace_days=grace_days,
            total_term_days=total_term_days,
        )
        real_total_term_days = calculate_real_total_term(advance_date, installment_dates)
        input_total_term_days = total_term_days
        calculated_installment_count = len(installment_dates)
        contractual_final_date = advance_date + timedelta(days=total_term_days)
    else:
        raise ValueError("Selecione um modo de definição da operação.")

    if split_automatically:
        installment_amount = dc_value / calculated_installment_count
    elif installment_amount is None or installment_amount <= 0:
        raise ValueError("Informe um valor de parcela maior que zero.")

    final_date = max(installment_dates)
    present_value, installments = calculate_present_value(
        advance_date,
        installment_dates,
        installment_amount,
        monthly_rate,
    )
    payment_dates = calculate_payment_dates(min(installment_dates), final_date, hospital_payment_day)
    radars = calculate_radar_windows(
        payment_dates,
        advance_date,
        final_date,
        present_value,
        dc_value,
        grace_days,
    )
    chart_end_date = max([final_date, *[radar.end_date for radar in radars]])
    dates = pd.date_range(advance_date, chart_end_date, freq="D")
    qmm_curve = build_qmm_curve(
        dates,
        advance_date,
        final_date,
        present_value,
        dc_value,
        grace_days,
        radars,
    )
    collection_curve = build_collection_curve(dates, installments)
    df = qmm_curve.merge(collection_curve, on="date")
    df["dc"] = dc_value
    return {
        "df": df,
        "present_value": present_value,
        "installments": installments,
        "payment_dates": payment_dates,
        "radars": radars,
        "final_date": final_date,
        "contractual_final_date": contractual_final_date,
        "input_total_term_days": input_total_term_days,
        "real_total_term_days": real_total_term_days,
        "operation_mode": operation_mode,
        "calculated_installment_count": calculated_installment_count,
        "installment_amount": installment_amount,
        "split_automatically": split_automatically,
        "chart_end_date": chart_end_date,
        "grace_end": advance_date + timedelta(days=grace_days),
        "monthly_rate": monthly_rate,
    }


def money_hover(values: pd.Series) -> list[str]:
    return [format_brl(float(value)) for value in values]


def add_reference_line(fig: go.Figure, value: date, color: str = "#65758b") -> None:
    x_value = value.isoformat()
    fig.add_shape(
        type="line",
        x0=x_value,
        x1=x_value,
        y0=0,
        y1=1,
        xref="x",
        yref="paper",
        line=dict(color=color, width=1, dash="dot"),
        layer="above",
    )


def build_chart(
    projection: dict[str, object],
    advance_date: date,
    dc_value: float,
) -> go.Figure:
    df = projection["df"]
    installments = projection["installments"]
    radars = projection["radars"]
    grace_end = projection["grace_end"]
    present_value = projection["present_value"]
    final_date = projection["final_date"]
    chart_end_date = projection["chart_end_date"]

    fig = go.Figure()

    for radar in radars:
        fig.add_shape(
            type="rect",
            x0=radar.start_date.isoformat(),
            x1=radar.end_date.isoformat(),
            y0=0,
            y1=1,
            xref="x",
            yref="paper",
            fillcolor=RADAR_COLOR,
            line=dict(width=0),
            layer="below",
        )
        fig.add_annotation(
            x=radar.start_date.isoformat(),
            y=1.01,
            xref="x",
            yref="paper",
            text=f"Radar {radar.month_label}",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            font=dict(size=9, color="#215e96"),
        )

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["qmm"],
            mode="lines",
            name="Curva QMM",
            line=dict(color=QMM_COLOR, width=4),
            customdata=money_hover(df["qmm"]),
            hovertemplate="%{x|%d/%m/%Y}<br>QMM: %{customdata}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["cobranca"],
            mode="lines",
            name="Curva Cobrança",
            line=dict(color=COBRANCA_COLOR, width=3, shape="hv"),
            customdata=money_hover(df["cobranca"]),
            hovertemplate="%{x|%d/%m/%Y}<br>Cobrança: %{customdata}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["dc"],
            mode="lines",
            name="Direito Creditório (DC)",
            line=dict(color=DC_COLOR, width=3),
            customdata=money_hover(df["dc"]),
            hovertemplate="%{x|%d/%m/%Y}<br>DC: %{customdata}<extra></extra>",
        )
    )

    add_reference_line(fig, advance_date)
    add_reference_line(fig, grace_end)
    for item in installments:
        add_reference_line(fig, item.due_date, COBRANCA_COLOR)
    add_reference_line(fig, final_date, DC_COLOR)

    label_points = [
        (advance_date, present_value, f"VP {format_brl(present_value)}", QMM_COLOR, 52),
        (final_date, dc_value, f"DC {format_brl(dc_value)}", DC_COLOR, -52),
    ]

    for x_value, y_value, text, color, ay in label_points:
        fig.add_annotation(
            x=x_value.isoformat(),
            y=y_value,
            text=text,
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=1,
            arrowcolor=color,
            ax=0,
            ay=ay,
            font=dict(size=11, color=color),
            bgcolor="rgba(255,255,255,0.88)",
            bordercolor=color,
            borderwidth=1,
        )

    y_max = max(dc_value, float(df[["qmm", "cobranca", "dc"]].max().max())) * 1.12
    fig.update_layout(
        height=620,
        template="plotly_white",
        margin=dict(l=24, r=24, t=80, b=46),
        title=dict(
            text="Simulação Executiva de Antecipação de Recebíveis Médicos",
            font=dict(size=22, color="#1f2937"),
            x=0.01,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=12),
        ),
        hovermode="x unified",
        plot_bgcolor="#ffffff",
        paper_bgcolor="#ffffff",
        font=dict(family="Arial, sans-serif", color="#243447"),
        xaxis=dict(
            title="Datas da operação",
            showgrid=True,
            gridcolor=GRID_COLOR,
            tickformat="%d/%m/%Y",
            range=[advance_date.isoformat(), chart_end_date.isoformat()],
            rangeslider=dict(visible=False),
        ),
        yaxis=dict(
            title="Valor acumulado / projetado",
            showgrid=True,
            gridcolor=GRID_COLOR,
            range=[0, y_max],
            tickprefix=BRL_PREFIX,
            separatethousands=True,
        ),
    )
    return fig


def render_metric_card(label: str, value: str, helper: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <span>{label}</span>
            <strong>{value}</strong>
            <small>{helper}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_assumptions(
    advance_date: date,
    hospital_payment_day: int,
    dc_value: float,
    grace_days: int,
    monthly_rate_pct: float,
    present_value: float,
    projection: dict[str, object],
) -> None:
    operation_mode = str(projection["operation_mode"])
    installment_count = int(projection["calculated_installment_count"])
    installment_amount = float(projection["installment_amount"])
    real_total_term_days = int(projection["real_total_term_days"])
    input_total_term_days = projection["input_total_term_days"]
    contractual_final_date = projection["contractual_final_date"]
    final_date = projection["final_date"]

    st.subheader("Premissas")
    rows = [
        ("Data da antecipação", format_date_pt(advance_date)),
        ("Modo de definição", operation_mode),
        ("Dia de pagamento do hospital", f"Dia {hospital_payment_day}"),
        ("Direito Creditório (DC)", format_brl(dc_value)),
        ("Parcelas do médico", f"{installment_count} x {format_brl(installment_amount)}"),
        ("Liquidação final", format_date_pt(final_date)),
        ("Carência", f"{grace_days} dias corridos"),
        ("Taxa de custo", f"{format_pct(monthly_rate_pct)} ao mês"),
        ("VP creditado ao médico", format_brl(present_value)),
    ]
    if operation_mode == "Por parcelas":
        rows.insert(5, ("Prazo total calculado", f"{real_total_term_days} dias corridos"))
    else:
        rows.insert(5, ("Prazo total informado", f"{int(input_total_term_days)} dias corridos"))
        rows.insert(6, ("Parcelas calculadas", str(installment_count)))
        rows.insert(7, ("Data limite informada", format_date_pt(contractual_final_date)))

    for label, value in rows:
        st.markdown(f"<div class='info-row'><span>{label}</span><strong>{value}</strong></div>", unsafe_allow_html=True)


def render_parameters(
    installments: list[Installment],
    radars: list[RadarWindow],
    present_value: float,
    projection: dict[str, object],
) -> None:
    operation_mode = str(projection["operation_mode"])
    st.subheader("Parâmetros / Fórmulas")
    st.markdown(
        """
        <div class="formula-box">
            <strong>Valor presente</strong><br>
            VP = soma(Parcela_i / (1 + i)^(t_i / 30))
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"**Resultado:** {format_brl(present_value)}")

    if operation_mode == "Por parcelas":
        st.caption(
            "Regra do modo: a quantidade informada define os próximos ciclos mensais do hospital; "
            f"o prazo total real é {projection['real_total_term_days']} dias."
        )
    else:
        st.caption(
            "Regra do modo: o prazo informado limita os ciclos mensais do hospital; "
            f"a quantidade calculada é {projection['calculated_installment_count']} parcelas."
        )

    st.markdown("**Datas das parcelas**")
    st.caption("A primeira parcela vence no primeiro pagamento do hospital após a carência; as demais seguem mensalmente.")
    for item in installments:
        st.caption(
            f"Parcela {item.number}: {format_date_pt(item.due_date)} | "
            f"{item.days_from_advance} dias | VP {format_brl(item.present_value)}"
        )

    st.markdown("**Janelas de radar**")
    for radar in radars:
        st.caption(
            f"{radar.month_label}: {format_date_pt(radar.start_date)} a "
            f"{format_date_pt(radar.end_date)} | QMM {format_brl(radar.qmm_value)}"
        )
    st.info("No primeiro dia do radar, o QMM assume o valor futuro projetado até o fim da janela e fica limitado ao DC.")


def build_timeline_comments(
    advance_date: date,
    grace_end: date,
    installments: list[Installment],
    radars: list[RadarWindow],
) -> pd.DataFrame:
    rows = [
        {
            "Data": format_date_pt(advance_date),
            "Marco": "Antecipação",
            "Comentário": "Crédito do valor presente ao médico e início da curva QMM.",
        },
        {
            "Data": format_date_pt(grace_end),
            "Marco": "Fim da carência",
            "Comentário": "A partir desta data o QMM volta a crescer linearmente até o próximo radar.",
        },
    ]
    for radar in radars:
        rows.append(
            {
                "Data": f"{format_date_pt(radar.start_date)} a {format_date_pt(radar.end_date)}",
                "Marco": f"Radar {radar.month_label}",
                "Comentário": f"QMM flat em {format_brl(radar.qmm_value)} durante a janela.",
            }
        )
    for item in installments:
        rows.append(
            {
                "Data": format_date_pt(item.due_date),
                "Marco": f"Vencimento da parcela {item.number}",
                "Comentário": f"Cobrança acumulada sobe em {format_brl(item.amount)}.",
            }
        )
    return pd.DataFrame(rows)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .main .block-container {
            max-width: 1440px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        h1, h2, h3 {
            color: #172033;
            letter-spacing: 0;
        }
        .metric-card {
            border: 1px solid #d9e0ea;
            border-left: 4px solid #c1121f;
            border-radius: 8px;
            padding: 14px 16px;
            background: #ffffff;
            min-height: 92px;
            box-shadow: 0 6px 20px rgba(31, 41, 55, 0.05);
        }
        .metric-card span {
            display: block;
            color: #64748b;
            font-size: 0.82rem;
            font-weight: 700;
            text-transform: uppercase;
        }
        .metric-card strong {
            display: block;
            color: #172033;
            font-size: 1.25rem;
            margin-top: 5px;
        }
        .metric-card small {
            color: #64748b;
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            gap: 18px;
            border-bottom: 1px solid #e8edf3;
            padding: 9px 0;
            font-size: 0.94rem;
        }
        .info-row span {
            color: #5d6b82;
        }
        .info-row strong {
            color: #172033;
            text-align: right;
        }
        .formula-box {
            border: 1px solid #d9e0ea;
            border-radius: 8px;
            padding: 12px 14px;
            background: #f8fafc;
            color: #243447;
            font-size: 0.95rem;
            margin-bottom: 10px;
        }
        div[data-testid="stSidebar"] {
            background: #f7f9fc;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="Simulação de Antecipação Médica",
        page_icon="",
        layout="wide",
    )
    inject_styles()

    st.title("Simulação de Antecipação de Recebíveis Médicos")
    st.caption("Curvas executivas de QMM, cobrança e Direito Creditório com radar mensal calculado em dias úteis.")

    with st.sidebar:
        st.header("Parâmetros da operação")
        advance_date = st.date_input("Data da antecipação", value=date(2026, 4, 18), format="DD/MM/YYYY")
        hospital_payment_day = st.number_input("Dia do mês de pagamento do hospital", min_value=1, max_value=31, value=20)
        operation_mode = st.radio(
            "Modo de definição da operação",
            options=["Por parcelas", "Por prazo total"],
            horizontal=False,
        )
        if operation_mode == "Por parcelas":
            installment_count_input = st.number_input(
                "Quantidade de parcelas de liquidação do médico",
                min_value=1,
                max_value=60,
                value=3,
                step=1,
            )
            total_term_days_input = None
            st.caption("O prazo total será calculado pelo último vencimento hospitalar usado.")
        else:
            total_term_days_input = st.number_input(
                "Prazo total da operação (dias corridos)",
                min_value=1,
                value=93,
                step=1,
            )
            installment_count_input = None
            st.caption("A quantidade de parcelas será calculada pelos vencimentos dentro do prazo.")

        monthly_rate_pct = st.number_input("Taxa de custo da antecipação (% ao mês)", min_value=0.0, value=2.5, step=0.1)
        grace_days = st.number_input("Carência (dias corridos)", min_value=0, max_value=3650, value=30, step=1)
        dc_value = st.number_input("Valor do Direito Creditório (DC)", min_value=0.01, value=100000.0, step=1000.0)
        split_automatically = st.toggle("Dividir DC automaticamente entre as parcelas", value=True)
        if not split_automatically:
            installment_amount = st.number_input("Valor de cada parcela", min_value=0.01, value=50000.0, step=1000.0)
        else:
            installment_amount = None

    try:
        projection = build_projection(
            advance_date=advance_date,
            hospital_payment_day=int(hospital_payment_day),
            operation_mode=operation_mode,
            monthly_rate_pct=float(monthly_rate_pct),
            total_term_days=int(total_term_days_input) if total_term_days_input is not None else None,
            grace_days=int(grace_days),
            dc_value=float(dc_value),
            installment_count=int(installment_count_input) if installment_count_input is not None else None,
            installment_amount=float(installment_amount) if installment_amount is not None else None,
            split_automatically=bool(split_automatically),
        )
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    present_value = float(projection["present_value"])
    installments = projection["installments"]
    radars = projection["radars"]
    grace_end = projection["grace_end"]
    installment_count = int(projection["calculated_installment_count"])
    installment_amount = float(projection["installment_amount"])
    real_total_term_days = int(projection["real_total_term_days"])

    with st.sidebar:
        st.divider()
        st.subheader("Resultado do calendário")
        if operation_mode == "Por parcelas":
            st.metric("Prazo total calculado", f"{real_total_term_days} dias")
        else:
            st.metric("Quantidade de parcelas calculada", installment_count)
        st.caption(f"Valor por parcela: {format_brl(installment_amount)}")
        st.caption(f"Última parcela: {format_date_pt(projection['final_date'])}")

    metric_cols = st.columns(4)
    with metric_cols[0]:
        render_metric_card("VP creditado", format_brl(present_value), "valor líquido projetado")
    with metric_cols[1]:
        render_metric_card("Direito Creditório", format_brl(float(dc_value)), "limite do QMM")
    with metric_cols[2]:
        render_metric_card("Radar mensal", f"{len(radars)} janelas", "5 dias úteis antes/depois")
    with metric_cols[3]:
        render_metric_card("Liquidação final", format_date_pt(projection["final_date"]), "ajustada ao hospital")

    chart_col, side_col = st.columns([2.45, 1], gap="large")
    with chart_col:
        fig = build_chart(projection, advance_date, float(dc_value))
        st.plotly_chart(fig, use_container_width=True)

    with side_col:
        render_assumptions(
            advance_date,
            int(hospital_payment_day),
            float(dc_value),
            int(grace_days),
            float(monthly_rate_pct),
            present_value,
            projection,
        )
        st.divider()
        render_parameters(installments, radars, present_value, projection)

    st.subheader("Comentários / Marcos")
    timeline = build_timeline_comments(advance_date, grace_end, installments, radars)
    st.dataframe(timeline, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
