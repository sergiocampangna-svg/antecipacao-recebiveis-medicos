from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from unicodedata import normalize

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


BRL_PREFIX = "R$ "
QMM_COLOR = "#c1121f"
COBRANCA_COLOR = "#f28c28"
DC_COLOR = "#111111"
RADAR_COLOR = "rgba(33, 94, 150, 0.13)"
GRID_COLOR = "#e8edf3"
DOCTOR_FIXED_TERM_DAYS = 90
DEFAULT_GRACE_DAYS = 30
DEFAULT_ACCRUAL_START_DELAY_DAYS = 30
FIXED_GRACE_RULE_DESCRIPTION = "primeiro pagamento hospitalar elegível após a carência configurada"
DEFAULT_RECEIVABLE_VALUE = 125000.0
DEFAULT_ADVANCE_PCT = 80.0
DEFAULT_ADVANCE_DATE = date(2026, 4, 1)
DEFAULT_HOSPITAL_BUSINESS_DAY = 15
DEFAULT_MONTHLY_RATE_PCT = 3.860968516779823
DEFAULT_BENCHMARK_ANNUAL_PCT = 14.75
DEFAULT_BENCHMARK_MODE = "Avançado"
DEFAULT_CESSION_FEE_PCT = 0.10
DEFAULT_PERFORMANCE_FEE_PCT = 10.0
PRICING_POLICY_RATE = "Taxa de antecipação informada"
PRICING_POLICY_TARGET_XIRR = "XIRR alvo do fundo"
DEFAULT_TARGET_XIRR_FUND_ANNUAL_PCT = 60.0
DEFAULT_BENCHMARK_RATE_POINTS = [
    (date(2026, 4, 1), 14.75),
    (date(2026, 4, 2), 14.75),
    (date(2026, 4, 6), 14.75),
    (date(2026, 4, 7), 14.75),
    (date(2026, 4, 8), 14.75),
    (date(2026, 4, 9), 14.74),
    (date(2026, 4, 10), 14.74),
    (date(2026, 4, 11), 14.74),
    (date(2026, 4, 14), 14.74),
    (date(2026, 4, 21), 14.74),
    (date(2026, 4, 25), 14.74),
    (date(2026, 4, 30), 14.74),
    (date(2026, 5, 1), 14.74),
    (date(2026, 5, 2), 14.74),
    (date(2026, 5, 7), 14.74),
    (date(2026, 5, 8), 14.74),
    (date(2026, 5, 9), 14.71),
    (date(2026, 5, 12), 14.69),
    (date(2026, 5, 26), 14.68),
    (date(2026, 5, 27), 14.67),
    (date(2026, 5, 28), 14.67),
    (date(2026, 5, 29), 14.67),
    (date(2026, 5, 30), 14.66),
    (date(2026, 6, 2), 14.65),
    (date(2026, 6, 6), 14.64),
    (date(2026, 6, 10), 14.64),
    (date(2026, 6, 11), 14.63),
    (date(2026, 6, 24), 14.62),
    (date(2026, 6, 25), 14.62),
    (date(2026, 6, 26), 14.62),
    (date(2026, 6, 27), 14.61),
    (date(2026, 7, 4), 14.61),
    (date(2026, 7, 7), 14.61),
    (date(2026, 7, 8), 14.60),
    (date(2026, 7, 10), 14.60),
    (date(2026, 7, 14), 14.60),
    (date(2026, 7, 23), 14.59),
    (date(2026, 7, 25), 14.58),
    (date(2026, 7, 29), 14.57),
    (date(2026, 7, 30), 14.56),
    (date(2026, 7, 31), 14.55),
    (date(2026, 8, 5), 14.55),
    (date(2026, 8, 8), 14.55),
    (date(2026, 8, 11), 14.54),
]
PARAMETRIZED_HOLIDAYS = {
    date(2026, 2, 16),
    date(2026, 2, 17),
    date(2026, 4, 3),
    date(2026, 4, 21),
    date(2026, 5, 1),
    date(2026, 6, 4),
    date(2026, 9, 7),
    date(2026, 10, 12),
    date(2026, 11, 2),
    date(2026, 11, 15),
    date(2026, 11, 20),
    date(2026, 12, 25),
    date(2027, 1, 1),
    date(2027, 2, 8),
    date(2027, 2, 9),
    date(2027, 3, 26),
    date(2027, 4, 21),
    date(2027, 5, 1),
    date(2027, 5, 27),
    date(2027, 9, 7),
    date(2027, 10, 12),
    date(2027, 11, 2),
    date(2027, 11, 15),
    date(2027, 11, 20),
    date(2027, 12, 25),
    date(2028, 1, 1),
    date(2028, 2, 28),
    date(2028, 2, 29),
    date(2028, 4, 14),
    date(2028, 4, 21),
    date(2028, 5, 1),
    date(2028, 6, 15),
    date(2028, 9, 7),
    date(2028, 10, 12),
    date(2028, 11, 2),
    date(2028, 11, 15),
    date(2028, 11, 20),
    date(2028, 12, 25),
}


def calculate_credit_limit(receivable_value: float, advance_pct: float) -> float:
    return max(receivable_value, 0.0) * max(min(advance_pct, 100.0), 0.0) / 100


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


@dataclass(frozen=True)
class DelayParameters:
    analysis_date: date
    monthly_late_rate: float
    fine_fixed: float
    fine_pct: float
    tolerance_days: int
    interest_base: str
    adjusted_qmm_enabled: bool


def format_brl(value: float) -> str:
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{BRL_PREFIX}{formatted}"


def format_brl_markdown(value: float) -> str:
    return format_brl(value).replace("$", r"\$")


def format_pct(value: float) -> str:
    return f"{value:.2f}%".replace(".", ",")


def format_optional_pct(value: float | None) -> str:
    if value is None:
        return "-"
    return format_pct(float(value) * 100)


def format_date_pt(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def excel_workday(value: date, business_days: int, holidays: set[date] | None = None) -> date:
    holidays = holidays or PARAMETRIZED_HOLIDAYS
    step = 1 if business_days >= 0 else -1
    remaining = abs(business_days)
    current = value
    while remaining:
        current += timedelta(days=step)
        if is_business_day(current, holidays):
            remaining -= 1
    return current


def month_payment_date(reference: date, hospital_payment_day: int) -> date:
    # Regra operacional: "nº dia útil" significa o enésimo dia útil dentro do
    # próprio mês de referência, excluindo finais de semana e feriados.
    target_business_day = max(int(hospital_payment_day), 1)
    current = date(reference.year, reference.month, 1)
    month_end = date(reference.year, reference.month, monthrange(reference.year, reference.month)[1])
    business_day_count = 0
    last_business_day = current

    while current <= month_end:
        if is_business_day(current, PARAMETRIZED_HOLIDAYS):
            business_day_count += 1
            last_business_day = current
            if business_day_count == target_business_day:
                return current
        current += timedelta(days=1)

    return last_business_day


def next_hospital_payment_date(reference: date, hospital_payment_day: int) -> date:
    candidate = month_payment_date(reference, hospital_payment_day)
    if candidate <= reference:
        candidate = month_payment_date(add_months(reference, 1), hospital_payment_day)
    return candidate


def hospital_payment_on_or_after(reference: date, hospital_payment_day: int) -> date:
    candidate = month_payment_date(reference, hospital_payment_day)
    if candidate < reference:
        candidate = month_payment_date(add_months(reference, 1), hospital_payment_day)
    return candidate


def first_installment_cycle_date(
    advance_date: date,
    hospital_payment_day: int,
    grace_days: int,
) -> date:
    # A carência é a trava operacional para definir o primeiro repasse elegível.
    # O radar só passa a considerar pagamentos hospitalares em ou após essa data.
    eligibility_date = advance_date + timedelta(days=max(int(grace_days), 0))
    return hospital_payment_on_or_after(eligibility_date, hospital_payment_day)


def calculate_accrual_start_date(advance_date: date, hospital_payment_day: int) -> date:
    payment_date_in_month = month_payment_date(advance_date, hospital_payment_day)
    if advance_date <= payment_date_in_month:
        return payment_date_in_month
    return advance_date


def calculate_accrual_start_date_from_final(final_date: date, total_term_days: int) -> date:
    # Convenção da planilha: WORKDAY(DataVencimento - Prazo + 1, -1, feriados).
    return excel_workday(final_date - timedelta(days=total_term_days - 1), -1, PARAMETRIZED_HOLIDAYS)


def calculate_accrual_start_date_from_delay(advance_date: date, accrual_start_delay_days: int) -> date:
    return advance_date + timedelta(days=max(int(accrual_start_delay_days), 0))


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
    return excel_workday(value, business_days, PARAMETRIZED_HOLIDAYS)


def is_business_day(value: date, holidays: set[date] | None = None) -> bool:
    holidays = holidays or PARAMETRIZED_HOLIDAYS
    return value.weekday() < 5 and value not in holidays


def business_days_between(start_date: date, end_date: date, holidays: set[date] | None = None) -> int:
    if end_date <= start_date:
        return 0
    current = start_date
    days = 0
    while current < end_date:
        current += timedelta(days=1)
        if is_business_day(current, holidays):
            days += 1
    return days


def contar_dias_uteis(data_inicio: date, data_fim: date, feriados: set[date] | None = None) -> int:
    if data_fim < data_inicio:
        return 0
    current = data_inicio
    total = 0
    while current <= data_fim:
        if is_business_day(current, feriados):
            total += 1
        current += timedelta(days=1)
    return total


def holidays_between(data_inicio: date, data_fim: date, feriados: set[date] | None = None) -> list[date]:
    feriados = feriados or PARAMETRIZED_HOLIDAYS
    return sorted(value for value in feriados if data_inicio <= value <= data_fim and value.weekday() < 5)


def monthly_to_annual_business_rate(monthly_rate: float) -> float:
    return (1 + monthly_rate) ** 12 - 1


def calcular_taxa_anual_equivalente(taxa_mensal: float) -> float:
    return (1 + taxa_mensal) ** 12 - 1


def calcular_valor_presente(valor_face: float, taxa_anual: float, dias_uteis: int) -> float:
    return valor_face / ((1 + taxa_anual) ** (dias_uteis / 252))


def obter_datas_base_vp(
    data_antecipacao: date,
    data_inicio_accrual: date,
    data_vencimento: date,
    vp_sensivel_data_antecipacao: bool,
) -> tuple[date, date]:
    if vp_sensivel_data_antecipacao:
        return data_antecipacao, data_vencimento
    return data_inicio_accrual, data_vencimento


def annual_to_monthly_rate(annual_rate: float) -> float:
    return (1 + annual_rate) ** (21 / 252) - 1


def xnpv(rate: float, cash_flows: list[tuple[date, float]]) -> float:
    if not cash_flows:
        return 0.0
    base_date = cash_flows[0][0]
    return sum(value / ((1 + rate) ** ((flow_date - base_date).days / 365)) for flow_date, value in cash_flows)


def calculate_xirr(cash_flows: list[tuple[date, float]]) -> float | None:
    if not cash_flows:
        return None
    values = [value for _, value in cash_flows]
    if not any(value < 0 for value in values) or not any(value > 0 for value in values):
        return None

    low = -0.9999
    high = 10.0
    low_value = xnpv(low, cash_flows)
    high_value = xnpv(high, cash_flows)
    while low_value * high_value > 0 and high < 1000:
        high *= 2
        high_value = xnpv(high, cash_flows)
    if low_value * high_value > 0:
        return None

    for _ in range(100):
        mid = (low + high) / 2
        mid_value = xnpv(mid, cash_flows)
        if abs(mid_value) < 1e-7:
            return mid
        if low_value * mid_value <= 0:
            high = mid
            high_value = mid_value
        else:
            low = mid
            low_value = mid_value
    return (low + high) / 2


def normalize_benchmark_table(table: pd.DataFrame | dict | None) -> pd.DataFrame:
    if table is None:
        return pd.DataFrame(columns=["data", "taxa_benchmark"])
    if isinstance(table, dict):
        if {"data", "taxa_benchmark"}.issubset(table.keys()):
            data_values = table.get("data")
            rate_values = table.get("taxa_benchmark")
            if isinstance(data_values, (list, tuple, pd.Series)) and isinstance(rate_values, (list, tuple, pd.Series)):
                return pd.DataFrame({"data": data_values, "taxa_benchmark": rate_values})
        return pd.DataFrame(columns=["data", "taxa_benchmark"])
    if not isinstance(table, pd.DataFrame) or table.empty:
        return pd.DataFrame(columns=["data", "taxa_benchmark"])
    if "data" not in table.columns or "taxa_benchmark" not in table.columns:
        return pd.DataFrame(columns=["data", "taxa_benchmark"])
    return table[["data", "taxa_benchmark"]].copy()


def parse_benchmark_table(table: pd.DataFrame | dict | None) -> dict[date, float]:
    table = normalize_benchmark_table(table)
    if table.empty:
        return {}
    parsed: dict[date, float] = {}
    for _, row in table.iterrows():
        raw_date = row.get("data")
        raw_rate = row.get("taxa_benchmark")
        if raw_date in (None, "") or pd.isna(raw_date) or raw_rate in (None, "") or pd.isna(raw_rate):
            continue
        parsed[pd.to_datetime(raw_date).date()] = max(float(raw_rate), 0.0) / 100
    return parsed


def default_benchmark_table() -> pd.DataFrame:
    return pd.DataFrame(
        [{"data": point_date, "taxa_benchmark": rate} for point_date, rate in DEFAULT_BENCHMARK_RATE_POINTS]
    )


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
    accrual_start_date: date | None = None,
    final_date: date | None = None,
    dc_value: float | None = None,
    holidays: set[date] | None = None,
    vp_start_date: date | None = None,
) -> tuple[float, list[Installment]]:
    if accrual_start_date is not None and final_date is not None and dc_value is not None:
        annual_rate = calcular_taxa_anual_equivalente(monthly_rate)
        business_days = contar_dias_uteis(vp_start_date or accrual_start_date, final_date, holidays)
        total_present_value = calcular_valor_presente(dc_value, annual_rate, business_days)
        installments = []
        for index, due_date in enumerate(installment_dates, start=1):
            days_from_advance = max((due_date - advance_date).days, 0)
            allocated_pv = total_present_value * (installment_amount / dc_value) if dc_value > 0 else 0.0
            installments.append(
                Installment(
                    number=index,
                    due_date=due_date,
                    amount=installment_amount,
                    days_from_advance=days_from_advance,
                    present_value=allocated_pv,
                )
            )
        return total_present_value, installments

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


def solve_monthly_rate_for_target_fund_xirr(
    target_xirr_annual: float,
    *,
    advance_date: date,
    hospital_payment_day: int,
    operation_mode: str,
    grace_days: int,
    dc_value: float,
    operational_variable_pct: float,
    operational_fixed_cost: float,
    operational_cost_allocation: str,
    benchmark_annual_pct: float,
    benchmark_mode: str,
    benchmark_table: pd.DataFrame | dict | None,
    cession_fee_pct: float,
    performance_fee_pct: float,
    receivable_value: float | None,
    advance_pct: float,
    radar_business_days: int,
    late_monthly_rate_pct: float,
    late_fine_pct: float,
    late_fine_fixed: float,
    vp_sensitive_to_advance_date: bool,
    total_term_days: int | None,
    installment_count: int | None,
    installment_amount: float | None,
    accrual_start_delay_days: int = DEFAULT_ACCRUAL_START_DELAY_DAYS,
) -> float:
    if target_xirr_annual <= -0.999:
        raise ValueError("Informe uma XIRR alvo maior que -99,9% ao ano.")

    def evaluated_xirr(rate_pct: float) -> float:
        projection = build_projection(
            advance_date=advance_date,
            hospital_payment_day=hospital_payment_day,
            operation_mode=operation_mode,
            monthly_rate_pct=rate_pct,
            grace_days=grace_days,
            dc_value=dc_value,
            operational_variable_pct=operational_variable_pct,
            operational_fixed_cost=operational_fixed_cost,
            operational_cost_allocation=operational_cost_allocation,
            benchmark_annual_pct=benchmark_annual_pct,
            benchmark_mode=benchmark_mode,
            benchmark_table=benchmark_table,
            cession_fee_pct=cession_fee_pct,
            performance_fee_pct=performance_fee_pct,
            receivable_value=receivable_value,
            advance_pct=advance_pct,
            radar_business_days=radar_business_days,
            late_monthly_rate_pct=late_monthly_rate_pct,
            late_fine_pct=late_fine_pct,
            late_fine_fixed=late_fine_fixed,
            vp_sensitive_to_advance_date=vp_sensitive_to_advance_date,
            total_term_days=total_term_days,
            installment_count=installment_count,
            installment_amount=installment_amount,
            pricing_policy=PRICING_POLICY_RATE,
            target_xirr_fund_annual_pct=None,
            accrual_start_delay_days=accrual_start_delay_days,
        )
        xirr_value = projection.get("xirr_fund_annual")
        if xirr_value is None:
            raise ValueError("Não foi possível calcular a XIRR líquida para resolver a taxa de antecipação.")
        return float(xirr_value)

    low = 0.0
    high = 10.0
    low_gap = evaluated_xirr(low) - target_xirr_annual
    high_gap = evaluated_xirr(high) - target_xirr_annual

    while high_gap < 0 and high < 500:
        high *= 2
        high_gap = evaluated_xirr(high) - target_xirr_annual

    if low_gap > 0:
        raise ValueError("A XIRR alvo está abaixo do retorno mínimo calculado com taxa de antecipação zero.")
    if high_gap < 0:
        raise ValueError(
            "A XIRR alvo não foi atingida mesmo com taxa de antecipação muito elevada. "
            "Revise o alvo, prazo ou parâmetros do fundo."
        )

    for _ in range(60):
        mid = (low + high) / 2
        mid_gap = evaluated_xirr(mid) - target_xirr_annual
        if abs(mid_gap) < 1e-8:
            return mid
        if mid_gap >= 0:
            high = mid
        else:
            low = mid
    return (low + high) / 2


def calculate_operational_costs(
    transaction_value: float,
    operational_variable_pct: float,
    operational_fixed_cost: float,
) -> dict[str, float]:
    variable_cost = 0.0
    fixed_cost = 0.0
    total_cost = 0.0
    return {
        "operational_variable_cost": variable_cost,
        "operational_fixed_cost": fixed_cost,
        "operational_total_cost": total_cost,
    }


def calculate_monthly_anticipation_rate_pct(
    monthly_interest_rate_pct: float,
    operational_variable_pct: float,
    operational_fixed_cost: float,
    transaction_value: float,
) -> float:
    return monthly_interest_rate_pct


def calculate_anticipation_cost_breakdown(
    gross_value: float,
    financial_present_value: float,
    operational_variable_pct: float,
    operational_fixed_cost: float,
) -> dict[str, float]:
    operational_costs = calculate_operational_costs(
        gross_value,
        operational_variable_pct,
        operational_fixed_cost,
    )
    net_disbursement = financial_present_value
    financial_cost = gross_value - financial_present_value
    total_cost = gross_value - net_disbursement
    equivalent_rate = total_cost / gross_value if gross_value > 0 else 0.0
    return {
        "financial_present_value": financial_present_value,
        "financial_cost": financial_cost,
        "net_disbursement": net_disbursement,
        "anticipation_cost": total_cost,
        "equivalent_operation_rate": equivalent_rate,
        **operational_costs,
    }


def projected_qmm_value(
    target_date: date,
    final_date: date,
    present_value: float,
    dc_value: float,
    accrual_start_date: date,
    annual_operation_rate: float,
) -> float:
    if target_date <= accrual_start_date:
        return min(present_value, dc_value)

    elapsed_du = contar_dias_uteis(accrual_start_date, min(target_date, final_date), PARAMETRIZED_HOLIDAYS)
    projected_value = present_value * ((1 + annual_operation_rate) ** (elapsed_du / 252))
    return min(max(projected_value, present_value), dc_value)


