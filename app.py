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
        rows.append({"date": current, "cobranca_esperada": accumulated})
    return pd.DataFrame(rows)


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


def build_delay_scenario_rows(
    installments: list[Installment],
    delayed_numbers: list[int],
    status_by_number: dict[int, str],
    paid_by_number: dict[int, float],
    payment_date_by_number: dict[int, date],
    delay_treatment: str = "Manter atraso em aberto",
) -> pd.DataFrame:
    rows = default_liquidation_rows(installments)
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

    if delay_treatment != "Manter atraso em aberto" and shortfall_by_number:
        total_shortfall = sum(shortfall_by_number.values())
        future_indexes = [
            index
            for index, row in rows.iterrows()
            if int(row["Parcela"]) > min(shortfall_by_number)
            and int(row["Parcela"]) not in delayed_set
        ]
        if delay_treatment == "Liquidar na próxima parcela":
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
    if delay_treatment == "Liquidar na próxima parcela":
        return indexes[:1]
    if delay_treatment == "Distribuir nas parcelas seguintes":
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

    if delay_treatment == "Manter atraso em aberto" or not target_indexes:
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


def parse_date_value(value: object, fallback: date) -> date:
    if isinstance(value, date):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return fallback
    return parsed.date()


def normalize_status(value: object) -> str:
    raw = str(value or "").strip().lower()
    if "parcial" in raw:
        return "Pago parcialmente"
    if "não" in raw or "nao" in raw or "não" in raw:
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
            payment_date = due_date
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
    overdue_balance: float,
    current_due: float,
) -> tuple[float, float, float, float]:
    remaining_payment = max(payment_amount, 0.0)

    paid_mora = min(remaining_payment, mora_balance)
    mora_balance -= paid_mora
    remaining_payment -= paid_mora

    paid_overdue = min(remaining_payment, overdue_balance)
    overdue_balance -= paid_overdue
    remaining_payment -= paid_overdue

    paid_current = min(remaining_payment, current_due)
    current_due -= paid_current
    remaining_payment -= paid_current

    return mora_balance, overdue_balance, current_due, remaining_payment


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
    expected_accumulated = 0.0
    realized_accumulated = 0.0
    last_interest_date = min(item.due_date for item in installments)

    for item in installments:
        schedule_row = schedule.loc[schedule["Parcela"] == item.number].iloc[0]
        status = str(schedule_row["Status"])
        due_date = item.due_date
        payment_date = parse_date_value(schedule_row["Data de pagamento"], due_date)
        paid_value = float(schedule_row["Valor pago"] or 0.0)
        if status == "Não pago":
            payment_date = params.analysis_date

        if paid_value > 0:
            cycle_event_date = max(due_date, min(payment_date, params.analysis_date))
        else:
            cycle_event_date = due_date
        if params.interest_base == "sobre saldo vencido":
            mora_balance += calculate_interest(overdue_balance, last_interest_date, due_date, params)
        else:
            mora_balance += calculate_interest(max(overdue_balance, 0), last_interest_date, due_date, params)

        current_due = item.amount
        expected_accumulated += item.amount

        if payment_date > due_date and paid_value > 0:
            interest_base = overdue_balance + current_due
            if params.interest_base == "sobre parcela em atraso":
                interest_base = current_due
            mora_balance += calculate_interest(interest_base, due_date, payment_date, params)

        mora_balance, overdue_balance, current_due, excess_payment = apply_payment_waterfall(
            paid_value,
            mora_balance,
            overdue_balance,
            current_due,
        )

        unpaid_after_payment = current_due
        if unpaid_after_payment > 0 and params.analysis_date > due_date + timedelta(days=params.tolerance_days):
            fine_balance += params.fine_fixed + unpaid_after_payment * params.fine_pct

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
                "Data de pagamento": payment_date if paid_value > 0 else None,
                "Valor pago": paid_value,
                "Saldo em atraso": overdue_balance,
                "Mora": mora_balance,
                "Multa": fine_balance,
                "Saldo exigível atualizado": saldo_exigivel,
                "Gap de cobrança": expected_accumulated - realized_accumulated,
                "Excedente amortizado": excess_payment,
                "Pagamento adicional": float(schedule_row.get("Pagamento adicional", 0.0) or 0.0),
            }
        )

    final_interest_date = max(params.analysis_date, last_interest_date)
    if params.interest_base == "sobre saldo vencido":
        mora_balance += calculate_interest(overdue_balance, last_interest_date, final_interest_date, params)
    fine_and_mora = mora_balance + fine_balance
    expected_total = sum(item.amount for item in installments)
    realized_total = sum(amount for _, amount in payments)
    gap_total = max(expected_total - realized_total, 0.0)

    if rows:
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
        "saldo_exigivel_total": overdue_balance + fine_and_mora,
    }