def calculate_radar_windows(
    payment_dates: list[date],
    advance_date: date,
    final_date: date,
    present_value: float,
    dc_value: float,
    accrual_start_date: date,
    annual_operation_rate: float,
    business_days_window: int = 5,
) -> list[RadarWindow]:
    radars: list[RadarWindow] = []
    for payment_date in payment_dates:
        start_date = add_business_days(payment_date, -business_days_window)
        end_date = add_business_days(payment_date, business_days_window)
        if end_date < advance_date or start_date > final_date:
            continue

        qmm_value = projected_qmm_value(
            end_date,
            final_date,
            present_value,
            dc_value,
            accrual_start_date,
            annual_operation_rate,
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
        rows.append({"date": current, "cobranca_esperada": accumulated})
    return pd.DataFrame(rows)


def build_fund_economic_curves(
    dates: pd.DatetimeIndex,
    advance_date: date,
    accrual_start_date: date,
    final_date: date,
    present_value: float,
    dc_value: float,
    annual_operation_rate: float,
    benchmark_annual_rate: float,
    cession_fee_pct: float,
    performance_fee_pct: float,
    benchmark_mode: str = "Simplificado",
    benchmark_table: pd.DataFrame | None = None,
    late_monthly_rate: float = 0.0,
    late_fine_pct: float = 0.0,
    late_fine_fixed: float = 0.0,
) -> tuple[pd.DataFrame, dict[str, float]]:
    rows = []
    cession_cost = present_value * (cession_fee_pct / 100)
    first_date = dates.date[0]
    benchmark_rates = parse_benchmark_table(benchmark_table)
    benchmark_value = present_value
    last_benchmark_rate = benchmark_annual_rate
    first_business_after_final = add_business_days(final_date, 1)
    late_daily_rate = (1 + late_monthly_rate) ** (1 / 30) - 1
    dc_economico = dc_value

    for current in dates.date:
        elapsed_du = contar_dias_uteis(accrual_start_date, min(current, final_date), PARAMETRIZED_HOLIDAYS)
        if current < accrual_start_date:
            cobranca_financeira = present_value
            benchmark = present_value
        else:
            cobranca_financeira = present_value * ((1 + annual_operation_rate) ** (elapsed_du / 252))
            if is_business_day(current, PARAMETRIZED_HOLIDAYS):
                if benchmark_mode == "Avançado" and benchmark_rates:
                    last_benchmark_rate = benchmark_rates.get(current, last_benchmark_rate)
                benchmark_value *= (1 + last_benchmark_rate) ** (1 / 252)
            benchmark = benchmark_value

        cobranca_financeira = min(cobranca_financeira, dc_value)
        if current <= final_date:
            dc_economico = dc_value
        else:
            fine = dc_value * late_fine_pct + late_fine_fixed if current == first_business_after_final else 0.0
            mora = dc_economico * late_daily_rate
            dc_economico = dc_economico + fine + mora
        spread = (cobranca_financeira if current <= final_date else dc_economico) - benchmark
        fee_performance = max(spread, 0) * (performance_fee_pct / 100)
        curva_liquida = cobranca_financeira - cession_cost - fee_performance
        rows.append(
            {
                "date": current,
                "cobranca_financeira": cobranca_financeira,
                "benchmark": benchmark,
                "benchmark_rate_annual": last_benchmark_rate,
                "dc_economico": dc_economico,
                "spread_bruto": spread,
                "cessao_fidc": cession_cost if current == first_date else 0.0,
                "fee_performance": fee_performance,
                "curva_liquida_fidc": curva_liquida,
            }
        )

    df = pd.DataFrame(rows)
    final_row = df.loc[df["date"] == final_date].iloc[-1]
    final_liquid_value = float(final_row["curva_liquida_fidc"])
    gross_cash_flows = [(advance_date, -present_value), (final_date, dc_value)]
    fund_cash_flows = [(advance_date, -(present_value + cession_cost)), (final_date, final_liquid_value)]
    xirr_gross_annual = calculate_xirr(gross_cash_flows)
    xirr_fund_annual = calculate_xirr(fund_cash_flows)
    xirr_gross_monthly = annual_to_monthly_rate(xirr_gross_annual) if xirr_gross_annual is not None else None
    xirr_fund_monthly = annual_to_monthly_rate(xirr_fund_annual) if xirr_fund_annual is not None else None
    metrics = {
        "annual_operation_rate": annual_operation_rate,
        "benchmark_annual_rate": benchmark_annual_rate,
        "benchmark_mode": benchmark_mode,
        "cession_fee_pct": cession_fee_pct,
        "performance_fee_pct": performance_fee_pct,
        "cession_cost": cession_cost,
        "benchmark_final": float(final_row["benchmark"]),
        "spread_bruto_final": float(final_row["spread_bruto"]),
        "performance_fee_final": float(final_row["fee_performance"]),
        "fidc_liquid_curve_final": final_liquid_value,
        "xirr_gross_annual": xirr_gross_annual,
        "xirr_gross_monthly": xirr_gross_monthly,
        "xirr_fund_annual": xirr_fund_annual,
        "xirr_fund_monthly": xirr_fund_monthly,
        "tirr_annual": xirr_fund_annual or 0.0,
    }
    return df, metrics


def default_liquidation_rows(installments: list[Installment]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Parcela": item.number,
                "Data de vencimento": item.due_date,
                "Valor previsto": item.amount,
                "Status": "Pago integralmente",
                "Data de pagamento": item.due_date,
                "Valor pago": item.amount,
                "Pagamento adicional": 0.0,
            }
            for item in installments
        ]
    )


def normalize_delay_treatment(delay_treatment: str) -> str:
    normalized = normalize("NFKD", str(delay_treatment or "")).encode("ascii", "ignore").decode("ascii").lower()
    if normalized.startswith("liquidar"):
        return "liquidar"
    if normalized.startswith("distribuir"):
        return "distribuir"
    return "manter"


def build_delay_scenario_rows(
    installments: list[Installment],
    delayed_numbers: list[int],
    status_by_number: dict[int, str],
    paid_by_number: dict[int, float],
    payment_date_by_number: dict[int, date],
    delay_treatment: str = "Manter atraso em aberto",
) -> pd.DataFrame:
    rows = default_liquidation_rows(installments)
    treatment = normalize_delay_treatment(delay_treatment)
    delayed_set = set(delayed_numbers)
    shortfall_by_number: dict[int, float] = {}
    for index, row in rows.iterrows():
        number = int(row["Parcela"])
        if number not in delayed_set:
            continue

        status = status_by_number.get(number, "Não pago")
        amount = float(row["Valor previsto"])
        rows.loc[index, "Status"] = status
        rows.loc[index, "Data de pagamento"] = payment_date_by_number.get(number, row["Data de vencimento"])
        if status == "Pago parcialmente":
            paid_value = min(max(paid_by_number.get(number, 0.0), 0.0), amount)
            rows.loc[index, "Valor pago"] = paid_value
        else:
            paid_value = 0.0
            rows.loc[index, "Valor pago"] = 0.0
        shortfall_by_number[number] = max(amount - paid_value, 0.0)

    if treatment != "manter" and shortfall_by_number:
        total_shortfall = sum(shortfall_by_number.values())
        future_indexes = [
            index
            for index, row in rows.iterrows()
            if int(row["Parcela"]) > min(shortfall_by_number)
            and int(row["Parcela"]) not in delayed_set
        ]
        if treatment == "liquidar":
            future_indexes = future_indexes[:1]

        if future_indexes:
            extra_per_installment = total_shortfall / len(future_indexes)
            for index in future_indexes:
                rows.loc[index, "Pagamento adicional"] = extra_per_installment
    return rows


def future_regularization_indexes(
    rows: pd.DataFrame,
    delayed_numbers: list[int],
    delay_treatment: str,
) -> list[int]:
    if not delayed_numbers:
        return []

    delayed_set = set(delayed_numbers)
    first_delayed = min(delayed_numbers)
    indexes = [
        index
        for index, row in rows.iterrows()
        if int(row["Parcela"]) > first_delayed and int(row["Parcela"]) not in delayed_set
    ]
    treatment = normalize_delay_treatment(delay_treatment)
    if treatment == "liquidar":
        return indexes[:1]
    if treatment == "distribuir":
        return indexes
    return []


def settle_delay_treatment(
    installments: list[Installment],
    scenario_rows: pd.DataFrame,
    params: DelayParameters,
    delayed_numbers: list[int],
    delay_treatment: str,
) -> tuple[pd.DataFrame, dict[str, object]]:
    rows = scenario_rows.copy()
    liquidation = calculate_liquidation_impacts(installments, rows, params)
    target_indexes = future_regularization_indexes(rows, delayed_numbers, delay_treatment)

    if normalize_delay_treatment(delay_treatment) == "manter" or not target_indexes:
        return rows, liquidation

    # Recalcula em rodadas curtas porque mora/multa também consomem pagamentos
    # pela ordem de baixa. O residual é incorporado às parcelas futuras até zerar.
    for _ in range(6):
        residual = float(liquidation["saldo_exigivel_total"])
        if residual <= 0.01:
            break

        extra_per_target = residual / len(target_indexes)
        for index in target_indexes:
            current_extra = float(rows.loc[index, "Pagamento adicional"] or 0.0)
            rows.loc[index, "Pagamento adicional"] = current_extra + extra_per_target

        liquidation = calculate_liquidation_impacts(installments, rows, params)

    return rows, liquidation


def calculate_automatic_analysis_date(scenario_rows: pd.DataFrame, installments: list[Installment]) -> date:
    payment_dates = []
    for _, row in scenario_rows.iterrows():
        paid_value = float(row.get("Valor pago", 0.0) or 0.0)
        if paid_value <= 0:
            continue
        fallback = row.get("Data de vencimento", installments[-1].due_date)
        payment_dates.append(parse_date_value(row.get("Data de pagamento"), fallback))

    if payment_dates:
        return max(payment_dates) + timedelta(days=1)
    return max(item.due_date for item in installments) + timedelta(days=1)


def parse_date_value(value: object, fallback: date) -> date:
    if isinstance(value, date):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return fallback
    return parsed.date()


def normalize_status(value: object) -> str:
    raw = str(value or "").strip().lower()
    ascii_raw = normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
    if "parcial" in ascii_raw:
        return "Pago parcialmente"
    if "nao" in ascii_raw or "no pago" in ascii_raw:
        return "Não pago"
    return "Pago integralmente"


def calculate_interest(
    principal: float,
    start_date: date,
    end_date: date,
    params: DelayParameters,
) -> float:
    effective_start = start_date + timedelta(days=params.tolerance_days)
    if principal <= 0 or end_date <= effective_start:
        return 0.0

    days = (end_date - effective_start).days
    daily_rate = (1 + params.monthly_late_rate) ** (1 / 30) - 1
    return principal * daily_rate * days


def normalize_payment_schedule(
    edited_rows: pd.DataFrame,
    installments: list[Installment],
) -> pd.DataFrame:
    fallback = default_liquidation_rows(installments)
    if edited_rows is None or edited_rows.empty:
        return fallback

    normalized = fallback.copy()
    edited_by_number = {
        int(row["Parcela"]): row
        for _, row in edited_rows.iterrows()
        if pd.notna(row.get("Parcela"))
    }
    for index, row in normalized.iterrows():
        number = int(row["Parcela"])
        edited = edited_by_number.get(number)
        if edited is None:
            continue

        status = normalize_status(edited.get("Status", row["Status"]))

        due_date = row["Data de vencimento"]
        payment_date = parse_date_value(edited.get("Data de pagamento"), due_date)
        paid_value = float(edited.get("Valor pago", row["Valor pago"]) or 0)
        additional_payment = float(edited.get("Pagamento adicional", row.get("Pagamento adicional", 0.0)) or 0)
        expected_value = float(row["Valor previsto"])

        if status == "Pago integralmente":
            paid_value = expected_value
        elif status == "Não pago":
            paid_value = 0.0
        else:
            paid_value = min(max(paid_value, 0.0), expected_value)
        paid_value += max(additional_payment, 0.0)

        normalized.loc[index, "Status"] = status
        normalized.loc[index, "Data de pagamento"] = payment_date
        normalized.loc[index, "Valor pago"] = paid_value
        normalized.loc[index, "Pagamento adicional"] = max(additional_payment, 0.0)

    return normalized


def apply_payment_waterfall(
    payment_amount: float,
    mora_balance: float,
    fine_balance: float,
    overdue_balance: float,
    current_due: float,
) -> tuple[float, float, float, float, float]:
    remaining_payment = max(payment_amount, 0.0)

    paid_mora = min(remaining_payment, mora_balance)
    mora_balance -= paid_mora
    remaining_payment -= paid_mora

    paid_fine = min(remaining_payment, fine_balance)
    fine_balance -= paid_fine
    remaining_payment -= paid_fine

    paid_overdue = min(remaining_payment, overdue_balance)
    overdue_balance -= paid_overdue
    remaining_payment -= paid_overdue

    paid_current = min(remaining_payment, current_due)
    current_due -= paid_current
    remaining_payment -= paid_current

    return mora_balance, fine_balance, overdue_balance, current_due, remaining_payment


def calculate_liquidation_impacts(
    installments: list[Installment],
    edited_rows: pd.DataFrame,
    params: DelayParameters,
) -> dict[str, object]:
    schedule = normalize_payment_schedule(edited_rows, installments)
    rows: list[dict[str, object]] = []
    payments: list[tuple[date, float]] = []

    overdue_balance = 0.0
    mora_balance = 0.0
    fine_balance = 0.0
    mora_charged_total = 0.0
    fine_charged_total = 0.0
    expected_accumulated = 0.0
    realized_accumulated = 0.0
    last_interest_date = min(item.due_date for item in installments)
    calculation_horizon = params.analysis_date

    for item in installments:
        schedule_row = schedule.loc[schedule["Parcela"] == item.number].iloc[0]
        status = str(schedule_row["Status"])
        due_date = item.due_date
        payment_date = parse_date_value(schedule_row["Data de pagamento"], due_date)
        paid_value = float(schedule_row["Valor pago"] or 0.0)
        if status == "Não pago":
            payment_date = max(params.analysis_date, payment_date)
            calculation_horizon = max(calculation_horizon, payment_date)

        if paid_value > 0:
            cycle_event_date = max(due_date, min(payment_date, params.analysis_date))
        else:
            cycle_event_date = due_date
        mora_generated_cycle = 0.0
        fine_generated_cycle = 0.0
        if params.interest_base == "sobre saldo vencido":
            interest_value = calculate_interest(overdue_balance, last_interest_date, due_date, params)
        else:
            interest_value = calculate_interest(max(overdue_balance, 0), last_interest_date, due_date, params)
        mora_balance += interest_value
        mora_generated_cycle += interest_value
        mora_charged_total += interest_value

        current_due = item.amount
        expected_accumulated += item.amount

        if payment_date > due_date and paid_value > 0:
            interest_base = overdue_balance + current_due
            if params.interest_base == "sobre parcela em atraso":
                interest_base = current_due
            interest_value = calculate_interest(interest_base, due_date, payment_date, params)
            mora_balance += interest_value
            mora_generated_cycle += interest_value
            mora_charged_total += interest_value

        mora_balance, fine_balance, overdue_balance, current_due, excess_payment = apply_payment_waterfall(
            paid_value,
            mora_balance,
            fine_balance,
            overdue_balance,
            current_due,
        )

        unpaid_after_payment = current_due
        assessment_date = max(params.analysis_date, payment_date)
        if unpaid_after_payment > 0 and assessment_date > due_date + timedelta(days=params.tolerance_days):
            fine_generated_cycle = params.fine_fixed + unpaid_after_payment * params.fine_pct
            fine_balance += fine_generated_cycle
            fine_charged_total += fine_generated_cycle

        overdue_balance += unpaid_after_payment
        realized_accumulated += paid_value
        if paid_value > 0:
            payments.append((payment_date, paid_value))

        last_interest_date = max(cycle_event_date, due_date)
        saldo_exigivel = overdue_balance + mora_balance + fine_balance
        rows.append(
            {
                "Parcela": item.number,
                "Data de vencimento": due_date,
                "Valor previsto": item.amount,
                "Status": status,
                "Data de pagamento": payment_date if paid_value > 0 or status == "Não pago" else None,
                "Valor pago": paid_value,
                "Saldo em atraso": overdue_balance,
                "Mora gerada": mora_generated_cycle,
                "Multa gerada": fine_generated_cycle,
                "Mora": mora_balance,
                "Multa": fine_balance,
                "Saldo exigível atualizado": saldo_exigivel,
                "Gap de cobrança": expected_accumulated - realized_accumulated,
                "Excedente amortizado": excess_payment,
                "Pagamento adicional": float(schedule_row.get("Pagamento adicional", 0.0) or 0.0),
            }
        )

    final_interest_date = max(calculation_horizon, last_interest_date)
    final_interest_value = 0.0
    if params.interest_base == "sobre saldo vencido":
        final_interest_value = calculate_interest(overdue_balance, last_interest_date, final_interest_date, params)
        mora_balance += final_interest_value
        mora_charged_total += final_interest_value
    fine_and_mora = mora_balance + fine_balance
    expected_total = sum(item.amount for item in installments)
    realized_total = sum(amount for _, amount in payments)
    gap_total = max(expected_total - realized_total, 0.0)

    if rows:
        rows[-1]["Mora gerada"] += final_interest_value
        rows[-1]["Mora"] = mora_balance
        rows[-1]["Saldo exigível atualizado"] = overdue_balance + fine_and_mora

    return {
        "input_table": schedule,
        "result_table": pd.DataFrame(rows),
        "payments": payments,
        "expected_total": expected_total,
        "realized_total": realized_total,
        "gap_total": gap_total,
        "overdue_total": overdue_balance,
        "mora_total": mora_balance,
        "fine_total": fine_balance,
        "mora_charged_total": mora_charged_total,
        "fine_charged_total": fine_charged_total,
        "saldo_exigivel_total": overdue_balance + fine_and_mora,
    }


def build_saldo_exigivel_curve(
    dates: pd.DatetimeIndex,
    result_table: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    if result_table.empty:
        return pd.DataFrame({"date": dates.date, "saldo_exigivel_curve": 0.0})

    events = [
        (parse_date_value(row["Data de vencimento"], dates.date[0]), float(row["Saldo exigível atualizado"]))
        for _, row in result_table.iterrows()
    ]
    for current in dates.date:
        applicable = [value for event_date, value in events if current >= event_date]
        rows.append({"date": current, "saldo_exigivel_curve": applicable[-1] if applicable else 0.0})
    return pd.DataFrame(rows)


def active_radar(current: date, radars: list[RadarWindow]) -> RadarWindow | None:
    for radar in radars:
        if radar.start_date <= current <= radar.end_date:
            return radar
    return None


def radar_value_on_date(current: date, radars: list[RadarWindow]) -> float:
    radar = active_radar(current, radars)
    return radar.qmm_value if radar else 0.0


def next_radar_after(current: date, radars: list[RadarWindow]) -> RadarWindow | None:
    future_radars = [radar for radar in radars if radar.start_date > current]
    return min(future_radars, key=lambda radar: radar.start_date, default=None)


def build_qmm_curve(
    dates: pd.DatetimeIndex,
    advance_date: date,
    final_date: date,
    present_value: float,
    dc_value: float,
    accrual_start_date: date,
    radars: list[RadarWindow],
) -> pd.DataFrame:
    rows = []
    qmm_radars = [radar for radar in radars if radar.qmm_value > 0]

    for current in dates.date:
        radar = active_radar(current, qmm_radars)
        if radar:
            qmm = radar.qmm_value
        elif current <= accrual_start_date:
            qmm = present_value
        else:
            upcoming_radar = next_radar_after(current, qmm_radars)
            segment_start = accrual_start_date
            segment_start_value = present_value

            previous_radars = [item for item in qmm_radars if item.end_date < current]
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


def build_daily_evolution_table(
    projection: dict[str, object],
    late_monthly_rate: float = 0.0,
    fine_pct: float = 0.0,
    fine_fixed: float = 0.0,
) -> pd.DataFrame:
    df = projection["df"].copy()
    annual_rate = float(projection["annual_operation_rate"])
    daily_business_rate = (1 + annual_rate) ** (1 / 252) - 1
    late_daily_rate = (1 + late_monthly_rate) ** (1 / 30) - 1
    present_value = float(projection["present_value"])
    dc_value = float(df["dc"].iloc[0])
    receivable_value = float(projection["receivable_value"])
    final_date = projection["final_date"]
    advance_date = projection["advance_date"]
    accrual_start_date = projection["accrual_start_date"]
    radars = projection["radars"]
    first_business_after_final = add_business_days(final_date, 1)
    cession_cost = float(projection["cession_cost"])
    performance_pct = float(projection["performance_fee_pct"]) / 100

    dc_previous = present_value
    dc_curve_previous = dc_value
    collection_previous = present_value
    selic_previous = present_value
    rows = []

    for _, source_row in df.iterrows():
        current = source_row["date"]
        if not (
            is_business_day(current, PARAMETRIZED_HOLIDAYS)
            or current in {advance_date, final_date, first_business_after_final}
        ):
            continue
        is_business_day_flag = is_business_day(current, PARAMETRIZED_HOLIDAYS)

        collection_opening = collection_previous
        if accrual_start_date <= current <= final_date and is_business_day_flag:
            collection_interest = min(collection_opening * daily_business_rate, max(dc_value - collection_opening, 0.0))
        else:
            collection_interest = 0.0
        radar = active_radar(current, radars)
        radar_value = radar.qmm_value if radar else 0.0
        qmm_value = float(source_row.get("qmm", 0.0))
        collection_closing = min(collection_opening + collection_interest, dc_value)
        economic_collection_curve = collection_closing if current <= final_date else dc_value
        collection_curve = min(max(economic_collection_curve, qmm_value), dc_value) if current <= final_date else dc_value

        opening_charges = collection_curve
        value_with_qmm = max(opening_charges, qmm_value)

        dc_opening = dc_previous
        if current >= accrual_start_date and is_business_day_flag:
            dc_interest = min(dc_opening * daily_business_rate, max(dc_value - dc_opening, 0.0))
            if current > final_date:
                dc_interest = dc_opening * daily_business_rate
        else:
            dc_interest = 0.0
        fine = dc_value * fine_pct + fine_fixed if current == first_business_after_final else 0.0
        late_interest = dc_opening * late_daily_rate if current > final_date else 0.0
        dc_closing = dc_opening + dc_interest + late_interest
        if current <= final_date:
            dc_closing = min(dc_closing, dc_value)
        dc_curve = dc_value if current <= final_date else dc_curve_previous + dc_interest + fine + late_interest
        post_maturity_value = collection_curve if current <= final_date else dc_curve

        benchmark_rate = float(source_row.get("benchmark_rate_annual", projection["benchmark_annual_rate"]))
        selic_opening = selic_previous
        if current >= accrual_start_date and is_business_day_flag:
            selic_accrual = selic_opening * ((1 + benchmark_rate) ** (1 / 252) - 1)
        else:
            selic_accrual = 0.0
        selic_closing = selic_opening + selic_accrual
        spread = (collection_curve if current <= final_date else dc_curve) - selic_closing
        cession_today = cession_cost if current == advance_date else 0.0
        performance_fee = max(spread, 0.0) * performance_pct
        fidc_base_curve = collection_curve if current <= final_date else dc_curve
        fidc_liquid_curve = fidc_base_curve - cession_today - performance_fee if current <= final_date else 0.0
        payment_flow = 0.0
        if current == advance_date:
            payment_flow = -fidc_liquid_curve
        elif current == final_date:
            payment_flow = fidc_liquid_curve

        rows.append(
            {
                "Data": current,
                "Abertura Encargos": opening_charges,
                "QMM": radar_value,
                "Valor Com QMM": value_with_qmm,
                "Abertura DC": dc_opening,
                "Acrual de Juros DC": dc_interest,
                "Multa": fine,
                "Juros moratórios": late_interest,
                "Valor Fechamento DC": dc_closing,
                "Curva DC": dc_curve,
                "Abertura Cobrança": collection_opening,
                "Acrual de Juros Cobrança": collection_interest,
                "Valor Fechamento Cobrança": collection_closing,
                "Curva Cobrança": collection_curve,
                "Valor a Receber": receivable_value,
                "Valor QMM": value_with_qmm,
                "Pós Vencimento": post_maturity_value,
                "Selic Hoje": benchmark_rate,
                "Selic Acumulada": selic_opening,
                "Acrual Selic": selic_accrual,
                "Fechamento Selic": selic_closing,
                "Spread": spread,
                "Custo de cessões realizadas ao FIDC": cession_today,
                "Fee de Performance (R$)": performance_fee,
                "Curva líquida FIDC": fidc_liquid_curve,
                "Fluxo de Pagamento 90º dias": payment_flow,
            }
        )

        dc_previous = dc_closing
        dc_curve_previous = dc_curve
        collection_previous = collection_closing
        selic_previous = selic_closing

    return pd.DataFrame(rows)


def format_daily_evolution_table(table: pd.DataFrame) -> pd.DataFrame:
    formatted = table.copy()
    formatted["Data"] = formatted["Data"].map(format_date_pt)
    pct_columns = {"Selic Hoje"}
    for column in pct_columns.intersection(formatted.columns):
        formatted[column] = formatted[column].apply(
            lambda value: "-" if value is None or pd.isna(value) else format_pct(float(value) * 100)
        )
    money_columns = [column for column in formatted.columns if column not in {"Data", *pct_columns}]
    for column in money_columns:
        formatted[column] = formatted[column].apply(
            lambda value: "-" if value is None or pd.isna(value) else format_brl(float(value))
        )
    return formatted


def build_projection(
    advance_date: date,
    hospital_payment_day: int,
    operation_mode: str,
    monthly_rate_pct: float,
    grace_days: int,
    dc_value: float,
    operational_variable_pct: float = 0.0,
    operational_fixed_cost: float = 0.0,
    operational_cost_allocation: str = "Diluído nas parcelas",
    benchmark_annual_pct: float = DEFAULT_BENCHMARK_ANNUAL_PCT,
    benchmark_mode: str = DEFAULT_BENCHMARK_MODE,
    benchmark_table: pd.DataFrame | None = None,
    cession_fee_pct: float = DEFAULT_CESSION_FEE_PCT,
    performance_fee_pct: float = DEFAULT_PERFORMANCE_FEE_PCT,
    receivable_value: float | None = None,
    advance_pct: float = 100.0,
    radar_business_days: int = 5,
    late_monthly_rate_pct: float = 0.0,
    late_fine_pct: float = 0.0,
    late_fine_fixed: float = 0.0,
    vp_sensitive_to_advance_date: bool = False,
    total_term_days: int | None = None,
    installment_count: int | None = None,
    installment_amount: float | None = None,
    pricing_policy: str = PRICING_POLICY_RATE,
    target_xirr_fund_annual_pct: float | None = None,
    accrual_start_delay_days: int = DEFAULT_ACCRUAL_START_DELAY_DAYS,
) -> dict[str, object]:
    if receivable_value is not None:
        dc_value = min(dc_value, calculate_credit_limit(receivable_value, advance_pct))
    accrual_start_date = calculate_accrual_start_date_from_delay(advance_date, accrual_start_delay_days)

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
        contractual_final_date = max(installment_dates)
    else:
        raise ValueError("Selecione um modo de definição da operação.")

    # Na versão de 90 dias fixos o DC é sempre distribuído automaticamente
    # entre os repasses elegíveis. Não há parametrização manual de parcelas.
    installment_amount = dc_value / calculated_installment_count

    last_liquidation_date = max(installment_dates)
    operation_limit_date = (
        advance_date + timedelta(days=total_term_days)
        if operation_mode == "Por prazo total" and total_term_days is not None
        else last_liquidation_date
    )
    # A data limite é o vencimento jurídico/econômico da operação. Os repasses
    # elegíveis são apenas marcos operacionais de liquidação antes desse limite.
    final_date = operation_limit_date
    grace_end = first_installment_cycle_date(advance_date, hospital_payment_day, grace_days)

    if pricing_policy == PRICING_POLICY_TARGET_XIRR:
        if target_xirr_fund_annual_pct is None:
            raise ValueError("Informe a XIRR alvo do fundo.")
        monthly_rate_pct = solve_monthly_rate_for_target_fund_xirr(
            target_xirr_fund_annual_pct / 100,
            advance_date=advance_date,
            hospital_payment_day=hospital_payment_day,
            operation_mode=operation_mode,
            grace_days=grace_days,
            dc_value=dc_value,
            operational_variable_pct=operational_variable_pct,
            operational_fixed_cost=operational_fixed_cost,
            operational_cost_allocation=operational_cost_allocation,
            benchmark_annual_pct=benchmark_annual_pct,
            benchmark_mode=benchmark_mode,
            benchmark_table=benchmark_table,
            cession_fee_pct=cession_fee_pct,
            performance_fee_pct=performance_fee_pct,
            receivable_value=receivable_value,
            advance_pct=advance_pct,
            radar_business_days=radar_business_days,
            late_monthly_rate_pct=late_monthly_rate_pct,
            late_fine_pct=late_fine_pct,
            late_fine_fixed=late_fine_fixed,
            vp_sensitive_to_advance_date=vp_sensitive_to_advance_date,
            total_term_days=total_term_days,
            installment_count=installment_count,
            installment_amount=installment_amount,
            accrual_start_delay_days=accrual_start_delay_days,
        )

    monthly_rate = monthly_rate_pct / 100
    annual_operation_rate = calcular_taxa_anual_equivalente(monthly_rate)
    operation_business_days = contar_dias_uteis(accrual_start_date, final_date, PARAMETRIZED_HOLIDAYS)
    vp_start_date, vp_end_date = obter_datas_base_vp(
        advance_date,
        accrual_start_date,
        final_date,
        vp_sensitive_to_advance_date,
    )
    vp_business_days = contar_dias_uteis(vp_start_date, vp_end_date, PARAMETRIZED_HOLIDAYS)
    financial_present_value, installments = calculate_present_value(
        advance_date,
        installment_dates,
        installment_amount,
        monthly_rate,
        accrual_start_date=accrual_start_date,
        final_date=final_date,
        dc_value=dc_value,
        holidays=PARAMETRIZED_HOLIDAYS,
        vp_start_date=vp_start_date,
    )
    cost_breakdown = calculate_anticipation_cost_breakdown(
        dc_value,
        financial_present_value,
        operational_variable_pct,
        operational_fixed_cost,
    )
    anticipation_monthly_rate_pct = calculate_monthly_anticipation_rate_pct(
        monthly_rate_pct,
        operational_variable_pct,
        operational_fixed_cost,
        dc_value,
    )
    present_value = cost_breakdown["net_disbursement"]
    if present_value <= 0:
        raise ValueError(
            "Os custos da operação tornam o valor líquido menor ou igual a zero. "
            "Reduza os custos operacionais ou a taxa de juros."
        )
    payment_dates = installment_dates
    radars = calculate_radar_windows(
        payment_dates,
        advance_date,
        final_date,
        present_value,
        dc_value,
        accrual_start_date,
        annual_operation_rate,
        radar_business_days,
    )
    post_maturity_end_date = add_business_days(final_date, 25)
    chart_end_date = max([post_maturity_end_date, *[radar.end_date for radar in radars]])
    dates = pd.date_range(advance_date, chart_end_date, freq="D")
    qmm_curve = build_qmm_curve(
        dates,
        advance_date,
        final_date,
        present_value,
        dc_value,
        accrual_start_date,
        radars,
    )
    collection_curve = build_collection_curve(dates, installments)
    df = qmm_curve.merge(collection_curve, on="date")
    fund_curves, fund_metrics = build_fund_economic_curves(
        dates,
        advance_date,
        accrual_start_date,
        final_date,
        present_value,
        dc_value,
        annual_operation_rate,
        benchmark_annual_pct / 100,
        cession_fee_pct,
        performance_fee_pct,
        benchmark_mode,
        benchmark_table,
        late_monthly_rate_pct / 100,
        late_fine_pct / 100,
        late_fine_fixed,
    )
    df = df.merge(fund_curves, on="date", how="left")
    df["curva_economica"] = df["cobranca_financeira"]
    df["qmm_radar_aplicavel"] = df["date"].apply(lambda value: radar_value_on_date(value, radars))
    df["cobranca_financeira"] = df[["curva_economica", "qmm"]].max(axis=1).clip(upper=dc_value)
    spread_base = df["cobranca_financeira"].where(df["date"] <= final_date, df["dc_economico"])
    df["spread_bruto"] = spread_base - df["benchmark"]
    df["fee_performance"] = df["spread_bruto"].clip(lower=0) * (performance_fee_pct / 100)
    cession_cost = float(fund_metrics["cession_cost"])
    df["curva_liquida_fidc"] = df["cobranca_financeira"] - cession_cost - df["fee_performance"]
    final_fund_row = df.loc[df["date"] == final_date].iloc[-1]
    fund_metrics.update(
        {
            "spread_bruto_final": float(final_fund_row["spread_bruto"]),
            "performance_fee_final": float(final_fund_row["fee_performance"]),
            "fidc_liquid_curve_final": float(final_fund_row["curva_liquida_fidc"]),
        }
    )
    df["qmm_ajustado"] = df["qmm"]
    df["dc"] = dc_value
    return {
        "df": df,
        "advance_date": advance_date,
        "present_value": present_value,
        "financial_present_value": financial_present_value,
        "operational_variable_pct": operational_variable_pct,
        "operational_fixed_cost_input": operational_fixed_cost,
        "operational_cost_allocation": operational_cost_allocation,
        "benchmark_annual_pct": benchmark_annual_pct,
        "benchmark_mode": benchmark_mode,
        "cession_fee_pct": cession_fee_pct,
        "performance_fee_pct": performance_fee_pct,
        "receivable_value": receivable_value if receivable_value is not None else dc_value,
        "advance_pct": advance_pct,
        "radar_business_days": radar_business_days,
        "grace_days": grace_days,
        "late_monthly_rate_pct": late_monthly_rate_pct,
        "late_fine_pct": late_fine_pct,
        "late_fine_fixed": late_fine_fixed,
        "vp_sensitive_to_advance_date": vp_sensitive_to_advance_date,
        "accrual_start_delay_days": accrual_start_delay_days,
        "vp_policy_label": "Baseado na data da antecipação"
        if vp_sensitive_to_advance_date
        else "Baseado no início do accrual",
        "vp_start_date": vp_start_date,
        "vp_end_date": vp_end_date,
        "vp_business_days": vp_business_days,
        "operation_business_days": operation_business_days,
        "parametrized_holidays": PARAMETRIZED_HOLIDAYS,
        "anticipation_monthly_rate_pct": anticipation_monthly_rate_pct,
        **cost_breakdown,
        **fund_metrics,
        "installments": installments,
        "payment_dates": payment_dates,
        "radars": radars,
        "final_date": final_date,
        "contractual_final_date": contractual_final_date,
        "last_liquidation_date": last_liquidation_date,
        "operation_limit_date": operation_limit_date,
        "input_total_term_days": input_total_term_days,
        "real_total_term_days": real_total_term_days,
        "operation_mode": operation_mode,
        "pricing_policy": pricing_policy,
        "target_xirr_fund_annual_pct": target_xirr_fund_annual_pct,
        "monthly_rate_pct": monthly_rate_pct,
        "calculated_installment_count": calculated_installment_count,
        "installment_amount": installment_amount,
        "chart_end_date": chart_end_date,
        "grace_end": grace_end,
        "accrual_start_date": accrual_start_date,
        "monthly_rate": monthly_rate,
    }


def apply_liquidation_to_projection(
    projection: dict[str, object],
    liquidation: dict[str, object],
    params: DelayParameters,
) -> dict[str, object]:
    df = projection["df"].copy()
    payment_dates = [payment_date for payment_date, _ in liquidation["payments"]]
    desired_end = max([params.analysis_date, projection["chart_end_date"], *payment_dates])
    if desired_end > projection["chart_end_date"]:
        dates = pd.date_range(projection["df"]["date"].min(), desired_end, freq="D")
        qmm_curve = build_qmm_curve(
            dates,
            projection["df"]["date"].min(),
            projection["final_date"],
            projection["present_value"],
            float(projection["df"]["dc"].iloc[0]),
            projection["accrual_start_date"],
            projection["radars"],
        )
        collection_curve = build_collection_curve(dates, projection["installments"])
        df = qmm_curve.merge(collection_curve, on="date")
        df["dc"] = float(projection["df"]["dc"].iloc[0])

    economic_columns = {
        "cobranca_financeira",
        "benchmark",
        "dc_economico",
        "spread_bruto",
        "cessao_fidc",
        "fee_performance",
        "curva_liquida_fidc",
    }
    if not economic_columns.issubset(df.columns):
        fund_curves, _ = build_fund_economic_curves(
            pd.DatetimeIndex(pd.to_datetime(df["date"])),
            projection["df"]["date"].min(),
            projection["accrual_start_date"],
            projection["final_date"],
            projection["present_value"],
            float(projection["df"]["dc"].iloc[0]),
            projection["annual_operation_rate"],
            projection["benchmark_annual_rate"],
            projection["cession_fee_pct"],
            projection["performance_fee_pct"],
            projection.get("benchmark_mode", "Simplificado"),
            None,
            float(projection.get("late_monthly_rate_pct", 0.0)) / 100,
            float(projection.get("late_fine_pct", 0.0)) / 100,
            float(projection.get("late_fine_fixed", 0.0)),
        )
        df = df.merge(fund_curves, on="date", how="left")

    df = df.drop(columns=["qmm_ajustado"], errors="ignore")
    saldo_curve = build_saldo_exigivel_curve(pd.DatetimeIndex(pd.to_datetime(df["date"])), liquidation["result_table"])
    df = df.merge(saldo_curve, on="date", how="left")
    df["saldo_exigivel_curve"] = df["saldo_exigivel_curve"].fillna(0.0)

    if params.adjusted_qmm_enabled:
        df["qmm_ajustado"] = (df["qmm"] - df["saldo_exigivel_curve"]).clip(lower=0)
    else:
        df["qmm_ajustado"] = df["qmm"]

    adjusted_projection = dict(projection)
    adjusted_projection["df"] = df
    adjusted_projection["liquidation"] = liquidation
    adjusted_projection["delay_params"] = params
    adjusted_projection["chart_end_date"] = desired_end
    return adjusted_projection


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


def add_chart_annotation(
    fig: go.Figure,
    text: str,
    x_value: date,
    y_value: float,
    color: str = "#475569",
    yref: str = "y",
) -> None:
    fig.add_annotation(
        x=x_value.isoformat(),
        y=y_value,
        xref="x",
        yref=yref,
        text=text,
        showarrow=False,
        font=dict(size=11, color=color),
        bgcolor="rgba(255,255,255,0.72)",
        bordercolor="rgba(148,163,184,0.35)",
        borderwidth=1,
        borderpad=4,
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
    accrual_start_date = projection["accrual_start_date"]
    present_value = projection["present_value"]
    final_date = projection["final_date"]
    chart_end_date = projection["chart_end_date"]
    fee_series = df["fee_performance"] if "fee_performance" in df else pd.Series([0.0] * len(df))
    fee_max = max(float(fee_series.max()), 1.0)
    fee_axis_max = fee_max * 5.0
    primary_columns = ["qmm", "qmm_ajustado", "cobranca_financeira", "benchmark", "dc_economico"]
    primary_min = float(df[primary_columns].min().min())
    receivable_value = float(projection.get("receivable_value", dc_value))
    primary_max = max(dc_value, receivable_value, float(df[primary_columns].max().max()))
    valor_a_receber = max(receivable_value, dc_value)
    df = df.copy()
    df["valor_a_receber"] = valor_a_receber

    fig = go.Figure()

    # The first traces are ordered to control legend sequence and filled areas.
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["dc_economico"],
            mode="lines",
            name="Base Transbordo",
            line=dict(color="rgba(0,0,0,0)", width=0),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["valor_a_receber"],
            mode="lines",
            name="Valor a Receber",
            line=dict(color="#6b7280", width=2),
            fill="tonexty",
            fillcolor="rgba(107, 114, 128, 0.10)",
            customdata=money_hover(df["valor_a_receber"]),
            hovertemplate="%{x|%d/%m/%Y}<br>Valor a receber: %{customdata}<extra></extra>",
        )
    )

    if chart_end_date > final_date:
        fig.add_vrect(
            x0=final_date.isoformat(),
            x1=chart_end_date.isoformat(),
            fillcolor="rgba(37, 99, 235, 0.08)",
            line_width=0,
            layer="below",
            annotation_text="Pós Vencimento",
            annotation_position="top left",
            annotation_font_size=11,
            annotation_font_color="#1d4ed8",
        )
        fig.add_trace(
            go.Scatter(
                x=[final_date, chart_end_date],
                y=[None, None],
                mode="lines",
                name="Pós Vencimento",
                line=dict(color="rgba(37, 99, 235, 0.35)", width=8),
                hoverinfo="skip",
            )
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=[final_date],
                y=[None],
                mode="lines",
                name="Pós Vencimento",
                line=dict(color="rgba(37, 99, 235, 0.35)", width=8),
                hoverinfo="skip",
            )
        )

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

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["qmm"],
            mode="lines",
            name="Valor QMM",
            line=dict(color=QMM_COLOR, width=4),
            customdata=money_hover(df["qmm"]),
            hovertemplate="%{x|%d/%m/%Y}<br>Valor QMM: %{customdata}<extra></extra>",
        )
    )
    if "delay_params" in projection and projection["delay_params"].adjusted_qmm_enabled:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["qmm_ajustado"],
                mode="lines",
                name="QMM Ajustado",
                line=dict(color="#7c3aed", width=3, dash="dash"),
                customdata=money_hover(df["qmm_ajustado"]),
                hovertemplate="%{x|%d/%m/%Y}<br>QMM ajustado: %{customdata}<extra></extra>",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["cobranca_financeira"],
            mode="lines",
            name="Curva Cobrança",
            line=dict(color="rgba(242, 140, 40, 0.78)", width=3, dash="dash"),
            customdata=money_hover(df["cobranca_financeira"]),
            hovertemplate="%{x|%d/%m/%Y}<br>Curva cobrança: %{customdata}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=fee_series,
            name="Fee de Performance (R$)",
            marker_color="rgba(30, 64, 175, 0.18)",
            marker_line_color="rgba(30, 64, 175, 0.28)",
            marker_line_width=0.35,
            opacity=0.75,
            yaxis="y2",
            customdata=money_hover(fee_series),
            hovertemplate="%{x|%d/%m/%Y}<br>Fee de performance: %{customdata}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["dc_economico"],
            mode="lines",
            name="Curva DC",
            line=dict(color=DC_COLOR, width=4),
            customdata=money_hover(df["dc_economico"]),
            hovertemplate="%{x|%d/%m/%Y}<br>Curva DC: %{customdata}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["benchmark"],
            mode="lines",
            name="Selic Acumulada",
            line=dict(color="#111111", width=2, dash="dot"),
            customdata=money_hover(df["benchmark"]),
            hovertemplate="%{x|%d/%m/%Y}<br>Selic acumulada: %{customdata}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["qmm"],
            mode="lines",
            name="Área visual do spread",
            line=dict(color="rgba(0,0,0,0)", width=0),
            fill="tonexty",
            fillcolor="rgba(220, 38, 38, 0.06)",
            hoverinfo="skip",
            showlegend=False,
        )
    )

    add_reference_line(fig, advance_date)
    add_reference_line(fig, grace_end)
    add_reference_line(fig, accrual_start_date, "#215e96")
    for item in installments:
        add_reference_line(fig, item.due_date, COBRANCA_COLOR)
    add_reference_line(fig, final_date, DC_COLOR)

    y_min = max(0, min(primary_min, present_value) * 0.94)
    y_max = valor_a_receber * 1.08
    mid_date = df["date"].iloc[len(df) // 2]
    transbordo_y = (valor_a_receber + max(float(df["dc_economico"].median()), 0)) / 2
    qmm_row = df.iloc[min(max(len(df) // 2, 0), len(df) - 1)]
    fee_row = df.iloc[int(fee_series.idxmax())] if fee_max > 1 else df.iloc[-1]
    add_chart_annotation(fig, "TRANSBORDO PARA O MÉDICO", mid_date, transbordo_y, "#4b5563")
    add_chart_annotation(fig, "QMM", qmm_row["date"], float(qmm_row["qmm"]), QMM_COLOR)
    if fee_max > 1:
        add_chart_annotation(fig, "FEE DE PERFORMANCE", fee_row["date"], fee_max * 1.08, "#1e40af", yref="y2")

    fig.update_layout(
        height=650,
        template="plotly_white",
        margin=dict(l=24, r=54, t=124, b=56),
        title=dict(
            text="Evolução econômica da operação<br><sup>Visão consolidada do ativo, benchmark, recuperação esperada e captura de valor do fundo</sup>",
            font=dict(size=20, color="#1f2937"),
            x=0.01,
            y=0.97,
            yanchor="top",
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=1.14,
            xanchor="left",
            x=0,
            font=dict(size=11),
        ),
        barmode="overlay",
        bargap=0,
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
            title="Valor econômico da operação",
            showgrid=True,
            gridcolor=GRID_COLOR,
            range=[y_min, y_max],
            tickprefix=BRL_PREFIX,
            separatethousands=True,
        ),
        yaxis2=dict(
            title=dict(text="Fee de Performance (R$)", font=dict(size=11, color="#64748b")),
            overlaying="y",
            side="right",
            showgrid=False,
            range=[0, fee_axis_max],
            tickprefix=BRL_PREFIX,
            separatethousands=True,
            tickfont=dict(size=10, color="#64748b"),
            zeroline=False,
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


def render_operation_summary(
    advance_date: date,
    dc_value: float,
    monthly_rate_pct: float,
    present_value: float,
    projection: dict[str, object],
) -> None:
    st.subheader("Resumo da operação")
    rows = [
        ("Data da antecipação", format_date_pt(advance_date)),
        ("Início do accrual QMM", format_date_pt(projection["accrual_start_date"])),
        ("Dias até início do accrual", f"{int(projection['accrual_start_delay_days'])} dias corridos"),
        ("Carência do primeiro repasse", f"{int(projection['grace_days'])} dias corridos"),
        ("Prazo limite da operação", f"{int(projection['input_total_term_days'])} dias"),
        ("Data limite / vencimento econômico", format_date_pt(projection["operation_limit_date"])),
        ("Prazo efetivo até liquidação", f"{int(projection['real_total_term_days'])} dias"),
        ("Última liquidação operacional prevista", format_date_pt(projection["last_liquidation_date"])),
        ("Valor bruto a receber", format_brl(float(projection["receivable_value"]))),
        ("Percentual antecipável", format_pct(float(projection["advance_pct"]))),
        ("Limite de crédito / DC", format_brl(dc_value)),
        ("VP creditado ao médico", format_brl(present_value)),
        ("Custo da antecipação", format_brl(float(projection["anticipation_cost"]))),
        ("Política de precificação", str(projection["pricing_policy"])),
        ("Política de cálculo do VP", str(projection["vp_policy_label"])),
        (
            "Taxa da operação",
            f"{format_pct(monthly_rate_pct)} a.m. | {format_pct(float(projection['annual_operation_rate']) * 100)} a.a.",
        ),
    ]
    for label, value in rows:
        st.markdown(f"<div class='info-row'><span>{label}</span><strong>{value}</strong></div>", unsafe_allow_html=True)


def render_liquidation_logic(projection: dict[str, object]) -> None:
    st.subheader("Lógica de liquidação")
    first_payment = projection["installments"][0].due_date if projection.get("installments") else projection["final_date"]
    bullets = [
        f"O primeiro repasse elegível ocorre em {format_date_pt(first_payment)}.",
        "Se o hospital não pagar no próximo repasse, a liquidação pode ocorrer nos repasses seguintes dentro do prazo.",
        "Se o repasse vier parcial, o sistema liquida o valor disponível e carrega o saldo para o próximo repasse elegível.",
        "O valor de referência para liquidação em cada repasse é o QMM vigente na data.",
    ]
    for item in bullets:
        st.caption(f"• {item}")


def render_fund_technical_notes(projection: dict[str, object]) -> None:
    st.subheader("Notas técnicas do fundo")
    benchmark_label = (
        f"{projection['benchmark_mode']} | {format_pct(float(projection['benchmark_annual_pct']))} a.a."
    )
    notes = [
        "A curva de cobrança representa o valor aplicável de cobrança, considerando o QMM quando houver radar ativo.",
        "O QMM funciona como piso econômico de referência nas janelas de radar.",
        "A Curva DC representa o saldo econômico/contratual e pode incorporar multa e mora após a data limite da operação.",
        "A data limite da operação é o vencimento jurídico/econômico usado no VP e na XIRR; a última liquidação prevista é apenas o último repasse operacional antes desse vencimento.",
        f"Benchmark Selic/CDI: {benchmark_label}.",
        f"XIRR bruta estimada: {format_optional_pct(projection.get('xirr_gross_annual'))} a.a.",
        f"XIRR líquida FIDC estimada: {format_optional_pct(projection.get('xirr_fund_annual'))} a.a.",
    ]
    for item in notes:
        st.caption(f"• {item}")


def render_calculation_details(projection: dict[str, object]) -> None:
    with st.expander("Detalhes de cálculo", expanded=False):
        vp_formula_base = (
            "DU(DataAntecipacao, DataVencimento)"
            if projection["vp_sensitive_to_advance_date"]
            else "DU(DataInicioAccrual, DataVencimento)"
        )
        st.markdown(
            f"""
            <div class="formula-box">
                <strong>Limite de crédito</strong><br>
                LimiteDeCredito = ValorBrutoReceber x PercentualAntecipavel
            </div>
            <div class="formula-box">
                <strong>Valor presente</strong><br>
                VP = VF / (1 + i_aa)^({vp_formula_base} / 252)
            </div>
            <div class="formula-box">
                <strong>QMM no radar</strong><br>
                QMM_radar = min(ValorFuturoProjetadoNoFimDaJanela, DC)
            </div>
            <div class="formula-box">
                <strong>Spread</strong><br>
                Spread = CurvaCobranca ou CurvaDC - Benchmark
            </div>
            <div class="formula-box">
                <strong>Cessão FIDC</strong><br>
                CessaoFIDC inicial = TaxaCessao x VP
            </div>
            <div class="formula-box">
                <strong>Fee de performance</strong><br>
                FeePerformance = Spread x PercentualPerformance
            </div>
            <div class="formula-box">
                <strong>XIRR</strong><br>
                soma(CF_i / (1 + r)^((d_i - d_0) / 365)) = 0
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            f"DU usado no VP: {int(projection['vp_business_days'])} dias úteis entre "
            f"{format_date_pt(projection['vp_start_date'])} e {format_date_pt(projection['vp_end_date'])}, "
            "excluindo sábados, domingos e feriados parametrizados."
        )
        if projection["pricing_policy"] == PRICING_POLICY_TARGET_XIRR:
            st.caption(
                "Precificação por XIRR alvo: a taxa mensal da antecipação é resolvida numericamente "
                f"para buscar XIRR líquida FIDC de {format_pct(float(projection['target_xirr_fund_annual_pct']))} a.a."
            )
        else:
            st.caption("Precificação por taxa: a taxa mensal é input e a XIRR é calculada como output.")
        if projection["vp_sensitive_to_advance_date"]:
            st.caption(
                "O VP é calculado a partir da data da antecipação; o custo financeiro reflete o período completo entre desembolso e vencimento."
            )
        else:
            st.caption(
                "O VP é calculado a partir do início do accrual; a data da antecipação só impacta o VP se alterar essa base ou o vencimento."
            )
        st.caption(
            f"Data limite / vencimento econômico usada no VP e na XIRR: {format_date_pt(projection['final_date'])}."
        )


def render_executive_simulation_notes(
    advance_date: date,
    dc_value: float,
    monthly_rate_pct: float,
    present_value: float,
    projection: dict[str, object],
) -> None:
    render_operation_summary(advance_date, dc_value, monthly_rate_pct, present_value, projection)
    st.divider()
    render_liquidation_logic(projection)
    st.divider()
    render_fund_technical_notes(projection)
    st.divider()
    render_calculation_details(projection)


def build_executive_milestones(advance_date: date, projection: dict[str, object]) -> pd.DataFrame:
    installments = projection.get("installments", [])
    first_payment = installments[0].due_date if installments else projection["final_date"]
    first_post_maturity = add_business_days(projection["final_date"], 1)
    rows = [
        {
            "Data": format_date_pt(advance_date),
            "Marco": "Antecipação",
            "Comentário": "Crédito do VP ao médico e início da exposição econômica.",
        },
        {
            "Data": format_date_pt(projection["accrual_start_date"]),
            "Marco": "Início do accrual QMM",
            "Comentário": "Data a partir da qual a curva econômica passa a apropriar juros.",
        },
        {
            "Data": format_date_pt(projection["vp_start_date"]),
            "Marco": "Base do VP",
            "Comentário": f"Política de cálculo do VP: {projection['vp_policy_label']}.",
        },
        {
            "Data": format_date_pt(first_payment),
            "Marco": "Primeiro repasse elegível",
            "Comentário": "Primeira possibilidade de liquidação pelo pagamento do hospital.",
        },
        {
            "Data": format_date_pt(projection["final_date"]),
            "Marco": "Vencimento econômico",
            "Comentário": "Data limite jurídica/econômica da operação, usada no VP e na XIRR.",
        },
        {
            "Data": format_date_pt(projection["last_liquidation_date"]),
            "Marco": "Última liquidação operacional prevista",
            "Comentário": "Último repasse hospitalar elegível antes da data limite da operação.",
        },
        {
            "Data": format_date_pt(first_post_maturity),
            "Marco": "Pós-vencimento",
            "Comentário": "A Curva DC passa a refletir os encargos de atraso configurados.",
        },
    ]
    return pd.DataFrame(rows)


def render_assumptions(
    advance_date: date,
    hospital_payment_day: int,
    dc_value: float,
    grace_days: int,
    monthly_rate_pct: float,
    present_value: float,
    projection: dict[str, object],
) -> None:
    installment_count = int(projection["calculated_installment_count"])
    installment_amount = float(projection["installment_amount"])
    input_total_term_days = projection["input_total_term_days"]
    final_date = projection["final_date"]
    last_liquidation_date = projection["last_liquidation_date"]
    liquidation = projection.get("liquidation", {})

    st.subheader("Premissas")
    rows = [
        ("Data da antecipação", format_date_pt(advance_date)),
        ("Modelo da operação", "Prazo total"),
        ("Dia útil de remuneração do hospital", f"{hospital_payment_day}º dia útil"),
        ("Radar QMM", f"{int(projection['radar_business_days'])} dias úteis antes/depois"),
        ("Valor bruto a receber", format_brl(float(projection["receivable_value"]))),
        ("Percentual antecipável", format_pct(float(projection["advance_pct"]))),
        ("Limite de crédito calculado", format_brl(calculate_credit_limit(float(projection["receivable_value"]), float(projection["advance_pct"])))),
        ("DC / valor de face da operação", format_brl(dc_value)),
        ("Repasses elegíveis", str(installment_count)),
        ("Prazo limite da operação", f"{int(input_total_term_days)} dias corridos"),
        ("Data limite / vencimento econômico", format_date_pt(projection["operation_limit_date"])),
        ("Prazo efetivo até liquidação", f"{int(projection['real_total_term_days'])} dias corridos"),
        ("Última liquidação operacional prevista", format_date_pt(last_liquidation_date)),
        ("Carência do primeiro repasse", f"{int(projection['grace_days'])} dias corridos"),
        ("Dias até início do accrual", f"{int(projection['accrual_start_delay_days'])} dias corridos"),
        ("Início do accrual QMM", format_date_pt(projection["accrual_start_date"])),
        ("Dias úteis da operação", str(int(projection["operation_business_days"]))),
        ("Custo da antecipação", f"{format_pct(monthly_rate_pct)} ao mês"),
        ("Taxa econômica consolidada", f"{format_pct(float(projection['anticipation_monthly_rate_pct']))} ao mês"),
        ("Custo anual equivalente", format_pct(float(projection["annual_operation_rate"]) * 100)),
        ("VP financeiro", format_brl(float(projection["financial_present_value"]))),
        ("Custo da antecipação", format_brl(float(projection["anticipation_cost"]))),
        ("Valor líquido creditado", format_brl(present_value)),
        ("Taxa de antecipação total", f"{format_pct(float(projection['equivalent_operation_rate']) * 100)} da operação"),
        ("Benchmark Selic/CDI", f"{projection['benchmark_mode']} | {format_pct(float(projection['benchmark_annual_pct']))} ao ano"),
        ("Juros moratórios", f"{format_pct(float(projection['late_monthly_rate_pct']))} ao mês"),
        ("Multa percentual", format_pct(float(projection["late_fine_pct"]))),
        ("Multa fixa", format_brl(float(projection["late_fine_fixed"]))),
        ("Custo de cessão ao FIDC", format_brl(float(projection["cession_cost"]))),
        ("Fee de performance", f"{format_pct(float(projection['performance_fee_pct']))} do spread"),
        ("Curva líquida FIDC", format_brl(float(projection["fidc_liquid_curve_final"]))),
        ("XIRR bruta", f"{format_optional_pct(projection.get('xirr_gross_annual'))} a.a."),
        ("XIRR líquida FIDC", f"{format_optional_pct(projection.get('xirr_fund_annual'))} a.a."),
    ]
    period_holidays = holidays_between(projection["accrual_start_date"], final_date, PARAMETRIZED_HOLIDAYS)
    rows.append(
        (
            "Feriados no período",
            ", ".join(format_date_pt(item) for item in period_holidays) if period_holidays else "-",
        )
    )
    rows.insert(8, ("Marcos de liquidação calculados", str(installment_count)))
    if liquidation:
        rows.extend(
            [
                ("Atraso acumulado", format_brl(float(liquidation["overdue_total"]))),
                ("Mora acumulada", format_brl(float(liquidation["mora_total"]))),
                ("Saldo exigível", format_brl(float(liquidation["saldo_exigivel_total"]))),
            ]
        )

    for label, value in rows:
        st.markdown(f"<div class='info-row'><span>{label}</span><strong>{value}</strong></div>", unsafe_allow_html=True)
def render_parameters(
    installments: list[Installment],
    radars: list[RadarWindow],
    present_value: float,
    projection: dict[str, object],
) -> None:
    st.subheader("Parâmetros / Fórmulas")
    st.markdown(
        """
        <div class="formula-box">
            <strong>Limite de crédito</strong><br>
            Limite de crédito = Valor bruto a receber x percentual antecipável
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        f"Limite de crédito calculado: {format_brl(float(projection['receivable_value']))} x "
        f"{format_pct(float(projection['advance_pct']))} = {format_brl(float(projection['df']['dc'].iloc[0]))}."
    )
    st.caption("Nesta versão, DC máximo = limite de crédito calculado.")
    st.markdown(
        """
        <div class="formula-box">
            <strong>Valor presente</strong><br>
            VP = VF / (1 + i_aa)^(DU / 252)
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"**VP financeiro:** {format_brl(float(projection['financial_present_value']))}")
    st.caption("i_aa = (1 + i_m)^12 - 1.")
    st.caption(
        f"DU = {int(projection['operation_business_days'])} dias úteis entre "
        f"{format_date_pt(projection['accrual_start_date'])} e {format_date_pt(projection['final_date'])}, "
        "excluindo sábados, domingos e feriados parametrizados."
    )
    st.caption("Valor líquido creditado = VP financeiro calculado pela taxa econômica consolidada.")
    st.caption(f"Custo da antecipação = DC - VP = {format_brl_markdown(float(projection['anticipation_cost']))}.")
    st.caption(
        f"Início do accrual QMM: {format_date_pt(projection['accrual_start_date'])}. "
        "Se a antecipação ocorrer até o pagamento hospitalar do mês, usa esse pagamento; "
        "se ocorrer depois, usa a data da antecipação."
    )
    st.caption(
        f"Taxa de antecipação total = custo total / DC = {format_pct(float(projection['equivalent_operation_rate']) * 100)}."
    )
    st.markdown("**Fórmulas econômicas do fundo**")
    formula_rows = [
        "i_aa = (1 + i_m)^12 - 1",
        "Curva econômica: abertura x ((1 + i_a)^(DU / 252)) até o DC",
        "Curva de cobrança = max(curva econômica, QMM de radar)",
        "QMM no radar = min(valor futuro projetado no fim da janela, DC)",
        "Valor com QMM = max(curva econômica, QMM)",
        "Curva DC = saldo econômico contratual; no pós-vencimento pode incorporar multa e mora",
        "Benchmark simplificado: Benchmark_t = Benchmark_(t-1) x (1 + i_a,bench)^(1/252)",
        "Benchmark avançado: usa a taxa informada por data e carrega a última taxa disponível nos dias úteis seguintes",
        "Spread = curva de cobrança ou curva DC - benchmark",
        "Cessão FIDC inicial = taxa de cessão x VP",
        "Fee de performance = spread x percentual de performance",
        "Curva líquida FIDC = curva de cobrança - custo inicial de cessão - fee de performance",
        "XIRR: soma(CF_i / (1 + r)^((d_i - d_0) / 365)) = 0",
        "XIRR bruta: saída no VP creditado e entrada no DC na data limite / vencimento econômico",
        "XIRR líquida: saída inicial no VP + cessão FIDC e entrada na curva líquida estimada",
    ]
    for formula in formula_rows:
        st.caption(formula)
    st.markdown(f"**Valor líquido creditado:** {format_brl(present_value)}")

    st.caption(
        "Regra do modelo: o prazo total da operação limita os ciclos mensais do hospital; "
        f"a quantidade calculada é {projection['calculated_installment_count']} repasses elegíveis."
    )
    st.caption(
        f"Data limite / vencimento econômico: {format_date_pt(projection['operation_limit_date'])}. "
        f"Última liquidação operacional prevista: {format_date_pt(projection['last_liquidation_date'])}. "
        f"Prazo efetivo até liquidação: {int(projection['real_total_term_days'])} dias."
    )

    st.markdown("**Repasses elegíveis / marcos de liquidação**")
    st.caption("A primeira liquidação elegível ocorre no primeiro pagamento hospitalar em ou após a carência configurada; as demais seguem mensalmente.")
    for item in installments:
        st.caption(
            f"Repasse {item.number}: {format_date_pt(item.due_date)} | "
            f"{item.days_from_advance} dias | VP {format_brl(item.present_value)}"
        )

    st.markdown("**Janelas de radar**")
    for radar in radars:
        st.caption(
            f"{radar.month_label}: {format_date_pt(radar.start_date)} a "
            f"{format_date_pt(radar.end_date)} | QMM {format_brl(radar.qmm_value)}"
        )
    st.info("No primeiro dia do radar, o QMM assume o valor futuro projetado até o fim da janela e fica limitado ao DC.")
    if "delay_params" in projection:
        params = projection["delay_params"]
        st.markdown("**Atraso / Mora**")
        st.caption(f"Mora: {format_pct(params.monthly_late_rate * 100)} ao mês, calculada por juros simples diários.")
        st.caption("Saldo exigível = atraso acumulado + mora + multa.")
        if params.adjusted_qmm_enabled:
            st.caption("QMM ajustado = QMM referência - saldo exigível em aberto.")


def render_concepts_panel() -> None:
    st.subheader("Conceitos")
    concepts = [
        ("Valor presente", "valor econômico creditado hoje, descontando os fluxos futuros."),
        ("DC / Valor de Face", "valor nominal do direito creditório cedido; nesta versão, coincide com o limite de crédito calculado."),
        ("Curva de cobrança", "valor aplicável de cobrança; durante radar, considera o QMM projetado."),
        ("QMM", "piso econômico de referência, especialmente relevante nas janelas de radar."),
        ("Curva DC", "saldo econômico/contratual; no pós-vencimento pode incorporar multa e mora."),
        ("Benchmark", "Selic/CDI acumulada usada como referência econômica."),
        ("Spread", "ganho da operação acima do benchmark."),
        ("Cessão FIDC", "custo inicial de cessão calculado sobre o VP."),
        ("Fee de performance", "captura de parte do spread positivo pelo fundo."),
        ("XIRR/TIRR", "retorno implícito calculado com datas reais dos fluxos de caixa."),
    ]
    for label, description in concepts:
        st.caption(f"**{label}:** {description}")


def build_timeline_comments(
    advance_date: date,
    grace_end: date,
    installments: list[Installment],
    radars: list[RadarWindow],
    projection: dict[str, object] | None = None,
    liquidation: dict[str, object] | None = None,
) -> pd.DataFrame:
    qmm_breakdown = build_qmm_collection_breakdown(installments, projection)
    accrual_start_date = projection.get("accrual_start_date") if projection else None
    rows = [
        {
            "Data": format_date_pt(advance_date),
            "Marco": "Antecipação",
            "Comentário": "Crédito do valor presente ao médico.",
        },
        {
            "Data": format_date_pt(grace_end),
            "Marco": "Primeiro pagamento elegível",
            "Comentário": "A carência operacional define o primeiro pagamento hospitalar elegível para desconto e radar.",
        },
    ]
    if accrual_start_date:
        rows.append(
            {
                "Data": format_date_pt(accrual_start_date),
                "Marco": "Início do accrual QMM",
                "Comentário": (
                    "Data calculada pela quantidade de dias corridos configurada após a antecipação; "
                    "a partir dela o QMM passa a crescer até os radares."
                ),
            }
        )
    for radar in radars:
        rows.append(
            {
                "Data": f"{format_date_pt(radar.start_date)} a {format_date_pt(radar.end_date)}",
                "Marco": f"Radar {radar.month_label}",
                "Comentário": f"QMM flat em {format_brl(radar.qmm_value)} durante a janela.",
            }
        )
    for item in installments:
        breakdown = qmm_breakdown.get(item.number)
        if breakdown:
            principal_amount = breakdown["principal"]
            interest_and_cost = breakdown["interest_and_cost"]
            financial_interest = breakdown["financial_interest"]
            operational_cost = breakdown["operational_cost"]
            qmm_reference = breakdown["qmm_due"]
        else:
            principal_amount = item.present_value
            interest_and_cost = item.amount - principal_amount
            financial_interest = interest_and_cost
            operational_cost = 0.0
            qmm_reference = item.amount
        payment_comment = (
            f"Cobrança acumulada sobe em {format_brl(item.amount)}: "
            f"principal {format_brl(principal_amount)}; "
            f"custo econômico da antecipação {format_brl(interest_and_cost)} "
            f"QMM de referência {format_brl(qmm_reference)})."
        )
        if liquidation:
            table = liquidation["result_table"]
            row = table.loc[table["Parcela"] == item.number]
            if not row.empty:
                status = str(row.iloc[0]["Status"])
                paid = float(row.iloc[0]["Valor pago"])
                overdue = float(row.iloc[0]["Saldo em atraso"])
                mora = float(row.iloc[0]["Mora"])
                payment_comment = (
                    f"Previsto: principal {format_brl(principal_amount)}; "
                    f"custo econômico da antecipação {format_brl(interest_and_cost)}; "
                    f"QMM de referência {format_brl(qmm_reference)}). "
                    f"{status}: pago {format_brl(paid)}; "
                    f"atraso acumulado {format_brl(overdue)}; mora {format_brl(mora)}."
                )
        rows.append(
            {
                "Data": format_date_pt(item.due_date),
                "Marco": f"Repasse elegível {item.number}",
                "Comentário": payment_comment,
            }
        )
    return pd.DataFrame(rows)


def build_fund_economic_comments(projection: dict[str, object]) -> pd.DataFrame:
    rows = [
        {
            "Tema": "Curva de cobrança",
            "Comentário": "Representa o valor aplicável de cobrança; durante radar, considera o QMM projetado.",
        },
        {
            "Tema": "QMM",
            "Comentário": "Funciona como piso econômico de referência, especialmente durante as janelas de radar.",
        },
        {
            "Tema": "Curva DC",
            "Comentário": "Representa o saldo econômico/contratual da operação; no pós-vencimento pode incorporar juros, multa e mora.",
        },
        {
            "Tema": "Benchmark",
            "Comentário": f"Selic/CDI acumulada usada como referência econômica no modo {projection['benchmark_mode']}.",
        },
        {
            "Tema": "Spread",
            "Comentário": "Mede o ganho econômico da operação acima do benchmark.",
        },
        {
            "Tema": "FIDC",
            "Comentário": "O custo inicial de cessão e a fee de performance reduzem a curva líquida estimada do fundo.",
        },
        {
            "Tema": "XIRR / TIRR",
            "Comentário": (
                f"Retorno calculado com datas reais. XIRR bruta: {format_optional_pct(projection.get('xirr_gross_annual'))} a.a.; "
                f"XIRR líquida FIDC: {format_optional_pct(projection.get('xirr_fund_annual'))} a.a."
            ),
        },
    ]
    return pd.DataFrame(rows)


def render_timeline_comments(timeline: pd.DataFrame) -> None:
    for _, row in timeline.iterrows():
        label = row["Marco"] if "Marco" in timeline.columns else row["Tema"]
        description = row["Comentário"]
        date_text = row["Data"] if "Data" in timeline.columns else "Fundo"
        st.markdown(
            f"""
            <div class="timeline-item">
                <div class="timeline-date">{date_text}</div>
                <div class="timeline-content">
                    <strong>{label}</strong>
                    <span>{description}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def qmm_value_on_date(projection: dict[str, object], target_date: date) -> float:
    df = projection["df"]
    row = df.loc[df["date"] == target_date]
    if not row.empty:
        return float(row.iloc[0]["qmm"])
    previous = df.loc[df["date"] <= target_date]
    if not previous.empty:
        return float(previous.iloc[-1]["qmm"])
    return float(projection["present_value"])


def build_qmm_collection_breakdown(
    installments: list[Installment],
    projection: dict[str, object] | None,
) -> dict[int, dict[str, float]]:
    if not projection:
        return {}

    previous_qmm = float(projection["present_value"])
    breakdown: dict[int, dict[str, float]] = {}
    for item in installments:
        qmm_at_due = qmm_value_on_date(projection, item.due_date)
        qmm_increment = max(qmm_at_due - previous_qmm, 0)
        interest_and_cost = min(qmm_increment, item.amount)
        principal_amount = max(item.amount - interest_and_cost, 0)
        breakdown[item.number] = {
            "qmm_start": previous_qmm,
            "qmm_due": qmm_at_due,
            "principal": principal_amount,
            "interest_and_cost": interest_and_cost,
            "financial_interest": interest_and_cost,
            "operational_cost": 0.0,
        }
        previous_qmm = qmm_at_due

    return breakdown


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
            padding: 12px 14px;
            background: #ffffff;
            height: 104px;
            box-shadow: 0 6px 20px rgba(31, 41, 55, 0.05);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            overflow: hidden;
        }
        .metric-card span {
            display: block;
            color: #64748b;
            font-size: 0.74rem;
            font-weight: 700;
            text-transform: uppercase;
            line-height: 1.15;
            min-height: 1.7rem;
        }
        .metric-card strong {
            display: block;
            color: #172033;
            font-size: 1.08rem;
            line-height: 1.2;
            white-space: nowrap;
        }
        .metric-card small {
            color: #64748b;
            font-size: 0.76rem;
            line-height: 1.15;
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
        .doctor-shell {
            display: block;
            max-width: 1080px;
            margin: 0 auto;
            align-items: start;
            padding: 0 0 28px;
            margin-top: -0.55rem;
        }
        .doctor-page-title {
            margin-bottom: 0.35rem;
        }
        .doctor-page-title h1 {
            margin-bottom: 0.2rem;
        }
        .doctor-page-title p {
            margin-top: 0;
            margin-bottom: 0.65rem;
            color: #64748b;
            font-size: 0.98rem;
        }
        .doctor-card {
            border: 0;
            border-radius: 0;
            padding: 0;
            background: transparent;
            box-shadow: none;
        }
        .doctor-limit {
            background: #f4f8fd;
            border: 1px solid #edf3fb;
            border-radius: 8px;
            padding: 13px 14px;
            color: #4b5563;
            font-size: 0.9rem;
            margin: 0 0 16px;
        }
        .doctor-limit strong {
            display: block;
            color: #172033;
            font-size: 1.2rem;
            line-height: 1.2;
            margin: 2px 0;
        }
        .doctor-limit small {
            display: block;
            color: #64748b;
            font-size: 0.78rem;
            line-height: 1.25;
        }
        .doctor-limit span {
            display: block;
            color: #64748b;
            font-size: 0.78rem;
            margin-top: 2px;
        }
        .doctor-question-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            margin: 6px 0 4px;
            flex-wrap: wrap;
        }
        .doctor-question-row strong {
            color: #172033;
            font-size: 0.92rem;
            line-height: 1.18;
            flex: 1 1 170px;
        }
        .doctor-question-row span {
            color: #1680e5;
            font-size: 1.22rem;
            font-weight: 800;
            line-height: 1.15;
            white-space: nowrap;
            margin-left: auto;
        }
        .doctor-slider-caption {
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: #8a95a7;
            font-size: 0.82rem;
            margin: -6px 0 14px;
        }
        .doctor-slider-caption strong {
            color: #1680e5;
            font-size: 1.0rem;
            font-weight: 800;
            white-space: nowrap;
        }
        .doctor-section {
            border-top: 1px solid #edf2f7;
            padding-top: 14px;
            margin-top: 14px;
        }
        .doctor-date-pill {
            display: inline-flex;
            border: 1px solid #dce5ef;
            border-radius: 7px;
            padding: 8px 12px;
            margin: 4px 0 0;
            color: #1f7ae0;
            font-weight: 700;
            background: #ffffff;
        }
        .doctor-result {
            border-top: 1px solid #e8edf3;
            padding-top: 16px;
            margin-top: 16px;
        }
        .doctor-result span {
            color: #172033;
            font-weight: 700;
        }
        .doctor-result strong {
            display: block;
            color: #1680e5;
            font-size: 1.72rem;
            line-height: 1.1;
            margin-top: 6px;
        }
        .doctor-summary {
            margin: 10px 0 14px;
            color: #5d6b82;
            font-size: 0.91rem;
        }
        .doctor-summary div {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            padding: 3px 0;
        }
        .doctor-summary strong {
            color: #172033;
        }
        .doctor-next-payment {
            border: 1px solid #bfdbfe;
            border-radius: 10px;
            background: #eff6ff;
            padding: 18px 16px;
            margin: 14px 0 12px;
            box-shadow: 0 8px 22px rgba(22, 128, 229, 0.10);
        }
        .doctor-next-payment span {
            display: block;
            color: #1f4f86;
            font-size: 0.86rem;
            font-weight: 800;
            margin-bottom: 8px;
        }
        .doctor-next-payment strong {
            display: block;
            color: #0f6fca;
            font-size: 1.5rem;
            line-height: 1.18;
        }
        .doctor-next-payment small {
            display: block;
            color: #526176;
            font-size: 0.78rem;
            margin-top: 8px;
            line-height: 1.3;
        }
        .doctor-secondary-repasses {
            border-top: 1px solid #edf2f7;
            padding-top: 8px;
            margin-top: 6px;
        }
        .doctor-secondary-repasses p {
            color: #64748b;
            font-size: 0.82rem;
            line-height: 1.35;
            margin: 0 0 6px;
        }
        .doctor-secondary-repasses div {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            color: #526176;
            font-size: 0.84rem;
            padding: 3px 0;
        }
        .doctor-secondary-repasses strong {
            color: #172033;
            white-space: nowrap;
        }
        .doctor-partial-note {
            color: #64748b;
            font-size: 0.79rem;
            line-height: 1.35;
            margin: 10px 0 12px;
        }
        .doctor-trust-note {
            color: #526176;
            font-size: 0.84rem;
            font-weight: 700;
            margin: 8px 0 10px;
        }
        .doctor-internal-note {
            color: #94a3b8;
            font-size: 0.68rem;
            line-height: 1.25;
            margin: 6px 0 0;
        }
        .doctor-cost-config {
            border: 1px solid #edf2f7;
            border-radius: 8px;
            background: #ffffff;
            padding: 8px 10px;
            margin: 8px 0 6px;
        }
        .doctor-cost-config div {
            display: flex;
            justify-content: space-between;
            gap: 12px;
            padding: 3px 0;
            font-size: 0.82rem;
            color: #64748b;
            line-height: 1.2;
        }
        .doctor-cost-config strong {
            color: #172033;
            white-space: nowrap;
        }
        .version-link {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            min-height: 38px;
            border-radius: 8px;
            background: #1680e5;
            color: #ffffff !important;
            font-weight: 700;
            font-size: 0.88rem;
            text-decoration: none !important;
            margin: 6px 0 4px;
        }
        .version-link:hover {
            background: #0f6ec4;
            color: #ffffff !important;
            text-decoration: none !important;
        }
        .doctor-installment-row {
            display: flex;
            gap: 9px;
            color: #5d6b82;
            font-size: 0.94rem;
            padding: 2px 0;
        }
        .doctor-installment-row span::before {
            content: "•";
            margin-right: 8px;
            color: #64748b;
        }
        .doctor-installment-row strong {
            color: #172033;
        }
        .doctor-impact-panel {
            border: 0;
            border-radius: 0;
            padding: 2px 0 0;
            background: transparent;
            box-shadow: none;
        }
        .doctor-impact-panel h3 {
            margin-top: 0;
            margin-bottom: 6px;
            font-size: 0.86rem;
            line-height: 1.2;
        }
        .doctor-impact-panel p {
            color: #64748b;
            margin-top: 0;
            margin-bottom: 5px;
            font-size: 0.74rem;
            line-height: 1.28;
        }
        .doctor-impact-item {
            border-top: 0;
            padding: 3px 0;
            color: #64748b;
            font-size: 0.76rem;
            line-height: 1.32;
        }
        .timeline-item {
            display: grid;
            grid-template-columns: minmax(118px, 170px) 1fr;
            gap: 14px;
            border: 1px solid #e8edf3;
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 8px;
            background: #ffffff;
        }
        .timeline-date {
            color: #64748b;
            font-weight: 700;
            font-size: 0.84rem;
            line-height: 1.25;
        }
        .timeline-content strong {
            display: block;
            color: #172033;
            font-size: 0.88rem;
            margin-bottom: 3px;
        }
        .timeline-content span {
            display: block;
            color: #526176;
            font-size: 0.83rem;
            line-height: 1.35;
            white-space: normal;
            overflow-wrap: anywhere;
        }
        @media (max-width: 980px) {
            .doctor-shell {
                max-width: 100%;
            }
            .timeline-item {
                grid-template-columns: 1fr;
                gap: 4px;
            }
        }
        div[data-testid="stSlider"] {
            padding-top: 0;
        }
        div[data-testid="stSlider"] [data-baseweb="slider"] > div {
            color: #1f7ae0;
        }
        div[data-testid="stSlider"] [data-testid="stTickBar"],
        div[data-testid="stSlider"] [data-testid="stTickBarMin"],
        div[data-testid="stSlider"] [data-testid="stTickBarMax"],
        div[data-testid="stSlider"] [data-testid="stThumbValue"],
        div[data-testid="stSlider"] [data-testid="stSliderTickBarMin"],
        div[data-testid="stSlider"] [data-testid="stSliderTickBarMax"],
        div[data-testid="stSlider"] [data-testid="stSliderThumbValue"],
        div[data-testid="stSlider"] output,
        div[data-testid="stSlider"] [role="tooltip"] {
            display: none !important;
        }
        div[data-testid="stSlider"] [data-baseweb="slider"] div[style*="position: absolute"][style*="top"] {
            font-size: 0 !important;
            color: transparent !important;
        }
        div[data-testid="stButton"] button[kind="primary"],
        div[data-testid="stBaseButton-primary"] {
            background: #1680e5 !important;
            border-color: #1680e5 !important;
            color: #ffffff !important;
            border-radius: 7px !important;
            min-height: 46px;
            font-weight: 800;
            box-shadow: 0 8px 18px rgba(22, 128, 229, 0.22);
        }
        div[data-testid="stButton"] button[kind="primary"]:hover,
        div[data-testid="stBaseButton-primary"]:hover {
            background: #0f6fca !important;
            border-color: #0f6fca !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def calculate_doctor_offer(
    request_date: date,
    hospital_payment_day: int,
    monthly_rate_pct: float,
    operational_variable_pct: float,
    operational_fixed_cost: float,
    grace_days: int,
    requested_value: float,
    installment_count: int,
    total_term_days: int | None = None,
    vp_sensitive_to_advance_date: bool = False,
    accrual_start_delay_days: int = DEFAULT_ACCRUAL_START_DELAY_DAYS,
) -> dict[str, object]:
    installment_dates = calculate_installment_dates_by_count(
        advance_date=request_date,
        hospital_payment_day=hospital_payment_day,
        grace_days=grace_days,
        installment_count=installment_count,
    )
    installment_amount = requested_value / installment_count
    final_date = request_date + timedelta(days=total_term_days) if total_term_days is not None else max(installment_dates)
    accrual_start_date = calculate_accrual_start_date_from_delay(request_date, accrual_start_delay_days)
    financial_present_value, installments = calculate_present_value(
        request_date,
        installment_dates,
        installment_amount,
        monthly_rate_pct / 100,
        accrual_start_date=accrual_start_date,
        final_date=final_date,
        dc_value=requested_value,
        holidays=PARAMETRIZED_HOLIDAYS,
        vp_start_date=request_date if vp_sensitive_to_advance_date else accrual_start_date,
    )
    cost_breakdown = calculate_anticipation_cost_breakdown(
        requested_value,
        financial_present_value,
        operational_variable_pct,
        operational_fixed_cost,
    )
    anticipation_monthly_rate_pct = calculate_monthly_anticipation_rate_pct(
        monthly_rate_pct,
        operational_variable_pct,
        operational_fixed_cost,
        requested_value,
    )
    if cost_breakdown["net_disbursement"] <= 0:
        raise ValueError("Os custos da operação tornam o valor líquido menor ou igual a zero.")
    return {
        "request_date": request_date,
        "hospital_payment_day": hospital_payment_day,
        "monthly_rate_pct": monthly_rate_pct,
        "operational_variable_pct": operational_variable_pct,
        "operational_fixed_cost": operational_fixed_cost,
        "grace_days": grace_days,
        "requested_value": requested_value,
        "installment_count": installment_count,
        "installment_amount": installment_amount,
        "installments": installments,
        "present_value": cost_breakdown["net_disbursement"],
        "first_due_date": installment_dates[0],
        "anticipation_monthly_rate_pct": anticipation_monthly_rate_pct,
        **cost_breakdown,
    }


def calculate_gross_value_from_net_disbursement(
    net_disbursement: float,
    request_date: date,
    hospital_payment_day: int,
    installment_dates: list[date],
    monthly_rate_pct: float,
    operational_variable_pct: float,
    operational_fixed_cost: float,
    total_term_days: int | None = None,
    vp_sensitive_to_advance_date: bool = False,
    accrual_start_delay_days: int = DEFAULT_ACCRUAL_START_DELAY_DAYS,
) -> float:
    if net_disbursement <= 0:
        raise ValueError("Informe um valor líquido maior que zero.")

    monthly_rate = monthly_rate_pct / 100
    annual_rate = calcular_taxa_anual_equivalente(monthly_rate)
    final_date = request_date + timedelta(days=total_term_days) if total_term_days is not None else max(installment_dates)
    accrual_start_date = calculate_accrual_start_date_from_delay(request_date, accrual_start_delay_days)
    vp_start_date = request_date if vp_sensitive_to_advance_date else accrual_start_date
    business_days = contar_dias_uteis(vp_start_date, final_date, PARAMETRIZED_HOLIDAYS)
    discount_factor = 1 / ((1 + annual_rate) ** (business_days / 252))
    if discount_factor <= 0:
        raise ValueError(
            "Os custos da operação tornam a solicitação inviável. "
            "Reduza os custos ou aumente o prazo/parcelamento."
        )
    return net_disbursement / discount_factor


def calculate_doctor_offer_from_net(
    request_date: date,
    hospital_payment_day: int,
    monthly_rate_pct: float,
    operational_variable_pct: float,
    operational_fixed_cost: float,
    grace_days: int,
    desired_net_value: float,
    total_term_days: int = DOCTOR_FIXED_TERM_DAYS,
    vp_sensitive_to_advance_date: bool = False,
    accrual_start_delay_days: int = DEFAULT_ACCRUAL_START_DELAY_DAYS,
) -> dict[str, object]:
    installment_dates = calculate_installment_dates_by_term(
        advance_date=request_date,
        hospital_payment_day=hospital_payment_day,
        grace_days=grace_days,
        total_term_days=total_term_days,
    )
    requested_value = calculate_gross_value_from_net_disbursement(
        desired_net_value,
        request_date,
        hospital_payment_day,
        installment_dates,
        monthly_rate_pct,
        operational_variable_pct,
        operational_fixed_cost,
        total_term_days,
        vp_sensitive_to_advance_date,
        accrual_start_delay_days,
    )
    return calculate_doctor_offer(
        request_date=request_date,
        hospital_payment_day=hospital_payment_day,
        monthly_rate_pct=monthly_rate_pct,
        operational_variable_pct=operational_variable_pct,
        operational_fixed_cost=operational_fixed_cost,
        grace_days=grace_days,
        requested_value=requested_value,
        installment_count=len(installment_dates),
        total_term_days=total_term_days,
        vp_sensitive_to_advance_date=vp_sensitive_to_advance_date,
        accrual_start_delay_days=accrual_start_delay_days,
    )


def save_doctor_request_to_state(offer: dict[str, object], credit_limit: float) -> None:
    receivable_value = float(st.session_state.get("doctor_receivable_value", st.session_state.get("fund_receivable_value", offer["requested_value"])))
    advance_pct = float(st.session_state.get("doctor_advance_pct", st.session_state.get("fund_advance_pct", DEFAULT_ADVANCE_PCT)))
    credit_limit = calculate_credit_limit(receivable_value, advance_pct)
    st.session_state["doctor_credit_limit_value"] = float(credit_limit)
    st.session_state["doctor_request"] = {
        "request_date": offer["request_date"],
        "credit_limit": credit_limit,
        "requested_value": offer["requested_value"],
        "installment_count": offer["installment_count"],
        "installment_amount": offer["installment_amount"],
        "total_term_days": int(
            st.session_state.get("fund_accrual_start_delay_days", DEFAULT_ACCRUAL_START_DELAY_DAYS)
        )
        + DOCTOR_FIXED_TERM_DAYS,
        "hospital_payment_day": offer["hospital_payment_day"],
        "monthly_rate_pct": offer["monthly_rate_pct"],
        "pricing_policy": st.session_state.get("fund_pricing_policy", PRICING_POLICY_RATE),
        "target_xirr_fund_annual_pct": float(
            st.session_state.get("fund_target_xirr_fund_annual_pct", DEFAULT_TARGET_XIRR_FUND_ANNUAL_PCT)
        ),
        "operational_variable_pct": 0.0,
        "operational_fixed_cost": 0.0,
        "benchmark_annual_pct": st.session_state.get("fund_benchmark_annual_pct", DEFAULT_BENCHMARK_ANNUAL_PCT),
        "benchmark_mode": st.session_state.get("fund_benchmark_mode", DEFAULT_BENCHMARK_MODE),
        "cession_fee_pct": st.session_state.get("fund_cession_fee_pct", DEFAULT_CESSION_FEE_PCT),
        "performance_fee_pct": st.session_state.get("fund_performance_fee_pct", DEFAULT_PERFORMANCE_FEE_PCT),
        "receivable_value": receivable_value,
        "advance_pct": advance_pct,
        "radar_business_days": int(st.session_state.get("fund_radar_business_days", 5)),
        "late_monthly_rate_pct": float(st.session_state.get("fund_late_monthly_rate_pct", 1.0)),
        "late_fine_pct": float(st.session_state.get("fund_late_fine_pct", 2.0)),
        "late_fine_fixed": float(st.session_state.get("fund_late_fine_fixed", 0.0)),
        "vp_sensitive_to_advance_date": bool(st.session_state.get("fund_vp_sensitive_to_advance_date", False)),
        "accrual_start_delay_days": int(st.session_state.get("fund_accrual_start_delay_days", DEFAULT_ACCRUAL_START_DELAY_DAYS)),
        "grace_days": offer["grace_days"],
        "first_due_date": offer["first_due_date"],
        "present_value": offer["present_value"],
        "financial_present_value": offer["financial_present_value"],
        "financial_cost": offer["financial_cost"],
        "anticipation_cost": offer["anticipation_cost"],
        "anticipation_monthly_rate_pct": offer["anticipation_monthly_rate_pct"],
        "equivalent_operation_rate": offer["equivalent_operation_rate"],
    }
    st.session_state["doctor_request_pending_sync"] = True


def get_fund_defaults() -> dict[str, object]:
    request = st.session_state.get("doctor_request", {})
    receivable_default = float(request.get("receivable_value", st.session_state.get("fund_receivable_value", DEFAULT_RECEIVABLE_VALUE)))
    advance_pct_default = float(request.get("advance_pct", st.session_state.get("fund_advance_pct", DEFAULT_ADVANCE_PCT)))
    credit_limit = calculate_credit_limit(receivable_default, advance_pct_default)
    pricing_policy_default = st.session_state.get("fund_pricing_policy", request.get("pricing_policy", PRICING_POLICY_RATE))
    rate_state_key = "fund_effective_monthly_rate_pct" if pricing_policy_default == PRICING_POLICY_TARGET_XIRR else "fund_monthly_rate_pct"
    monthly_rate_default = float(st.session_state.get(rate_state_key, request.get("monthly_rate_pct", DEFAULT_MONTHLY_RATE_PCT)))
    target_xirr_default = float(
        st.session_state.get(
            "fund_target_xirr_fund_annual_pct",
            request.get("target_xirr_fund_annual_pct", DEFAULT_TARGET_XIRR_FUND_ANNUAL_PCT),
        )
    )
    accrual_start_delay_default = int(
        st.session_state.get(
            "fund_accrual_start_delay_days",
            request.get("accrual_start_delay_days", DEFAULT_ACCRUAL_START_DELAY_DAYS),
        )
    )
    total_term_default = accrual_start_delay_default + DOCTOR_FIXED_TERM_DAYS
    if request and st.session_state.get("doctor_request_pending_sync"):
        return {
            "advance_date": request.get("request_date", DEFAULT_ADVANCE_DATE),
            "hospital_payment_day": int(request.get("hospital_payment_day", DEFAULT_HOSPITAL_BUSINESS_DAY)),
            "installment_count": max(1, min(int(request.get("installment_count", 3)), 4)),
            "accrual_start_delay_days": accrual_start_delay_default,
            "total_term_days": total_term_default,
            "monthly_rate_pct": monthly_rate_default,
            "pricing_policy": pricing_policy_default,
            "target_xirr_fund_annual_pct": target_xirr_default,
            "operational_variable_pct": 0.0,
            "operational_fixed_cost": 0.0,
            "operational_cost_allocation": "Diluído nas parcelas",
            "benchmark_annual_pct": float(st.session_state.get("fund_benchmark_annual_pct", request.get("benchmark_annual_pct", DEFAULT_BENCHMARK_ANNUAL_PCT))),
            "benchmark_mode": st.session_state.get("fund_benchmark_mode", request.get("benchmark_mode", DEFAULT_BENCHMARK_MODE)),
            "cession_fee_pct": float(st.session_state.get("fund_cession_fee_pct", request.get("cession_fee_pct", DEFAULT_CESSION_FEE_PCT))),
            "performance_fee_pct": float(st.session_state.get("fund_performance_fee_pct", request.get("performance_fee_pct", DEFAULT_PERFORMANCE_FEE_PCT))),
            "grace_days": int(st.session_state.get("fund_grace_days", request.get("grace_days", DEFAULT_GRACE_DAYS))),
            "receivable_value": receivable_default,
            "advance_pct": advance_pct_default,
            "radar_business_days": int(st.session_state.get("fund_radar_business_days", request.get("radar_business_days", 5))),
            "late_monthly_rate_pct": float(st.session_state.get("fund_late_monthly_rate_pct", request.get("late_monthly_rate_pct", 1.0))),
            "late_fine_pct": float(st.session_state.get("fund_late_fine_pct", request.get("late_fine_pct", 2.0))),
            "late_fine_fixed": float(st.session_state.get("fund_late_fine_fixed", request.get("late_fine_fixed", 0.0))),
            "vp_sensitive_to_advance_date": bool(st.session_state.get("fund_vp_sensitive_to_advance_date", request.get("vp_sensitive_to_advance_date", False))),
            "dc_value": min(float(request.get("requested_value", credit_limit)), credit_limit),
            "credit_limit": credit_limit,
        }
    operation_mode = st.session_state.get("fund_operation_mode", "Por prazo total")
    if operation_mode == "Por prazo total":
        installment_count = st.session_state.get("fund_calculated_installment_count", request.get("installment_count", 3))
    else:
        installment_count = st.session_state.get("fund_installment_count", request.get("installment_count", 3))
    return {
        "advance_date": st.session_state.get("fund_advance_date", request.get("request_date", DEFAULT_ADVANCE_DATE)),
        "hospital_payment_day": int(st.session_state.get("fund_hospital_payment_day", request.get("hospital_payment_day", DEFAULT_HOSPITAL_BUSINESS_DAY))),
        "installment_count": max(1, min(int(installment_count), 4)),
        "accrual_start_delay_days": accrual_start_delay_default,
        "total_term_days": total_term_default,
        "monthly_rate_pct": monthly_rate_default,
        "pricing_policy": pricing_policy_default,
        "target_xirr_fund_annual_pct": target_xirr_default,
        "operational_variable_pct": 0.0,
        "operational_fixed_cost": 0.0,
        "operational_cost_allocation": "Diluído nas parcelas",
        "benchmark_annual_pct": float(st.session_state.get("fund_benchmark_annual_pct", request.get("benchmark_annual_pct", DEFAULT_BENCHMARK_ANNUAL_PCT))),
        "benchmark_mode": st.session_state.get("fund_benchmark_mode", request.get("benchmark_mode", DEFAULT_BENCHMARK_MODE)),
        "cession_fee_pct": float(st.session_state.get("fund_cession_fee_pct", request.get("cession_fee_pct", DEFAULT_CESSION_FEE_PCT))),
        "performance_fee_pct": float(st.session_state.get("fund_performance_fee_pct", request.get("performance_fee_pct", DEFAULT_PERFORMANCE_FEE_PCT))),
        "grace_days": int(st.session_state.get("fund_grace_days", request.get("grace_days", DEFAULT_GRACE_DAYS))),
        "receivable_value": float(st.session_state.get("fund_receivable_value", receivable_default)),
        "advance_pct": float(st.session_state.get("fund_advance_pct", advance_pct_default)),
        "radar_business_days": int(st.session_state.get("fund_radar_business_days", request.get("radar_business_days", 5))),
        "late_monthly_rate_pct": float(st.session_state.get("fund_late_monthly_rate_pct", request.get("late_monthly_rate_pct", 1.0))),
        "late_fine_pct": float(st.session_state.get("fund_late_fine_pct", request.get("late_fine_pct", 2.0))),
        "late_fine_fixed": float(st.session_state.get("fund_late_fine_fixed", request.get("late_fine_fixed", 0.0))),
        "vp_sensitive_to_advance_date": bool(st.session_state.get("fund_vp_sensitive_to_advance_date", request.get("vp_sensitive_to_advance_date", False))),
        "dc_value": min(float(st.session_state.get("fund_dc_value", request.get("requested_value", credit_limit))), calculate_credit_limit(float(st.session_state.get("fund_receivable_value", receivable_default)), float(st.session_state.get("fund_advance_pct", advance_pct_default)))),
        "credit_limit": calculate_credit_limit(float(st.session_state.get("fund_receivable_value", receivable_default)), float(st.session_state.get("fund_advance_pct", advance_pct_default))),
    }


def sync_fund_widget_state(defaults: dict[str, object]) -> None:
    if not st.session_state.get("doctor_request_pending_sync"):
        return
    st.session_state["fund_advance_date"] = defaults["advance_date"]
    st.session_state["fund_hospital_payment_day"] = defaults["hospital_payment_day"]
    st.session_state["fund_operation_mode"] = "Por prazo total"
    st.session_state["fund_installment_count"] = max(1, min(int(defaults["installment_count"]), 4))
    st.session_state["fund_monthly_rate_pct"] = defaults["monthly_rate_pct"]
    st.session_state["fund_pricing_policy"] = defaults["pricing_policy"]
    st.session_state["fund_target_xirr_fund_annual_pct"] = defaults["target_xirr_fund_annual_pct"]
    st.session_state["fund_accrual_start_delay_days"] = defaults["accrual_start_delay_days"]
    st.session_state["fund_total_term_days"] = defaults["total_term_days"]
    st.session_state["fund_benchmark_annual_pct"] = defaults["benchmark_annual_pct"]
    st.session_state["fund_benchmark_mode"] = defaults["benchmark_mode"]
    st.session_state["fund_cession_fee_pct"] = defaults["cession_fee_pct"]
    st.session_state["fund_performance_fee_pct"] = defaults["performance_fee_pct"]
    st.session_state["fund_grace_days"] = defaults["grace_days"]
    st.session_state["fund_receivable_value"] = defaults["receivable_value"]
    st.session_state["fund_advance_pct"] = defaults["advance_pct"]
    st.session_state["fund_radar_business_days"] = defaults["radar_business_days"]
    st.session_state["fund_late_monthly_rate_pct"] = defaults["late_monthly_rate_pct"]
    st.session_state["fund_late_fine_pct"] = defaults["late_fine_pct"]
    st.session_state["fund_late_fine_fixed"] = defaults["late_fine_fixed"]
    st.session_state["fund_vp_sensitive_to_advance_date"] = defaults["vp_sensitive_to_advance_date"]
    st.session_state["fund_dc_value"] = min(float(defaults["dc_value"]), float(defaults["credit_limit"]))
    st.session_state["doctor_receivable_value"] = defaults["receivable_value"]
    st.session_state["doctor_advance_pct"] = defaults["advance_pct"]
    st.session_state["doctor_credit_limit_value"] = defaults["credit_limit"]
    st.session_state["doctor_request_pending_sync"] = False


def sync_doctor_widget_state_from_fund(defaults: dict[str, object]) -> None:
    st.session_state["doctor_request_date"] = defaults["advance_date"]
    st.session_state["doctor_hospital_payment_day"] = defaults["hospital_payment_day"]
    st.session_state["doctor_grace_days"] = defaults["grace_days"]
    st.session_state["doctor_accrual_start_delay_days"] = defaults["accrual_start_delay_days"]
    st.session_state["doctor_monthly_rate_pct"] = defaults["monthly_rate_pct"]
    st.session_state["doctor_receivable_value"] = defaults["receivable_value"]
    st.session_state["doctor_advance_pct"] = defaults["advance_pct"]
    st.session_state["doctor_credit_limit_value"] = defaults["credit_limit"]


def max_total_term_for_doctor_limit(
    advance_date: date,
    hospital_payment_day: int,
    grace_days: int,
) -> int:
    installment_dates = calculate_installment_dates_by_count(
        advance_date=advance_date,
        hospital_payment_day=hospital_payment_day,
        grace_days=grace_days,
        installment_count=4,
    )
    return calculate_real_total_term(advance_date, installment_dates)


def render_doctor_installment_list(installments: list[Installment]) -> None:
    for item in installments:
        st.markdown(
            f"""
            <div class="doctor-installment-row">
                <span>{item.due_date.strftime("%d/%m")}</span>
                <strong>{format_brl(item.amount)}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )


def build_doctor_repasses_table(offer: dict[str, object], projection: dict[str, object]) -> pd.DataFrame:
    rows = []
    for index, item in enumerate(offer["installments"], start=1):
        rows.append(
            {
                "Repasse": f"M{index}",
                "Data": format_date_pt(item.due_date),
                "Desconto estimado": format_brl(qmm_value_on_date(projection, item.due_date)),
            }
        )
    return pd.DataFrame(rows)


def render_doctor_parameters(defaults: dict[str, object]) -> dict[str, object]:
    st.header("Parâmetros do médico")
    receivable_value = st.number_input(
        "Valor bruto a receber",
        min_value=0.0,
        value=float(st.session_state.get("doctor_receivable_value", defaults["receivable_value"])),
        step=1000.0,
        key="doctor_receivable_value",
    )
    advance_pct = st.number_input(
        "Percentual antecipável (%)",
        min_value=0.0,
        max_value=100.0,
        value=float(st.session_state.get("doctor_advance_pct", defaults["advance_pct"])),
        step=1.0,
        key="doctor_advance_pct",
    )
    credit_limit = calculate_credit_limit(float(receivable_value), float(advance_pct))
    st.session_state["doctor_credit_limit_value"] = float(credit_limit)
    st.metric("Limite de crédito calculado", format_brl(float(credit_limit)))
    request_date = st.date_input(
        "Data da antecipação",
        value=defaults["advance_date"],
        format="DD/MM/YYYY",
        key="doctor_request_date",
    )
    hospital_payment_day = st.number_input(
        "Dia útil de remuneração do hospital",
        min_value=1,
        max_value=31,
        value=int(defaults["hospital_payment_day"]),
        key="doctor_hospital_payment_day",
    )
    grace_days = int(defaults["grace_days"])
    accrual_start_delay_days = int(defaults["accrual_start_delay_days"])
    st.markdown("**Regra de carência**")
    st.caption(
        f"O primeiro repasse elegível ocorre no primeiro pagamento hospitalar em ou após "
        f"{grace_days} dias corridos da antecipação."
    )
    monthly_rate_pct = float(defaults["monthly_rate_pct"])
    operational_variable_pct = 0.0
    operational_fixed_cost = 0.0
    st.markdown("**Composição configurada pelo Fundo**")
    st.caption(
        "A oferta do médico usa a taxa econômica consolidada definida na Área do Fundo."
    )
    st.markdown(
        f"""
        <div class="doctor-cost-config">
            <div><span>Taxa de antecipação</span><strong>{format_pct(monthly_rate_pct)} a.m.</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Esses parâmetros alimentam a oferta do médico e, depois, a análise do fundo.")
    return {
        "credit_limit": float(credit_limit),
        "receivable_value": float(receivable_value),
        "advance_pct": float(advance_pct),
        "request_date": request_date,
        "hospital_payment_day": int(hospital_payment_day),
        "grace_days": grace_days,
        "accrual_start_delay_days": accrual_start_delay_days,
        "monthly_rate_pct": float(monthly_rate_pct),
        "operational_variable_pct": float(operational_variable_pct),
        "operational_fixed_cost": float(operational_fixed_cost),
    }


def render_doctor_app(defaults: dict[str, object], doctor_params: dict[str, object]) -> None:
    st.markdown('<div class="doctor-shell">', unsafe_allow_html=True)
    left_col, right_col = st.columns([0.72, 1.0], gap="medium")
    with left_col:
        st.markdown('<div class="doctor-card">', unsafe_allow_html=True)
        render_doctor_request_card(defaults, doctor_params)
        st.markdown("</div>", unsafe_allow_html=True)

    with right_col:
        render_doctor_fund_mapping()

    st.markdown("</div>", unsafe_allow_html=True)


def render_doctor_request_card(defaults: dict[str, object], doctor_params: dict[str, object]) -> None:
    credit_limit = float(doctor_params["credit_limit"])
    receivable_value = float(doctor_params["receivable_value"])
    advance_pct = float(doctor_params["advance_pct"])
    request_date = doctor_params["request_date"]
    hospital_payment_day = int(doctor_params["hospital_payment_day"])
    grace_days = int(doctor_params["grace_days"])
    accrual_start_delay_days = int(doctor_params["accrual_start_delay_days"])
    monthly_rate_pct = float(doctor_params["monthly_rate_pct"])
    operational_variable_pct = float(doctor_params["operational_variable_pct"])
    operational_fixed_cost = float(doctor_params["operational_fixed_cost"])
    operation_total_term_days = accrual_start_delay_days + DOCTOR_FIXED_TERM_DAYS

    if credit_limit < 1000:
        st.error("O limite de crédito disponível precisa ser de pelo menos R$ 1.000.")
        return

    try:
        eligible_dates = calculate_installment_dates_by_term(
            advance_date=request_date,
            hospital_payment_day=hospital_payment_day,
            grace_days=grace_days,
            total_term_days=operation_total_term_days,
        )
        max_offer = calculate_doctor_offer(
            request_date=request_date,
            hospital_payment_day=hospital_payment_day,
            monthly_rate_pct=monthly_rate_pct,
            operational_variable_pct=operational_variable_pct,
            operational_fixed_cost=operational_fixed_cost,
            grace_days=grace_days,
            requested_value=float(credit_limit),
            installment_count=len(eligible_dates),
            total_term_days=operation_total_term_days,
            vp_sensitive_to_advance_date=bool(defaults["vp_sensitive_to_advance_date"]),
            accrual_start_delay_days=accrual_start_delay_days,
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    max_net_value = max(float(max_offer["present_value"]), 0.0)
    min_net_value = min(1000.0, max_net_value)
    default_net_value = min(
        max(float(defaults.get("present_value", max_net_value)), min_net_value),
        max_net_value,
    )

    st.markdown(
        f"""
        <div class="doctor-limit">
            Limite disponível<br>
            <strong>{format_brl(float(credit_limit))}</strong>
            <small>Disponível para antecipação imediata</small>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "doctor_net_value" not in st.session_state:
        st.session_state["doctor_net_value"] = default_net_value
    st.session_state["doctor_net_value"] = min(max(float(st.session_state["doctor_net_value"]), min_net_value), max_net_value)
    st.session_state.setdefault("doctor_net_slider", st.session_state["doctor_net_value"])
    st.session_state.setdefault("doctor_net_input", st.session_state["doctor_net_value"])
    st.session_state["doctor_net_slider"] = min(max(float(st.session_state["doctor_net_slider"]), min_net_value), max_net_value)
    st.session_state["doctor_net_input"] = min(max(float(st.session_state["doctor_net_input"]), min_net_value), max_net_value)

    def sync_net_from_slider() -> None:
        st.session_state["doctor_net_value"] = float(st.session_state["doctor_net_slider"])

    st.markdown(
        f"""
        <div class="doctor-question-row">
            <strong>Quanto você quer receber hoje?</strong>
            <span>{format_brl(float(st.session_state["doctor_net_value"]))}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.slider(
        "Valor líquido desejado",
        min_value=float(min_net_value),
        max_value=float(max_net_value),
        value=float(st.session_state["doctor_net_value"]),
        step=100.0,
        key="doctor_net_slider",
        on_change=sync_net_from_slider,
        label_visibility="collapsed",
    )
    requested_net_value = float(st.session_state["doctor_net_value"])
    st.markdown(
        f"""
        <div class="doctor-slider-caption">
            <span>mín {format_brl(float(min_net_value))}</span>
            <span>máx {format_brl(float(max_net_value))}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        offer = calculate_doctor_offer_from_net(
            request_date=request_date,
            hospital_payment_day=hospital_payment_day,
            monthly_rate_pct=monthly_rate_pct,
            operational_variable_pct=operational_variable_pct,
            operational_fixed_cost=operational_fixed_cost,
            grace_days=grace_days,
            desired_net_value=float(requested_net_value),
            total_term_days=operation_total_term_days,
            vp_sensitive_to_advance_date=bool(defaults["vp_sensitive_to_advance_date"]),
            accrual_start_delay_days=accrual_start_delay_days,
        )
        doctor_projection = build_projection(
            advance_date=request_date,
            hospital_payment_day=hospital_payment_day,
            operation_mode="Por prazo total",
            monthly_rate_pct=monthly_rate_pct,
            operational_variable_pct=operational_variable_pct,
            operational_fixed_cost=operational_fixed_cost,
            total_term_days=operation_total_term_days,
            grace_days=grace_days,
            accrual_start_delay_days=accrual_start_delay_days,
            dc_value=float(offer["requested_value"]),
            benchmark_annual_pct=float(defaults["benchmark_annual_pct"]),
            benchmark_mode=str(defaults["benchmark_mode"]),
            benchmark_table=normalize_benchmark_table(st.session_state.get("fund_benchmark_table"))
            if str(defaults["benchmark_mode"]) == "Avançado"
            else None,
            cession_fee_pct=float(defaults["cession_fee_pct"]),
            performance_fee_pct=float(defaults["performance_fee_pct"]),
            receivable_value=receivable_value,
            advance_pct=advance_pct,
            radar_business_days=int(defaults["radar_business_days"]),
            late_monthly_rate_pct=float(defaults["late_monthly_rate_pct"]),
            late_fine_pct=float(defaults["late_fine_pct"]),
            late_fine_fixed=float(defaults["late_fine_fixed"]),
            vp_sensitive_to_advance_date=bool(defaults["vp_sensitive_to_advance_date"]),
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    save_doctor_request_to_state(offer, float(credit_limit))

    repasses = []
    for item in offer["installments"]:
        repasses.append(
            {
                "date": item.due_date,
                "discount": qmm_value_on_date(doctor_projection, item.due_date),
            }
        )
    next_repasse = repasses[0]
    following_repasses = repasses[1:]

    st.markdown(
        f"""
        <div class="doctor-next-payment">
            <span>No próximo repasse, o desconto estimado será:</span>
            <strong>{format_date_pt(next_repasse["date"])} · {format_brl(float(next_repasse["discount"]))}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if following_repasses:
        following_rows = "\n".join(
            f"<div><span>{format_date_pt(item['date'])}</span><strong>{format_brl(float(item['discount']))}</strong></div>"
            for item in following_repasses
        )
        st.markdown(
            f"""
            <div class="doctor-secondary-repasses">
                <p>Se não houver repasse nessa data, os próximos descontos serão:</p>
                {following_rows}
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown(
        """
        <p class="doctor-partial-note">
            Se o repasse vier parcial, descontamos o valor disponível e o restante segue para o próximo pagamento.
        </p>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<p class='doctor-trust-note'>Sem boleto. Sem cobrança manual.</p>", unsafe_allow_html=True)
    if st.button(f"Receber {format_brl(float(offer['present_value']))} agora", type="primary", use_container_width=True):
        st.session_state["pending_selected_area"] = "Aplicação do Fundo"
        st.session_state["_previous_area"] = "Aplicação do Médico"
        st.session_state["doctor_request_pending_sync"] = True
        st.rerun()


def render_doctor_fund_mapping() -> None:
    mapping_rows = [
        "Você escolhe quanto quer receber hoje.",
        "Mostramos o desconto estimado no próximo repasse.",
        "Se o hospital não pagar nesse repasse, usamos os próximos repasses elegíveis.",
        "Se o repasse vier parcial, liquidamos parte da antecipação e o restante segue para o próximo repasse.",
        "Sua solicitação também atualiza automaticamente a análise operacional e financeira do fundo.",
    ]
    st.markdown('<div class="doctor-impact-panel">', unsafe_allow_html=True)
    st.markdown("<h3>Entenda como funciona</h3>", unsafe_allow_html=True)
    for item in mapping_rows:
        st.markdown(
            f"<div class='doctor-impact-item'>• {item}</div>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
    render_doctor_api_notes()


def render_api_field_list(title: str, fields: list[str]) -> None:
    st.markdown(f"<strong>{title}</strong>", unsafe_allow_html=True)
    for field in fields:
        st.markdown(f"<div class='doctor-impact-item'>• {field}</div>", unsafe_allow_html=True)


def render_api_field_table(title: str, rows: list[tuple[str, str]]) -> None:
    st.markdown(f"<strong>{title}</strong>", unsafe_allow_html=True)
    for field, description in rows:
        st.markdown(
            f"<div class='doctor-impact-item'>• <strong>{field}</strong>: {description}</div>",
            unsafe_allow_html=True,
        )


def render_doctor_api_notes() -> None:
    st.markdown('<div class="doctor-impact-panel doctor-api-panel">', unsafe_allow_html=True)
    st.markdown("<h3>APIs de integração</h3>", unsafe_allow_html=True)
    st.caption("Campos conceituais para integrar a solicitação do médico com a análise operacional do fundo.")

    with st.expander("API 1 · Solicitação de antecipação", expanded=False):
        render_api_field_table(
            "Entrada",
            [
                ("id_hospital", "identificador do hospital/calendário operacional usado para calcular os repasses."),
                ("medico_cnpj", "identificador fiscal do médico ou da pessoa jurídica solicitante."),
                ("data_antecipacao", "data do pedido e do desembolso previsto ao médico."),
                (
                    "valor_antecipacao_solicitado",
                    "valor presente solicitado pelo médico; corresponde ao valor líquido a depositar hoje.",
                ),
                (
                    "taxa_antecipacao_contratada",
                    "taxa de antecipação efetivamente contratada para a cessão específica daquele médico/operação.",
                ),
                (
                    "datas_vencimento_previstas",
                    "lista dos repasses hospitalares elegíveis calculados pelo calendário do hospital.",
                ),
                (
                    "prazo_total_operacao",
                    "dias corridos entre a antecipação e a data limite da operação; no modelo atual = dias até accrual + 90.",
                ),
                (
                    "carencia_dias_inicio_accrual_juros",
                    "quantidade de dias corridos após a antecipação para iniciar accrual de juros/QMM.",
                ),
                (
                    "carencia_dias_inicio_radar_cobranca",
                    "quantidade de dias corridos usada para definir o primeiro repasse elegível e ativar o radar.",
                ),
            ],
        )
        render_api_field_table(
            "Retorno",
            [
                ("status", "resultado do processamento da solicitação, por exemplo aprovado, pendente ou rejeitado."),
                ("id_solicitacao", "identificador único da solicitação para rastreio entre Médico e Fundo."),
                ("mensagem_processamento", "descrição curta do resultado ou inconsistência encontrada."),
                (
                    "cenario_base_fundo_atualizado",
                    "indica se a solicitação foi gravada e sensibilizou a análise operacional do fundo.",
                ),
            ],
        )

    with st.expander("API 2 · Cálculo de valor presente e QMM", expanded=False):
        render_api_field_table(
            "Entrada",
            [
                ("id_hospital", "identificador do hospital para buscar a regra de pagamento e calendário operacional."),
                ("medico_cnpj", "identificador do médico usado para buscar limite, elegibilidade e políticas de crédito."),
                ("data_antecipacao", "data base para cálculo de prazo, VP, QMM e repasses elegíveis."),
                (
                    "carencia_dias_inicio_accrual_juros",
                    "dias corridos usados para calcular data_inicio_accrual = data_antecipacao + carência.",
                ),
                (
                    "carencia_dias_inicio_radar_cobranca",
                    "dias corridos usados para excluir repasses antes da carência e definir o primeiro radar elegível.",
                ),
                (
                    "valor_limite_credito_medico",
                    "limite máximo elegível para antecipação, calculado a partir do recebível e percentual antecipável.",
                ),
                (
                    "datas_vencimento_previstas",
                    "primeiro, segundo e terceiro repasses elegíveis dentro da data limite da operação.",
                ),
            ],
        )
        render_api_field_table(
            "Retorno",
            [
                (
                    "valor_presente_antecipacao",
                    "valor líquido a depositar ao médico, calculado pelo VP do DC conforme política da operação.",
                ),
                (
                    "valor_qmm_primeiro_repasse_elegivel",
                    "valor econômico de referência/QMM aplicável no primeiro repasse elegível.",
                ),
                (
                    "valor_qmm_segundo_repasse_elegivel",
                    "valor econômico de referência/QMM aplicável no segundo repasse elegível.",
                ),
                (
                    "valor_qmm_terceiro_repasse_elegivel",
                    "valor econômico de referência/QMM aplicável no terceiro repasse elegível.",
                ),
            ],
        )

    with st.expander("API 2.1 · Taxa mínima para rentabilidade", expanded=False):
        st.caption(
            "Alternativa simplificada à API 2. A FIN-X envia os parâmetros operacionais mínimos e a Integral retorna "
            "a taxa mínima de antecipação necessária para garantir a rentabilidade alvo da operação/fundo."
        )
        render_api_field_table(
            "Entrada",
            [
                ("id_hospital", "identificador do hospital usado para buscar calendário de pagamento, feriados e regra operacional."),
                (
                    "prazo_total_operacao",
                    "prazo jurídico/econômico total da operação em dias corridos, usado para definir a data limite/vencimento econômico.",
                ),
                (
                    "carencia_dias_inicio_accrual_juros",
                    "dias corridos após a antecipação para início do accrual de juros/QMM.",
                ),
                (
                    "carencia_dias_inicio_radar_cobranca",
                    "dias corridos após a antecipação para definir o primeiro repasse elegível e ativar radar/cobrança.",
                ),
            ],
        )
        render_api_field_table(
            "Retorno",
            [
                (
                    "taxa_antecipacao_minima",
                    "taxa mínima de antecipação que preserva a rentabilidade alvo definida pela Integral/Fundo.",
                ),
                ("mensagem_processamento", "descrição curta do resultado ou da inconsistência encontrada."),
            ],
        )

    with st.expander("API 3 · Extrato preliminar do lastro", expanded=False):
        st.caption("Integração para enviar ao fundo os recebíveis que compõem o lastro potencial da antecipação.")
        render_api_field_table(
            "Entrada",
            [
                ("id_hospital", "identificador do hospital responsável pelo repasse do recebível."),
                ("medico_cnpj", "CNPJ do médico ou da pessoa jurídica titular do recebível."),
                ("id_atendimento", "identificador único do atendimento que originou o recebível médico."),
                ("codigo_procedimento", "código do procedimento realizado, usado para rastreabilidade clínica/operacional."),
                ("valor_a_receber", "valor bruto do recebível associado ao atendimento/procedimento."),
                (
                    "valor_limite_antecipacao",
                    "valor máximo antecipável sobre o recebível, após aplicação da política de elegibilidade/haircut.",
                ),
            ],
        )
        render_api_field_table(
            "Retorno",
            [
                ("status", "indica se o PDF do extrato preliminar foi gerado com sucesso ou se houve falha."),
                ("mensagem_processamento", "descrição curta do sucesso ou do erro encontrado na geração do PDF."),
            ],
        )
    st.markdown("<strong>Premissas para a FIN-X calcular o QMM por repasse</strong>", unsafe_allow_html=True)
    qmm_premises = [
        "Usar a taxa de antecipação contratada para a cessão específica do médico.",
        "Usar a mesma data de antecipação, data de início do accrual e data limite/vencimento econômico.",
        "Usar o mesmo DC/valor de face da operação e aplicar cap do QMM no DC.",
        "Calcular as datas de repasse elegíveis pelo calendário do hospital, excluindo fins de semana e feriados parametrizados.",
        "Aplicar a janela de radar configurada, por exemplo 5 dias úteis antes e 5 dias úteis depois do repasse.",
        "Dentro do radar, calcular o QMM como o valor futuro projetado até o fim da janela do radar, limitado ao DC.",
        "Fora do radar, calcular o QMM pela curva econômica acumulada desde o início do accrual até a data de referência, limitado ao DC.",
    ]
    for item in qmm_premises:
        st.markdown(f"<div class='doctor-impact-item'>• {item}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_version_selector() -> None:
    st.markdown("**Versões da aplicação**")
    col_original, col_fixed, _ = st.columns([0.14, 0.18, 0.68])
    with col_original:
        st.page_link("app.py", label="Versão original", icon=":material/home:")
    with col_fixed:
        st.page_link("pages/90_Dias_Fixo.py", label="Versão 90 dias fixo", icon=":material/calendar_month:")


def main() -> None:
    inject_styles()

    defaults = get_fund_defaults()
    if "pending_selected_area" in st.session_state:
        st.session_state["selected_area"] = st.session_state.pop("pending_selected_area")
    with st.sidebar:
        selected_area = st.radio("Menu", ["Aplicação do Médico", "Aplicação do Fundo"], key="selected_area")

    if selected_area == "Aplicação do Médico":
        if st.session_state.get("_previous_area") == "Aplicação do Fundo":
            defaults = get_fund_defaults()
            sync_doctor_widget_state_from_fund(defaults)
        with st.sidebar:
            doctor_params = render_doctor_parameters(defaults)
        st.markdown(
            """
            <div class="doctor-page-title">
                <h1>Solicitação de antecipação</h1>
                <p>Escolha quanto deseja receber hoje e veja o desconto estimado nos próximos repasses.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        render_doctor_app(defaults, doctor_params)
        st.session_state["_previous_area"] = selected_area
        return

    sync_fund_widget_state(defaults)
    st.title("Simulação de Antecipação de Recebíveis Médicos")
    st.caption("Curvas executivas de QMM, cobrança e Direito Creditório com radar mensal calculado em dias úteis.")
    nav_col, _ = st.columns([0.28, 0.72])
    with nav_col:
        if st.button("← Solicitar antecipação", key="go_to_doctor_app", use_container_width=True):
            st.session_state["pending_selected_area"] = "Aplicação do Médico"
            st.session_state["_previous_area"] = "Aplicação do Fundo"
            st.rerun()

    with st.sidebar:
        st.header("Inputs operacionais")
        if st.session_state.get("doctor_request"):
            st.info("Parâmetros carregados da solicitação do médico. Você pode ajustar a análise abaixo.")
        advance_date = st.date_input(
            "Data da antecipação",
            value=defaults["advance_date"],
            format="DD/MM/YYYY",
            key="fund_advance_date",
        )
        hospital_payment_day = st.number_input(
            "Dia útil de remuneração do hospital",
            min_value=1,
            max_value=31,
            value=int(defaults["hospital_payment_day"]),
            key="fund_hospital_payment_day",
        )
        radar_business_days = st.number_input(
            "Dias úteis do radar QMM antes/depois do pagamento",
            min_value=1,
            max_value=15,
            value=int(defaults["radar_business_days"]),
            step=1,
            key="fund_radar_business_days",
        )
        grace_days = st.number_input(
            "Carência para primeiro repasse elegível (dias corridos)",
            min_value=0,
            max_value=180,
            value=int(defaults["grace_days"]),
            step=1,
            key="fund_grace_days",
        )
        accrual_start_delay_days = st.number_input(
            "Início do accrual após a antecipação (dias corridos)",
            min_value=0,
            max_value=180,
            value=int(defaults["accrual_start_delay_days"]),
            step=1,
            key="fund_accrual_start_delay_days",
        )
        operation_mode = "Por prazo total"
        total_term_days_input = int(accrual_start_delay_days) + DOCTOR_FIXED_TERM_DAYS
        st.caption(
            f"Prazo total da operação: {int(accrual_start_delay_days)} dias até o accrual "
            f"+ {DOCTOR_FIXED_TERM_DAYS} dias de accrual = {total_term_days_input} dias corridos."
        )
        installment_count_input = None
        operation_limit_date = advance_date + timedelta(days=int(total_term_days_input))
        operation_accrual_start_preview = calculate_accrual_start_date_from_delay(
            advance_date,
            int(accrual_start_delay_days),
        )
        st.caption(f"Data limite / vencimento econômico: {format_date_pt(operation_limit_date)}.")
        st.caption(f"Data de início do accrual: {format_date_pt(operation_accrual_start_preview)}.")
        vp_sensitive_to_advance_date = st.toggle(
            "VP sensível à data da antecipação",
            value=bool(defaults["vp_sensitive_to_advance_date"]),
            key="fund_vp_sensitive_to_advance_date",
        )
        if vp_sensitive_to_advance_date:
            st.caption(
                "O VP é calculado a partir da data da antecipação, refletindo o período completo entre desembolso e vencimento."
            )
        else:
            st.caption(
                "O VP é calculado a partir do início do accrual; a data da antecipação só altera o VP se mudar a duração econômica."
            )
        try:
            preview_dates = calculate_installment_dates_by_term(
                advance_date=advance_date,
                hospital_payment_day=int(hospital_payment_day),
                grace_days=int(grace_days),
                total_term_days=int(total_term_days_input),
            )
            st.caption(
                "Última liquidação operacional prevista pelo calendário do hospital: "
                f"{format_date_pt(max(preview_dates))}."
            )
        except ValueError:
            st.caption("Última liquidação operacional prevista: sem repasse elegível dentro do prazo informado.")

        st.header("Inputs econômicos da operação")
        receivable_value = st.number_input(
            "Valor bruto a receber",
            min_value=0.01,
            value=float(defaults["receivable_value"]),
            step=1000.0,
            key="fund_receivable_value",
        )
        advance_pct = st.number_input(
            "Percentual antecipável (%)",
            min_value=0.01,
            max_value=100.0,
            value=min(max(float(defaults["advance_pct"]), 0.01), 100.0),
            step=1.0,
            key="fund_advance_pct",
        )
        credit_limit = calculate_credit_limit(float(receivable_value), float(advance_pct))
        dc_value = min(float(defaults.get("dc_value", credit_limit)), credit_limit)
        st.metric("Limite de crédito calculado", format_brl(credit_limit))
        st.caption("Limite de crédito = valor bruto a receber x percentual antecipável. Neste modelo, DC máximo = limite de crédito.")
        st.metric("DC / valor de face da operação", format_brl(dc_value))
        pricing_policy = st.radio(
            "Política de precificação",
            [PRICING_POLICY_RATE, PRICING_POLICY_TARGET_XIRR],
            index=[PRICING_POLICY_RATE, PRICING_POLICY_TARGET_XIRR].index(str(defaults["pricing_policy"]))
            if str(defaults["pricing_policy"]) in [PRICING_POLICY_RATE, PRICING_POLICY_TARGET_XIRR]
            else 0,
            key="fund_pricing_policy",
        )
        if pricing_policy == PRICING_POLICY_RATE:
            monthly_rate_pct = st.number_input(
                "Custo da antecipação (% ao mês)",
                min_value=0.0,
                value=float(defaults["monthly_rate_pct"]),
                step=0.1,
                key="fund_monthly_rate_pct",
            )
            target_xirr_fund_annual_pct = float(defaults["target_xirr_fund_annual_pct"])
            st.caption("A taxa de antecipação é input; a XIRR do fundo é calculada como output.")
        else:
            target_xirr_fund_annual_pct = st.number_input(
                "XIRR alvo líquida do fundo (% a.a.)",
                min_value=0.0,
                value=float(defaults["target_xirr_fund_annual_pct"]),
                step=1.0,
                key="fund_target_xirr_fund_annual_pct",
            )
            monthly_rate_pct = float(defaults["monthly_rate_pct"])
            st.caption("A XIRR alvo é input; a taxa de antecipação é calculada para atingir esse retorno.")
        operational_variable_pct = 0.0
        operational_fixed_cost = 0.0
        operational_cost_allocation = "Diluído nas parcelas"
        st.caption("Taxa econômica consolidada usada para VP, QMM, cobrança financeira e custo da antecipação.")
        st.header("Inputs do fundo")
        benchmark_mode_options = ["Simplificado", "Avançado"]
        benchmark_mode = st.radio(
            "Benchmark Selic/CDI",
            options=benchmark_mode_options,
            index=benchmark_mode_options.index(str(defaults["benchmark_mode"]))
            if str(defaults["benchmark_mode"]) in benchmark_mode_options
            else 0,
            key="fund_benchmark_mode",
        )
        benchmark_annual_pct = st.number_input(
            "Taxa benchmark anual constante (%)",
            min_value=0.0,
            value=float(defaults["benchmark_annual_pct"]),
            step=0.25,
            key="fund_benchmark_annual_pct",
            disabled=benchmark_mode == "Avançado",
        )
        benchmark_table = None
        if benchmark_mode == "Avançado":
            benchmark_seed = normalize_benchmark_table(
                st.session_state.get("fund_benchmark_table", default_benchmark_table())
            )
            if benchmark_seed.empty:
                benchmark_seed = default_benchmark_table()
            benchmark_table = st.data_editor(
                benchmark_seed,
                column_config={
                    "data": st.column_config.DateColumn("data", format="DD/MM/YYYY"),
                    "taxa_benchmark": st.column_config.NumberColumn("taxa_benchmark", min_value=0.0, step=0.25),
                },
                num_rows="dynamic",
                key="fund_benchmark_table",
                hide_index=True,
            )
        cession_fee_pct = st.number_input(
            "Custo de cessão ao FIDC (% do VP)",
            min_value=0.0,
            value=float(defaults["cession_fee_pct"]),
            step=0.1,
            key="fund_cession_fee_pct",
        )
        performance_fee_pct = st.number_input(
            "Fee de performance (% do spread)",
            min_value=0.0,
            max_value=100.0,
            value=float(defaults["performance_fee_pct"]),
            step=1.0,
            key="fund_performance_fee_pct",
        )
        st.markdown("**Regra de carência**")
        st.caption(
            f"O primeiro repasse elegível é o primeiro pagamento hospitalar em ou após "
            f"{int(grace_days)} dias corridos da antecipação."
        )
        st.header("Inputs de pós-vencimento")
        late_monthly_rate_pct = st.number_input(
            "Juros moratórios (% ao mês)",
            min_value=0.0,
            value=float(defaults["late_monthly_rate_pct"]),
            step=0.1,
            key="fund_late_monthly_rate_pct",
        )
        late_fine_pct = st.number_input(
            "Multa percentual por atraso (%)",
            min_value=0.0,
            value=float(defaults["late_fine_pct"]),
            step=0.1,
            key="fund_late_fine_pct",
        )
        late_fine_fixed = st.number_input(
            "Multa fixa por atraso",
            min_value=0.0,
            value=float(defaults["late_fine_fixed"]),
            step=100.0,
            key="fund_late_fine_fixed",
        )
        st.caption("Esses parâmetros sensibilizam a Curva DC e a memória diária após o vencimento.")
        installment_amount = None

    try:
        projection = build_projection(
            advance_date=advance_date,
            hospital_payment_day=int(hospital_payment_day),
            operation_mode=operation_mode,
            monthly_rate_pct=float(monthly_rate_pct),
            operational_variable_pct=float(operational_variable_pct),
            operational_fixed_cost=float(operational_fixed_cost),
            operational_cost_allocation=str(operational_cost_allocation),
            benchmark_annual_pct=float(benchmark_annual_pct),
            benchmark_mode=str(benchmark_mode),
            benchmark_table=benchmark_table,
            cession_fee_pct=float(cession_fee_pct),
            performance_fee_pct=float(performance_fee_pct),
            receivable_value=float(receivable_value),
            advance_pct=float(advance_pct),
            radar_business_days=int(radar_business_days),
            late_monthly_rate_pct=float(late_monthly_rate_pct),
            late_fine_pct=float(late_fine_pct),
            late_fine_fixed=float(late_fine_fixed),
            vp_sensitive_to_advance_date=bool(vp_sensitive_to_advance_date),
            total_term_days=int(total_term_days_input) if total_term_days_input is not None else None,
            grace_days=int(grace_days),
            dc_value=float(dc_value),
            installment_count=int(installment_count_input) if installment_count_input is not None else None,
            installment_amount=float(installment_amount) if installment_amount is not None else None,
            pricing_policy=str(pricing_policy),
            target_xirr_fund_annual_pct=float(target_xirr_fund_annual_pct),
            accrual_start_delay_days=int(accrual_start_delay_days),
        )
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    present_value = float(projection["present_value"])
    monthly_rate_pct = float(projection["monthly_rate_pct"])
    st.session_state["fund_effective_monthly_rate_pct"] = monthly_rate_pct
    financial_present_value = float(projection["financial_present_value"])
    financial_cost = float(projection["financial_cost"])
    operational_total_cost = float(projection["operational_total_cost"])
    equivalent_operation_rate = float(projection["equivalent_operation_rate"])
    anticipation_monthly_rate_pct = float(projection["anticipation_monthly_rate_pct"])
    benchmark_final = float(projection["benchmark_final"])
    spread_bruto_final = float(projection["spread_bruto_final"])
    cession_cost = float(projection["cession_cost"])
    performance_fee_final = float(projection["performance_fee_final"])
    fidc_liquid_curve_final = float(projection["fidc_liquid_curve_final"])
    xirr_gross_annual = projection.get("xirr_gross_annual")
    xirr_fund_annual = projection.get("xirr_fund_annual")
    installments = projection["installments"]
    radars = projection["radars"]
    grace_end = projection["grace_end"]
    installment_count = int(projection["calculated_installment_count"])
    st.session_state["fund_calculated_installment_count"] = installment_count
    if installment_count > 4:
        st.error(
            "A operação calculada possui mais de 4 repasses elegíveis. "
            "A Área do Médico permite no máximo 4 repasses; reduza o prazo total."
        )
        st.stop()
    installment_amount = float(projection["installment_amount"])
    real_total_term_days = int(projection["real_total_term_days"])
    anticipation_cost = float(projection["anticipation_cost"])

    with st.sidebar:
        st.divider()
        st.subheader("Resultado do calendário")
        st.metric("Prazo limite da operação", f"{int(projection['input_total_term_days'])} dias")
        st.caption(f"Data limite / vencimento econômico: {format_date_pt(projection['operation_limit_date'])}")
        st.caption(f"Prazo efetivo até última liquidação: {int(projection['real_total_term_days'])} dias")
        st.metric("Repasses elegíveis", installment_count)
        st.caption(f"Última liquidação operacional prevista: {format_date_pt(projection['last_liquidation_date'])}")
        if projection["pricing_policy"] == PRICING_POLICY_TARGET_XIRR:
            st.caption(
                "Taxa mensal calculada pela XIRR alvo: "
                f"{format_pct(anticipation_monthly_rate_pct)} ao mês"
            )
        else:
            st.caption(f"Taxa mensal da antecipação: {format_pct(anticipation_monthly_rate_pct)} ao mês")
        st.caption(f"Taxa de antecipação total: {format_pct(equivalent_operation_rate * 100)} da operação")

    tab_main = st.container()

    with tab_main:
        metric_cols = st.columns(5)
        with metric_cols[0]:
            render_metric_card("VP creditado", format_brl(present_value), "valor líquido projetado")
        with metric_cols[1]:
            render_metric_card("Direito Creditório", format_brl(float(dc_value)), "valor nominal do ativo")
        with metric_cols[2]:
            render_metric_card("Benchmark", format_brl(benchmark_final), "Selic/CDI acumulado")
        with metric_cols[3]:
            render_metric_card("Spread bruto", format_brl(spread_bruto_final), "operação - benchmark")
        with metric_cols[4]:
            render_metric_card("XIRR bruta", format_optional_pct(xirr_gross_annual), "fluxo da operação")
        metric_cols_2 = st.columns(5)
        with metric_cols_2[0]:
            render_metric_card("Cessão FIDC", format_brl(cession_cost), "custo inicial")
        with metric_cols_2[1]:
            render_metric_card("Fee performance", format_brl(performance_fee_final), "sobre spread")
        with metric_cols_2[2]:
            render_metric_card("Curva líquida FIDC", format_brl(fidc_liquid_curve_final), "após cessão inicial")
        with metric_cols_2[3]:
            render_metric_card("XIRR líquida", format_optional_pct(xirr_fund_annual), "VP + cessão inicial")
        with metric_cols_2[4]:
            render_metric_card("Vencimento econômico", format_date_pt(projection["final_date"]), "data limite da operação")

        chart_col, side_col = st.columns([2.45, 1], gap="large")
        with chart_col:
            fig = build_chart(projection, advance_date, float(dc_value))
            st.plotly_chart(fig, use_container_width=True, key="chart_operacao_prevista")

        with side_col:
            render_executive_simulation_notes(
                advance_date,
                float(dc_value),
                float(monthly_rate_pct),
                present_value,
                projection,
            )

        st.subheader("Comentários / Marcos")
        st.dataframe(
            build_executive_milestones(advance_date, projection),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("Tabela analítica diária da operação", expanded=False):
            st.caption(
                "Tabela analítica por dia útil com Curva de Encargos, DC, Cobrança, Selic, Fundo e Fluxo de Pagamento."
            )
            daily_evolution = format_daily_evolution_table(
                build_daily_evolution_table(
                    projection,
                    late_monthly_rate=float(projection["late_monthly_rate_pct"]) / 100,
                    fine_pct=float(projection["late_fine_pct"]) / 100,
                    fine_fixed=float(projection["late_fine_fixed"]),
                )
            )
            st.dataframe(daily_evolution, use_container_width=True, hide_index=True)

    if False:
        st.caption(
            "Use esta aba para testar deterioração da liquidação. A operação prevista permanece preservada na primeira aba."
        )
        st.subheader("Configuração da simulação")
        st.caption(
            "Ajuste esta seção como um cenário alternativo. Parcelas não marcadas continuam pagas integralmente no vencimento."
        )

        with st.expander("Parâmetros de atraso / mora", expanded=True):
            param_cols = st.columns(4)
            with param_cols[0]:
                monthly_late_rate_pct = st.number_input("Taxa de mora (% ao mês)", min_value=0.0, value=1.0, step=0.1)
                tolerance_days = st.number_input("Dias de tolerância", min_value=0, max_value=60, value=0, step=1)
            with param_cols[1]:
                fine_fixed = st.number_input("Multa fixa por atraso", min_value=0.0, value=0.0, step=100.0)
                fine_pct = st.number_input("Multa percentual por atraso (%)", min_value=0.0, value=0.0, step=0.1)
            with param_cols[2]:
                interest_base = st.selectbox("Base do juro", ["sobre saldo vencido", "sobre parcela em atraso"])
                use_manual_analysis_date = st.toggle("Usar data-base manual", value=False)
            with param_cols[3]:
                manual_analysis_date = st.date_input(
                    "Data-base manual",
                    value=max(item.due_date for item in installments) + timedelta(days=1),
                    format="DD/MM/YYYY",
                    disabled=not use_manual_analysis_date,
                )
                adjusted_qmm_enabled = st.toggle("Exibir QMM ajustado", value=True)
                st.caption("Mora calculada por juros simples diários.")

        installment_labels = {
            f"Parcela {item.number} - {format_date_pt(item.due_date)} - {format_brl(item.amount)}": item.number
            for item in installments
        }
        selected_labels = st.multiselect(
            "Parcelas com atraso",
            options=list(installment_labels.keys()),
            help="Todas as parcelas não selecionadas serão consideradas pagas integralmente no vencimento.",
        )
        delayed_numbers = [installment_labels[label] for label in selected_labels]
        delay_treatment = st.selectbox(
            "Tratamento do atraso",
            [
                "Manter atraso em aberto",
                "Liquidar na próxima parcela",
                "Distribuir nas parcelas seguintes",
            ],
            help="Define como o principal em atraso será incorporado aos pagamentos futuros da simulação.",
        )

        status_by_number: dict[int, str] = {}
        paid_by_number: dict[int, float] = {}
        payment_date_by_number: dict[int, date] = {}
        apuration_placeholders = {}
        if delayed_numbers:
            st.caption("Configure apenas as parcelas em atraso.")
        else:
            st.info("Nenhuma parcela marcada como atrasada. O cenário alternativo replica a operação prevista.")

        for number in delayed_numbers:
            item = next(installment for installment in installments if installment.number == number)
            with st.container(border=True):
                st.markdown(f"**Parcela {item.number} | {format_date_pt(item.due_date)} | {format_brl(item.amount)}**")
                c1, c2, c3 = st.columns([1.2, 1, 1])
                with c1:
                    status = st.selectbox(
                        "Tipo de atraso",
                        ["Não pago", "Pago parcialmente"],
                        key=f"delay_status_{number}",
                    )
                with c2:
                    if status == "Pago parcialmente":
                        payment_date = st.date_input(
                            "Data do pagamento parcial",
                            value=item.due_date,
                            format="DD/MM/YYYY",
                            key=f"delay_payment_date_{number}",
                        )
                    else:
                        payment_date = item.due_date
                        apuration_placeholders[number] = st.empty()
                with c3:
                    if status == "Pago parcialmente":
                        paid_value = st.number_input(
                            "Valor pago",
                            min_value=0.0,
                            max_value=float(item.amount),
                            value=float(item.amount) / 2,
                            step=1000.0,
                            key=f"delay_paid_{number}",
                        )
                    else:
                        paid_value = 0.0
                        st.metric("Valor pago", format_brl(0.0))
                status_by_number[number] = status
                paid_by_number[number] = float(paid_value)
                payment_date_by_number[number] = payment_date

        edited_table = build_delay_scenario_rows(
            installments,
            delayed_numbers,
            status_by_number,
            paid_by_number,
            payment_date_by_number,
            delay_treatment,
        )
        automatic_analysis_date = calculate_automatic_analysis_date(edited_table, installments)
        analysis_date = manual_analysis_date if use_manual_analysis_date else automatic_analysis_date
        analysis_date_source = "data-base manual" if use_manual_analysis_date else "data-base automática"
        for placeholder in apuration_placeholders.values():
            placeholder.markdown(
                f"""
                <div style="border:1px solid #d9e0ea;border-radius:8px;padding:9px 11px;background:#ffffff;">
                    <span style="display:block;color:#64748b;font-size:0.72rem;font-weight:700;line-height:1.1;">Apuração</span>
                    <strong style="display:block;color:#172033;font-size:0.98rem;line-height:1.25;margin-top:3px;">{format_date_pt(analysis_date)}</strong>
                    <small style="display:block;color:#64748b;font-size:0.72rem;line-height:1.15;">{analysis_date_source}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )
        delay_params = DelayParameters(
            analysis_date=analysis_date,
            monthly_late_rate=float(monthly_late_rate_pct) / 100,
            fine_fixed=float(fine_fixed),
            fine_pct=float(fine_pct) / 100,
            tolerance_days=int(tolerance_days),
            interest_base=interest_base,
            adjusted_qmm_enabled=bool(adjusted_qmm_enabled),
        )
        edited_table, liquidation = settle_delay_treatment(
            installments,
            edited_table,
            delay_params,
            delayed_numbers,
            delay_treatment,
        )
        if delay_treatment != "Manter atraso em aberto" and delayed_numbers:
            target_indexes = future_regularization_indexes(edited_table, delayed_numbers, delay_treatment)
            if not target_indexes:
                st.warning("Não há parcelas futuras disponíveis para liquidar ou distribuir o atraso.")
        risk_projection = apply_liquidation_to_projection(projection, liquidation, delay_params)

        st.divider()
        st.subheader("Resumo executivo do cenário")
        additional_payment_total = float(edited_table["Pagamento adicional"].sum())
        risk_cols = st.columns(6)
        with risk_cols[0]:
            render_metric_card("Data-base", format_date_pt(analysis_date), "corte da simulação")
        with risk_cols[1]:
            render_metric_card("Atraso acumulado", format_brl(float(liquidation["overdue_total"])), "principal vencido")
        with risk_cols[2]:
            render_metric_card("Mora gerada", format_brl(float(liquidation["mora_charged_total"])), "juros calculados")
        with risk_cols[3]:
            render_metric_card("Multa gerada", format_brl(float(liquidation["fine_charged_total"])), "penalidade calculada")
        with risk_cols[4]:
            render_metric_card("Pagamento adicional", format_brl(additional_payment_total), "regularização futura")
        with risk_cols[5]:
            render_metric_card("Cobrança realizada", format_brl(float(liquidation["realized_total"])), "fluxo efetivo")

        st.plotly_chart(
            build_chart(risk_projection, advance_date, float(dc_value)),
            use_container_width=True,
            key="chart_simulacao_atraso",
        )

        with st.expander("Memória diária das curvas no cenário de atraso", expanded=False):
            st.caption(
                "Nesta memória, multa e juros moratórios usam os parâmetros informados na simulação de atraso."
            )
            risk_daily_evolution = build_daily_evolution_table(
                risk_projection,
                late_monthly_rate=float(monthly_late_rate_pct) / 100,
                fine_pct=float(fine_pct) / 100,
                fine_fixed=float(fine_fixed),
            )
            st.dataframe(format_daily_evolution_table(risk_daily_evolution), use_container_width=True, hide_index=True)

        with st.expander("Premissas do cálculo do atraso", expanded=False):
            st.markdown(
                "- Parcelas não selecionadas são consideradas pagas integralmente no vencimento.\n"
                "- A cobrança esperada preserva o cronograma contratual original.\n"
                "- Mora = saldo vencido x taxa diária equivalente, após a tolerância definida.\n"
                "- Multa gerada = multa fixa + percentual configurado sobre o valor vencido não pago.\n"
                "- A memória mostra mora e multa geradas no ciclo, mesmo quando foram quitadas por pagamento adicional.\n"
                "- Pagamentos adicionais baixam primeiro mora, depois multa, atraso acumulado e parcela corrente.\n"
                "- QMM ajustado, quando ativo, reduz o QMM de referência pelo saldo exigível em aberto."
            )

        result_table = liquidation["result_table"].copy()
        result_table = result_table[
            [
                "Parcela",
                "Data de vencimento",
                "Valor previsto",
                "Status",
                "Data de pagamento",
                "Valor pago",
                "Saldo em atraso",
                "Mora gerada",
                "Multa gerada",
                "Pagamento adicional",
            ]
        ].rename(
            columns={
                "Mora gerada": "Mora",
                "Multa gerada": "Multa",
            }
        )
        money_columns = [
            "Valor previsto",
            "Valor pago",
            "Saldo em atraso",
            "Multa",
            "Mora",
            "Pagamento adicional",
        ]
        for col in money_columns:
            result_table[col] = result_table[col].map(format_brl)
        result_table["Data de vencimento"] = result_table["Data de vencimento"].map(format_date_pt)
        result_table["Data de pagamento"] = result_table["Data de pagamento"].apply(
            lambda value: "-" if value is None or pd.isna(value) else format_date_pt(value)
        )
        with st.expander("Memória de cálculo por parcela", expanded=False):
            st.dataframe(result_table, use_container_width=True, hide_index=True)

        with st.expander("Comentários / marcos do cenário", expanded=False):
            risk_timeline = build_timeline_comments(
                advance_date,
                grace_end,
                installments,
                radars,
                projection=projection,
                liquidation=liquidation,
            )
            render_timeline_comments(risk_timeline)

    st.session_state["_previous_area"] = selected_area

if __name__ == "__main__":
    main()