def build_realized_collection_curve(
    dates: pd.DatetimeIndex,
    payments: list[tuple[date, float]],
) -> pd.DataFrame:
    rows = []
    for current in dates.date:
        accumulated = sum(amount for payment_date, amount in payments if current >= payment_date)
        rows.append({"date": current, "cobranca_realizada": accumulated})
    return pd.DataFrame(rows)


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
    df["cobranca_realizada"] = df["cobranca_esperada"]
    df["gap_cobranca"] = 0.0
    df["qmm_ajustado"] = df["qmm"]
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
            (projection["grace_end"] - projection["df"]["date"].min()).days,
            projection["radars"],
        )
        collection_curve = build_collection_curve(dates, projection["installments"])
        df = qmm_curve.merge(collection_curve, on="date")
        df["dc"] = float(projection["df"]["dc"].iloc[0])

    realized_curve = build_realized_collection_curve(pd.DatetimeIndex(pd.to_datetime(df["date"])), liquidation["payments"])
    df = df.drop(columns=["cobranca_realizada", "gap_cobranca", "qmm_ajustado"], errors="ignore").merge(
        realized_curve,
        on="date",
        how="left",
    )
    df["cobranca_realizada"] = df["cobranca_realizada"].fillna(0.0)
    df["gap_cobranca"] = (df["cobranca_esperada"] - df["cobranca_realizada"]).clip(lower=0)
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

    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["qmm"],
            mode="lines",
            name="Curva QMM Ref.",
            line=dict(color=QMM_COLOR, width=4),
            customdata=money_hover(df["qmm"]),
            hovertemplate="%{x|%d/%m/%Y}<br>QMM: %{customdata}<extra></extra>",
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
            y=df["cobranca_esperada"],
            mode="lines",
            name="Cobrança Esperada",
            line=dict(color=COBRANCA_COLOR, width=3, shape="hv"),
            customdata=money_hover(df["cobranca_esperada"]),
            hovertemplate="%{x|%d/%m/%Y}<br>Cobrança esperada: %{customdata}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["cobranca_realizada"],
            mode="lines",
            name="Cobrança Realizada",
            line=dict(color="#2a9d8f", width=3, shape="hv"),
            fill="tonexty",
            fillcolor="rgba(242, 140, 40, 0.10)",
            customdata=money_hover(df["cobranca_realizada"]),
            hovertemplate="%{x|%d/%m/%Y}<br>Cobrança realizada: %{customdata}<extra></extra>",
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

    y_columns = ["qmm", "qmm_ajustado", "cobranca_esperada", "cobranca_realizada", "dc"]
    y_max = max(dc_value, float(df[y_columns].max().max())) * 1.12
    fig.update_layout(
        height=620,
        template="plotly_white",
        margin=dict(l=24, r=24, t=128, b=48),
        title=dict(
            text="Simulação Executiva de Antecipação de Recebíveis Médicos",
            font=dict(size=20, color="#1f2937"),
            x=0.01,
            y=0.97,
            yanchor="top",
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=1.10,
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
    liquidation = projection.get("liquidation", {})

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
    if "delay_params" in projection:
        params = projection["delay_params"]
        st.markdown("**Atraso / Mora**")
        st.caption(f"Mora: {format_pct(params.monthly_late_rate * 100)} ao mês, calculada por juros simples diários.")
        st.caption("Saldo exigível = atraso acumulado + mora + multa.")
        st.caption("Gap = cobrança esperada - cobrança realizada.")
        if params.adjusted_qmm_enabled:
            st.caption("QMM ajustado = QMM referência - saldo exigível em aberto.")


def build_timeline_comments(
    advance_date: date,
    grace_end: date,
    installments: list[Installment],
    radars: list[RadarWindow],
    liquidation: dict[str, object] | None = None,
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
        payment_comment = f"Cobrança acumulada sobe em {format_brl(item.amount)}."
        if liquidation:
            table = liquidation["result_table"]
            row = table.loc[table["Parcela"] == item.number]
            if not row.empty:
                status = str(row.iloc[0]["Status"])
                paid = float(row.iloc[0]["Valor pago"])
                overdue = float(row.iloc[0]["Saldo em atraso"])
                mora = float(row.iloc[0]["Mora"])
                payment_comment = (
                    f"{status}: pago {format_brl(paid)}; "
                    f"atraso acumulado {format_brl(overdue)}; mora {format_brl(mora)}."
                )
        rows.append(
            {
                "Data": format_date_pt(item.due_date),
                "Marco": f"Vencimento da parcela {item.number}",
                "Comentário": payment_comment,
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
    anticipation_cost = sum(item.amount for item in installments) - present_value

    with st.sidebar:
        st.divider()
        st.subheader("Resultado do calendário")
        if operation_mode == "Por parcelas":
            st.metric("Prazo total calculado", f"{real_total_term_days} dias")
        else:
            st.metric("Quantidade de parcelas calculada", installment_count)
        st.caption(f"Valor por parcela: {format_brl(installment_amount)}")
        st.caption(f"Última parcela: {format_date_pt(projection['final_date'])}")

    tab_main, tab_delay = st.tabs(["Operação prevista", "Simulação de atraso"])

    with tab_main:
        metric_cols = st.columns(5)
        with metric_cols[0]:
            render_metric_card("VP creditado", format_brl(present_value), "valor líquido projetado")
        with metric_cols[1]:
            render_metric_card("Custo da antecipação", format_brl(anticipation_cost), "DC/parcelas - VP")
        with metric_cols[2]:
            render_metric_card("Direito Creditório", format_brl(float(dc_value)), "limite do QMM")
        with metric_cols[3]:
            render_metric_card("Radar mensal", f"{len(radars)} janelas", "5 dias úteis antes/depois")
        with metric_cols[4]:
            render_metric_card("Liquidação final", format_date_pt(projection["final_date"]), "calendário hospitalar")

        chart_col, side_col = st.columns([2.45, 1], gap="large")
        with chart_col:
            fig = build_chart(projection, advance_date, float(dc_value))
            st.plotly_chart(fig, use_container_width=True, key="chart_operacao_prevista")

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

    with tab_delay:
        st.caption(
            "Use esta aba para testar deterioração da liquidação. A operação prevista permanece preservada na primeira aba."
        )
        param_cols = st.columns(4)
        with param_cols[0]:
            analysis_date = st.date_input("Data de análise", value=date.today(), format="DD/MM/YYYY")
            monthly_late_rate_pct = st.number_input("Taxa de mora (% ao mês)", min_value=0.0, value=1.0, step=0.1)
        with param_cols[1]:
            fine_fixed = st.number_input("Multa fixa por atraso", min_value=0.0, value=0.0, step=100.0)
            fine_pct = st.number_input("Multa percentual por atraso (%)", min_value=0.0, value=0.0, step=0.1)
        with param_cols[2]:
            tolerance_days = st.number_input("Dias de tolerância", min_value=0, max_value=60, value=0, step=1)
            interest_base = st.selectbox("Base do juro", ["sobre saldo vencido", "sobre parcela em atraso"])
        with param_cols[3]:
            adjusted_qmm_enabled = st.toggle("Exibir QMM ajustado", value=True)
            st.caption("Mora calculada por juros simples diários.")

        st.info(
            "Premissas do atraso: parcelas não selecionadas são pagas integralmente no vencimento; "
            "mora = saldo vencido x taxa diária equivalente; saldo exigível = atraso + mora + multa; "
            "QMM ajustado = QMM de referência - saldo exigível em aberto."
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

        st.subheader("Configuração do cenário de atraso")
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
        if delayed_numbers:
            st.caption("Configure apenas as parcelas em atraso. As demais ficam pagas integralmente no vencimento.")
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
                    payment_date = st.date_input(
                        "Data de pagamento / análise",
                        value=max(item.due_date, analysis_date),
                        format="DD/MM/YYYY",
                        key=f"delay_payment_date_{number}",
                    )
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

        risk_cols = st.columns(5)
        with risk_cols[0]:
            render_metric_card("Atraso acumulado", format_brl(float(liquidation["overdue_total"])), "saldo vencido")
        with risk_cols[1]:
            render_metric_card("Mora acumulada", format_brl(float(liquidation["mora_total"])), "juros por atraso")
        with risk_cols[2]:
            render_metric_card("Saldo exigível", format_brl(float(liquidation["saldo_exigivel_total"])), "atraso + mora + multa")
        with risk_cols[3]:
            render_metric_card("Cobrança realizada", format_brl(float(liquidation["realized_total"])), "pagamentos efetivos")
        with risk_cols[4]:
            render_metric_card("Gap de cobrança", format_brl(float(liquidation["gap_total"])), "esperada - realizada")

        st.plotly_chart(
            build_chart(risk_projection, advance_date, float(dc_value)),
            use_container_width=True,
            key="chart_simulacao_atraso",
        )

        result_table = liquidation["result_table"].copy()
        money_columns = [
            "Valor previsto",
            "Valor pago",
            "Saldo em atraso",
            "Mora",
            "Multa",
            "Saldo exigível atualizado",
            "Gap de cobrança",
            "Pagamento adicional",
            "Excedente amortizado",
        ]
        for col in money_columns:
            result_table[col] = result_table[col].map(format_brl)
        result_table["Data de vencimento"] = result_table["Data de vencimento"].map(format_date_pt)
        result_table["Data de pagamento"] = result_table["Data de pagamento"].apply(
            lambda value: "-" if value is None or pd.isna(value) else format_date_pt(value)
        )
        st.dataframe(result_table, use_container_width=True, hide_index=True)

        risk_timeline = build_timeline_comments(advance_date, grace_end, installments, radars, liquidation)
        st.dataframe(risk_timeline, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()

