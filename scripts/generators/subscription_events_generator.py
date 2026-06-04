"""
subscription_events_generator.py

Project Atlas / Nexus Technologies
Phase 3D - Billing Subscription Events

Purpose
-------
Generates billing_subscription_events.csv from billing_subscriptions.csv.

This table is the authoritative ARR / MRR movement ledger for subscription
lifecycle analytics.

It supports:
- ARR bridge reporting
- New ARR
- Expansion ARR
- Contraction ARR
- Churned ARR
- GRR / NRR
- lifecycle cohorts
- DataPulse acquisition repricing narrative
- audit / dbt control testing

Grain
-----
One row per subscription commercial event.

Design principle
----------------
billing_subscriptions.csv = current / contract master state
billing_subscription_events.csv = historical movement ledger

For churned subscriptions, billing_subscriptions.mrr_gbp may retain the last
contracted recurring value. The terminal churn event sets new_mrr/new_arr to 0.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

from scripts.utils.config import BusinessRulesConfig
from scripts.utils.logger import get_logger
from scripts.utils.paths import get_raw_data_path


logger = get_logger("SubscriptionEventsGenerator", "generation_execution.log")


@dataclass(frozen=True)
class SubscriptionEventDefectRates:
    """Controlled synthetic defect rates for subscription event data."""

    math_mismatch: float = 0.010
    chronology_violation: float = 0.005
    ghost_event: float = 0.005
    terminal_event_not_zeroed: float = 0.0025


@dataclass(frozen=True)
class SubscriptionEventRules:
    """Business rules for subscription event generation."""

    current_date: date = date(2026, 6, 3)
    datapulse_reprice_start: date = date(2024, 11, 1)
    datapulse_reprice_end: date = date(2025, 3, 31)
    created_at: date = date(2026, 6, 3)
    updated_at: date = date(2026, 6, 3)


class SubscriptionEventsGenerator:
    """
    Generates billing subscription event history from subscription master data.

    Input
    -----
    data/raw/billing/billing_subscriptions.csv

    Output
    ------
    data/raw/billing/billing_subscription_events.csv
    """

    REQUIRED_SUBSCRIPTION_COLUMNS = {
        "subscription_id",
        "customer_id",
        "customer_segment",
        "contract_start_date",
        "contract_end_date",
        "contract_term_months",
        "billing_frequency",
        "contract_status",
        "mrr_local",
        "mrr_gbp",
        "arr_local",
        "arr_gbp",
        "currency",
        "source_system",
        "acquisition_source",
        "is_defect_flag",
        "defect_type",
    }

    VALID_EVENT_TYPES = {
        "new",
        "renewal",
        "expansion",
        "contraction",
        "price_increase",
        "churn",
        "pause",
    }

    VALID_CUSTOMER_SEGMENTS = {"SMB", "Mid-Market", "Enterprise"}

    def __init__(self) -> None:
        self.config = BusinessRulesConfig()
        self.seed: int = int(self.config.project.get("random_seed", 42))
        self.output_filename = "billing_subscription_events.csv"

        self.defect_rates = SubscriptionEventDefectRates()
        self.rules = SubscriptionEventRules()

        # Use a shifted seed so event randomness is stable but not identical
        # to subscription/customer generation patterns.
        self.rng = np.random.default_rng(self.seed + 700)

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_pk(value: str) -> str:
        """Generate deterministic MD5 surrogate key."""
        return hashlib.md5(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _to_date(value: object, column_name: str) -> Optional[date]:
        """Robustly parse a date-like value. Returns None for blank/null."""
        if pd.isna(value) or str(value).strip() == "":
            return None

        parsed = pd.to_datetime(value, errors="coerce")

        if pd.isna(parsed):
            raise ValueError(f"Unable to parse {column_name}: {value!r}")

        return parsed.date()

    @staticmethod
    def _normalise_bool_int(value: object, default: int = 0) -> int:
        """Normalize common boolean/integer/string flags into 0/1."""
        if pd.isna(value):
            return default

        if isinstance(value, bool):
            return int(value)

        if isinstance(value, (int, float)):
            return int(value == 1)

        value_str = str(value).strip().lower()

        if value_str in {"1", "true", "yes", "y"}:
            return 1

        if value_str in {"0", "false", "no", "n"}:
            return 0

        return default

    def _random_date_between(self, start_date: date, end_date: date) -> date:
        """Return random date between start_date and end_date inclusive."""
        delta_days = (end_date - start_date).days

        if delta_days <= 0:
            return start_date

        offset = int(self.rng.integers(0, delta_days + 1))
        return start_date + timedelta(days=offset)

    # ------------------------------------------------------------------
    # Loading and preparation
    # ------------------------------------------------------------------

    def _load_subscriptions(self) -> pd.DataFrame:
        """Load and validate billing_subscriptions.csv."""
        subscriptions_path = get_raw_data_path("billing") / "billing_subscriptions.csv"

        if not subscriptions_path.exists():
            raise FileNotFoundError(
                f"billing_subscriptions.csv not found at: {subscriptions_path}. "
                "Run the subscription generator first."
            )

        subscriptions_df = pd.read_csv(subscriptions_path)

        self._validate_input_columns(
            df=subscriptions_df,
            required_columns=self.REQUIRED_SUBSCRIPTION_COLUMNS,
            dataset_name="billing_subscriptions.csv",
        )

        subscriptions_df = self._prepare_subscriptions(subscriptions_df)

        logger.info(
            "Loaded subscription master: %s rows.",
            f"{len(subscriptions_df):,}",
        )

        return subscriptions_df

    @staticmethod
    def _validate_input_columns(
        df: pd.DataFrame,
        required_columns: set[str],
        dataset_name: str,
    ) -> None:
        """Validate required input columns."""
        missing_columns = required_columns.difference(df.columns)

        if missing_columns:
            raise ValueError(
                f"{dataset_name} is missing required columns: "
                f"{sorted(missing_columns)}"
            )

    def _prepare_subscriptions(self, subscriptions_df: pd.DataFrame) -> pd.DataFrame:
        """Normalize subscription fields before event generation."""
        df = subscriptions_df.copy()

        if df.empty:
            raise ValueError("billing_subscriptions.csv is empty.")

        df["subscription_id"] = df["subscription_id"].astype(str)
        df["customer_id"] = df["customer_id"].astype(str)
        df["customer_segment"] = df["customer_segment"].astype(str)
        df["billing_frequency"] = df["billing_frequency"].astype(str)
        df["contract_status"] = df["contract_status"].astype(str)
        df["currency"] = df["currency"].astype(str).str.upper()
        df["source_system"] = df["source_system"].fillna("unknown").astype(str)
        df["acquisition_source"] = df["acquisition_source"].fillna("unknown").astype(str)

        df["contract_start_date"] = pd.to_datetime(
            df["contract_start_date"],
            errors="coerce",
        )

        df["contract_end_date"] = pd.to_datetime(
            df["contract_end_date"],
            errors="coerce",
        )

        if df["contract_start_date"].isna().any():
            bad_count = int(df["contract_start_date"].isna().sum())
            raise ValueError(
                f"billing_subscriptions.csv contains {bad_count:,} invalid contract_start_date values."
            )

        for column in ["mrr_local", "mrr_gbp", "arr_local", "arr_gbp"]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

            if df[column].isna().any():
                bad_count = int(df[column].isna().sum())
                raise ValueError(
                    f"billing_subscriptions.csv contains {bad_count:,} invalid {column} values."
                )

        df["contract_term_months"] = pd.to_numeric(
            df["contract_term_months"],
            errors="coerce",
        ).fillna(12).astype(int)

        df["is_defect_flag"] = df["is_defect_flag"].apply(
            lambda x: self._normalise_bool_int(x, default=0)
        )

        df["defect_type"] = df["defect_type"].where(
            df["defect_type"].notna(),
            None,
        )

        invalid_segments = set(df["customer_segment"].unique()).difference(
            self.VALID_CUSTOMER_SEGMENTS
        )

        if invalid_segments:
            raise ValueError(
                f"Invalid customer_segment values in billing_subscriptions.csv: "
                f"{sorted(invalid_segments)}"
            )

        return df

    # ------------------------------------------------------------------
    # Event math
    # ------------------------------------------------------------------

    @staticmethod
    def _arr_from_mrr(mrr: float) -> float:
        """Calculate ARR from MRR."""
        return round(float(mrr) * 12, 2)

    @staticmethod
    def _round_money(value: float) -> float:
        """Stable financial rounding."""
        return round(float(value), 2)
    
    def _recalculate_event_amounts(
        self,
        event: dict,
        previous_mrr_local: float,
        new_mrr_local: float,
        previous_mrr_gbp: float,
        new_mrr_gbp: float,
    ) -> dict:
        """
        Recalculate all MRR/ARR amount fields for an event.

        This is used by the timeline replay step to ensure each event's previous
        MRR equals the previous event's ending MRR.
        """
        previous_mrr_local = self._round_money(previous_mrr_local)
        new_mrr_local = self._round_money(new_mrr_local)
        previous_mrr_gbp = self._round_money(previous_mrr_gbp)
        new_mrr_gbp = self._round_money(new_mrr_gbp)

        previous_arr_local = self._arr_from_mrr(previous_mrr_local)
        new_arr_local = self._arr_from_mrr(new_mrr_local)
        previous_arr_gbp = self._arr_from_mrr(previous_mrr_gbp)
        new_arr_gbp = self._arr_from_mrr(new_mrr_gbp)

        event["previous_mrr_local"] = previous_mrr_local
        event["new_mrr_local"] = new_mrr_local
        event["mrr_delta_local"] = self._round_money(new_mrr_local - previous_mrr_local)

        event["previous_mrr_gbp"] = previous_mrr_gbp
        event["new_mrr_gbp"] = new_mrr_gbp
        event["mrr_delta_gbp"] = self._round_money(new_mrr_gbp - previous_mrr_gbp)

        event["previous_arr_local"] = previous_arr_local
        event["new_arr_local"] = new_arr_local
        event["arr_delta_local"] = self._round_money(new_arr_local - previous_arr_local)

        event["previous_arr_gbp"] = previous_arr_gbp
        event["new_arr_gbp"] = new_arr_gbp
        event["arr_delta_gbp"] = self._round_money(new_arr_gbp - previous_arr_gbp)

        return event


    def _replay_subscription_timeline(self, events: list[dict]) -> list[dict]:
        """
        Replay a subscription's event timeline in date order.

        Why this exists
        ---------------
        Events may be generated in logical blocks:
        - new
        - renewals
        - price increases
        - expansions
        - contractions
        - terminal churn/pause

        After sorting by event_date, a later renewal may fall after an expansion.
        This replay step ensures the revenue state carries forward correctly.

        Rules
        -----
        new:
            previous MRR = 0
            new MRR = originally generated opening MRR

        renewal:
            previous MRR = current MRR
            new MRR = current MRR
            delta = 0

        expansion / contraction / price_increase:
            preserve the originally intended delta, but apply it to the current MRR

        churn / pause:
            previous MRR = current MRR
            new MRR = 0
        """
        if not events:
            return events

        # Sort into true business timeline first.
        events = sorted(
            events,
            key=lambda row: (
                row["event_date"],
                row["event_sequence"],
                row["event_id"],
            ),
        )

        current_mrr_local = 0.00
        current_mrr_gbp = 0.00

        replayed_events: list[dict] = []

        for sequence, event in enumerate(events, start=1):
            event = event.copy()
            event["event_sequence"] = sequence

            event_type = str(event["event_type"])

            original_previous_mrr_local = float(event["previous_mrr_local"])
            original_new_mrr_local = float(event["new_mrr_local"])
            original_previous_mrr_gbp = float(event["previous_mrr_gbp"])
            original_new_mrr_gbp = float(event["new_mrr_gbp"])

            if event_type == "new":
                # New event starts the revenue timeline.
                previous_mrr_local = 0.00
                previous_mrr_gbp = 0.00
                new_mrr_local = original_new_mrr_local
                new_mrr_gbp = original_new_mrr_gbp

            elif event_type == "renewal":
                # Renewal is an administrative/commercial continuation unless
                # repriced separately by a price_increase event.
                previous_mrr_local = current_mrr_local
                previous_mrr_gbp = current_mrr_gbp
                new_mrr_local = current_mrr_local
                new_mrr_gbp = current_mrr_gbp

            elif event_type in {"expansion", "contraction", "price_increase"}:
                # Preserve the originally intended movement ratio.
                # This avoids stale previous_mrr values after date sorting.
                if original_previous_mrr_local > 0:
                    local_multiplier = original_new_mrr_local / original_previous_mrr_local
                else:
                    local_multiplier = 1.00

                if original_previous_mrr_gbp > 0:
                    gbp_multiplier = original_new_mrr_gbp / original_previous_mrr_gbp
                else:
                    gbp_multiplier = 1.00

                previous_mrr_local = current_mrr_local
                previous_mrr_gbp = current_mrr_gbp
                new_mrr_local = self._round_money(current_mrr_local * local_multiplier)
                new_mrr_gbp = self._round_money(current_mrr_gbp * gbp_multiplier)

            elif event_type in {"churn", "pause"}:
                # Terminal event ends the revenue stream.
                previous_mrr_local = current_mrr_local
                previous_mrr_gbp = current_mrr_gbp
                new_mrr_local = 0.00
                new_mrr_gbp = 0.00
                event["is_terminal_event"] = 1

            else:
                raise ValueError(f"Unsupported event_type during timeline replay: {event_type}")

            event = self._recalculate_event_amounts(
                event=event,
                previous_mrr_local=previous_mrr_local,
                new_mrr_local=new_mrr_local,
                previous_mrr_gbp=previous_mrr_gbp,
                new_mrr_gbp=new_mrr_gbp,
            )

            current_mrr_local = float(event["new_mrr_local"])
            current_mrr_gbp = float(event["new_mrr_gbp"])

            replayed_events.append(event)

        return replayed_events

    def _build_event(
        self,
        event_id: str,
        subscription: pd.Series,
        event_sequence: int,
        event_date: date,
        event_type: str,
        event_reason: str,
        previous_mrr_local: float,
        new_mrr_local: float,
        previous_mrr_gbp: float,
        new_mrr_gbp: float,
        is_terminal_event: int = 0,
        is_defect_flag: bool = False,
        defect_type: Optional[str] = None,
        override_subscription_id: Optional[str] = None,
    ) -> dict:
        """Build a single subscription event record."""
        previous_mrr_local = self._round_money(previous_mrr_local)
        new_mrr_local = self._round_money(new_mrr_local)
        previous_mrr_gbp = self._round_money(previous_mrr_gbp)
        new_mrr_gbp = self._round_money(new_mrr_gbp)

        previous_arr_local = self._arr_from_mrr(previous_mrr_local)
        new_arr_local = self._arr_from_mrr(new_mrr_local)
        previous_arr_gbp = self._arr_from_mrr(previous_mrr_gbp)
        new_arr_gbp = self._arr_from_mrr(new_mrr_gbp)

        mrr_delta_local = self._round_money(new_mrr_local - previous_mrr_local)
        mrr_delta_gbp = self._round_money(new_mrr_gbp - previous_mrr_gbp)
        arr_delta_local = self._round_money(new_arr_local - previous_arr_local)
        arr_delta_gbp = self._round_money(new_arr_gbp - previous_arr_gbp)

        subscription_id = override_subscription_id or str(subscription["subscription_id"])

        return {
            "event_pk": self._generate_pk(event_id),
            "event_id": event_id,
            "subscription_id": subscription_id,
            "customer_id": str(subscription["customer_id"]),
            "event_sequence": event_sequence,
            "event_date": event_date.isoformat(),
            "event_type": event_type,
            "event_reason": event_reason,
            "previous_mrr_local": previous_mrr_local,
            "new_mrr_local": new_mrr_local,
            "mrr_delta_local": mrr_delta_local,
            "previous_mrr_gbp": previous_mrr_gbp,
            "new_mrr_gbp": new_mrr_gbp,
            "mrr_delta_gbp": mrr_delta_gbp,
            "previous_arr_local": previous_arr_local,
            "new_arr_local": new_arr_local,
            "arr_delta_local": arr_delta_local,
            "previous_arr_gbp": previous_arr_gbp,
            "new_arr_gbp": new_arr_gbp,
            "arr_delta_gbp": arr_delta_gbp,
            "currency": str(subscription["currency"]),
            "source_system": str(subscription["source_system"]),
            "is_terminal_event": is_terminal_event,
            "is_defect_flag": bool(is_defect_flag),
            "defect_type": defect_type,
            "created_at": self.rules.created_at.isoformat(),
            "updated_at": self.rules.updated_at.isoformat(),
        }

    # ------------------------------------------------------------------
    # Movement decisioning
    # ------------------------------------------------------------------

    def _should_generate_expansion(self, subscription: pd.Series) -> bool:
        """Determine whether a subscription should get an expansion event."""
        if subscription["contract_status"] != "Active":
            return False

        segment = str(subscription["customer_segment"])

        if segment == "Enterprise":
            return bool(self.rng.random() < 0.30)

        if segment == "Mid-Market":
            return bool(self.rng.random() < 0.20)

        return bool(self.rng.random() < 0.08)

    def _should_generate_contraction(self, subscription: pd.Series) -> bool:
        """Determine whether a subscription should get a contraction event."""
        if subscription["contract_status"] != "Active":
            return False

        segment = str(subscription["customer_segment"])

        if segment == "Enterprise":
            return bool(self.rng.random() < 0.08)

        if segment == "Mid-Market":
            return bool(self.rng.random() < 0.06)

        return bool(self.rng.random() < 0.04)

    def _should_generate_datapulse_price_increase(self, subscription: pd.Series) -> bool:
        """Determine whether a DataPulse subscription should receive a migration reprice."""
        if str(subscription["acquisition_source"]) != "DataPulse Analytics":
            return False

        if subscription["contract_status"] == "Churned":
            end_date = self._to_date(subscription["contract_end_date"], "contract_end_date")
            if end_date and end_date < self.rules.datapulse_reprice_start:
                return False

        return bool(self.rng.random() < 0.35)

    def _choose_midterm_event_date(
        self,
        start_date: date,
        terminal_date: Optional[date],
    ) -> date:
        """Choose a plausible mid-term event date after start and before terminal/current date."""
        earliest = start_date + relativedelta(months=3)
        latest = terminal_date or self.rules.current_date

        # Avoid placing movement after terminal date or current date.
        latest = min(latest, self.rules.current_date)

        if earliest >= latest:
            return start_date

        return self._random_date_between(earliest, latest)

    # ------------------------------------------------------------------
    # Per-subscription event generation
    # ------------------------------------------------------------------

    def _generate_events_for_subscription(
        self,
        subscription: pd.Series,
        starting_event_counter: int,
    ) -> tuple[list[dict], int]:
        """
        Generate clean event history for one subscription.

        Returns:
            events
            next_event_counter
        """
        event_counter = starting_event_counter
        events: list[dict] = []

        start_date = self._to_date(subscription["contract_start_date"], "contract_start_date")
        end_date = self._to_date(subscription["contract_end_date"], "contract_end_date")

        if start_date is None:
            raise ValueError(
                f"Subscription {subscription['subscription_id']} has no contract_start_date."
            )

        final_mrr_local = float(subscription["mrr_local"])
        final_mrr_gbp = float(subscription["mrr_gbp"])
        final_status = str(subscription["contract_status"])
        term_months = int(subscription["contract_term_months"])
        billing_frequency = str(subscription["billing_frequency"])

        # Zero-value pricing defects can still have a New event with zero value.
        movement_events: list[dict] = []

        # Decide whether this subscription receives commercial movements.
        has_datapulse_reprice = self._should_generate_datapulse_price_increase(subscription)
        has_expansion = self._should_generate_expansion(subscription)
        has_contraction = False if has_expansion else self._should_generate_contraction(subscription)

        # Backsolve opening MRR from final MRR for movement histories.
        opening_mrr_local = final_mrr_local
        opening_mrr_gbp = final_mrr_gbp

        datapulse_multiplier = 1.0
        expansion_multiplier = 1.0
        contraction_multiplier = 1.0

        if has_datapulse_reprice:
            datapulse_multiplier = float(self.rng.uniform(1.08, 1.18))

        if has_expansion:
            expansion_multiplier = float(self.rng.uniform(1.15, 1.45))

        if has_contraction:
            contraction_multiplier = float(self.rng.uniform(0.75, 0.90))

        total_multiplier = datapulse_multiplier * expansion_multiplier * contraction_multiplier

        if total_multiplier > 0:
            opening_mrr_local = self._round_money(final_mrr_local / total_multiplier)
            opening_mrr_gbp = self._round_money(final_mrr_gbp / total_multiplier)

        # 1. Genesis event.
        event_counter += 1
        new_event_id = f"EVT-{event_counter:08d}"

        events.append(
            self._build_event(
                event_id=new_event_id,
                subscription=subscription,
                event_sequence=1,
                event_date=start_date,
                event_type="new",
                event_reason="initial_contract",
                previous_mrr_local=0.00,
                new_mrr_local=opening_mrr_local,
                previous_mrr_gbp=0.00,
                new_mrr_gbp=opening_mrr_gbp,
                is_terminal_event=0,
            )
        )

        current_sequence = 2
        current_mrr_local = opening_mrr_local
        current_mrr_gbp = opening_mrr_gbp

        # 2. Renewal events for annual/term contracts only.
        if billing_frequency == "Annual" and term_months >= 12:
            renewal_date = start_date + relativedelta(months=term_months)

            while renewal_date < self.rules.current_date:
                if end_date and renewal_date >= end_date:
                    break

                event_counter += 1
                renewal_event_id = f"EVT-{event_counter:08d}"

                events.append(
                    self._build_event(
                        event_id=renewal_event_id,
                        subscription=subscription,
                        event_sequence=current_sequence,
                        event_date=renewal_date,
                        event_type="renewal",
                        event_reason="standard_renewal",
                        previous_mrr_local=current_mrr_local,
                        new_mrr_local=current_mrr_local,
                        previous_mrr_gbp=current_mrr_gbp,
                        new_mrr_gbp=current_mrr_gbp,
                        is_terminal_event=0,
                    )
                )

                current_sequence += 1
                renewal_date = renewal_date + relativedelta(months=term_months)

        # 3. DataPulse migration reprice.
        if has_datapulse_reprice:
            reprice_start = max(self.rules.datapulse_reprice_start, start_date + timedelta(days=30))
            reprice_end = min(
                self.rules.datapulse_reprice_end,
                end_date or self.rules.datapulse_reprice_end,
            )

            if reprice_start <= reprice_end:
                new_mrr_local = self._round_money(current_mrr_local * datapulse_multiplier)
                new_mrr_gbp = self._round_money(current_mrr_gbp * datapulse_multiplier)

                event_counter += 1
                price_event_id = f"EVT-{event_counter:08d}"

                events.append(
                    self._build_event(
                        event_id=price_event_id,
                        subscription=subscription,
                        event_sequence=current_sequence,
                        event_date=self._random_date_between(reprice_start, reprice_end),
                        event_type="price_increase",
                        event_reason="datapulse_migration_reprice",
                        previous_mrr_local=current_mrr_local,
                        new_mrr_local=new_mrr_local,
                        previous_mrr_gbp=current_mrr_gbp,
                        new_mrr_gbp=new_mrr_gbp,
                        is_terminal_event=0,
                    )
                )

                current_sequence += 1
                current_mrr_local = new_mrr_local
                current_mrr_gbp = new_mrr_gbp

        # 4. Expansion.
        if has_expansion:
            event_date = self._choose_midterm_event_date(start_date, end_date)

            if event_date > start_date:
                new_mrr_local = self._round_money(current_mrr_local * expansion_multiplier)
                new_mrr_gbp = self._round_money(current_mrr_gbp * expansion_multiplier)

                event_counter += 1
                expansion_event_id = f"EVT-{event_counter:08d}"

                events.append(
                    self._build_event(
                        event_id=expansion_event_id,
                        subscription=subscription,
                        event_sequence=current_sequence,
                        event_date=event_date,
                        event_type="expansion",
                        event_reason=str(
                            self.rng.choice(["seat_expansion", "tier_upgrade"])
                        ),
                        previous_mrr_local=current_mrr_local,
                        new_mrr_local=new_mrr_local,
                        previous_mrr_gbp=current_mrr_gbp,
                        new_mrr_gbp=new_mrr_gbp,
                        is_terminal_event=0,
                    )
                )

                current_sequence += 1
                current_mrr_local = new_mrr_local
                current_mrr_gbp = new_mrr_gbp

        # 5. Contraction.
        if has_contraction:
            event_date = self._choose_midterm_event_date(start_date, end_date)

            if event_date > start_date:
                new_mrr_local = self._round_money(current_mrr_local * contraction_multiplier)
                new_mrr_gbp = self._round_money(current_mrr_gbp * contraction_multiplier)

                event_counter += 1
                contraction_event_id = f"EVT-{event_counter:08d}"

                events.append(
                    self._build_event(
                        event_id=contraction_event_id,
                        subscription=subscription,
                        event_sequence=current_sequence,
                        event_date=event_date,
                        event_type="contraction",
                        event_reason=str(
                            self.rng.choice(["seat_reduction", "downgrade"])
                        ),
                        previous_mrr_local=current_mrr_local,
                        new_mrr_local=new_mrr_local,
                        previous_mrr_gbp=current_mrr_gbp,
                        new_mrr_gbp=new_mrr_gbp,
                        is_terminal_event=0,
                    )
                )

                current_sequence += 1
                current_mrr_local = new_mrr_local
                current_mrr_gbp = new_mrr_gbp

        # 6. Terminal events.
        if final_status == "Churned":
            terminal_date = end_date or self.rules.current_date

            event_counter += 1
            churn_event_id = f"EVT-{event_counter:08d}"

            events.append(
                self._build_event(
                    event_id=churn_event_id,
                    subscription=subscription,
                    event_sequence=current_sequence,
                    event_date=terminal_date,
                    event_type="churn",
                    event_reason="customer_churn",
                    previous_mrr_local=current_mrr_local,
                    new_mrr_local=0.00,
                    previous_mrr_gbp=current_mrr_gbp,
                    new_mrr_gbp=0.00,
                    is_terminal_event=1,
                )
            )

        elif final_status == "Paused":
            terminal_date = end_date or self.rules.current_date

            event_counter += 1
            pause_event_id = f"EVT-{event_counter:08d}"

            events.append(
                self._build_event(
                    event_id=pause_event_id,
                    subscription=subscription,
                    event_sequence=current_sequence,
                    event_date=terminal_date,
                    event_type="pause",
                    event_reason="billing_pause",
                    previous_mrr_local=current_mrr_local,
                    new_mrr_local=0.00,
                    previous_mrr_gbp=current_mrr_gbp,
                    new_mrr_gbp=0.00,
                    is_terminal_event=1,
                )
            )

        # Sort and replay the generated timeline so MRR state carries forward correctly.
        events = self._replay_subscription_timeline(events)

        return events, event_counter

    # ------------------------------------------------------------------
    # Defect injection
    # ------------------------------------------------------------------

    def _inject_defects(
        self,
        df: pd.DataFrame,
        subscriptions_df: pd.DataFrame,
        starting_event_counter: int,
    ) -> pd.DataFrame:
        """Inject controlled synthetic defects into the event stream."""
        if df.empty:
            return df

        output_df = df.copy()

        clean_mask = ~output_df["is_defect_flag"].astype(bool)

        # 1. Math mismatch: alter arr_delta_gbp only.
        math_sample_size = max(1, int(len(output_df) * self.defect_rates.math_mismatch))
        math_candidates = output_df[clean_mask].sample(
            n=min(math_sample_size, clean_mask.sum()),
            random_state=self.seed + 701,
        ).index

        output_df.loc[math_candidates, "arr_delta_gbp"] = (
            output_df.loc[math_candidates, "arr_delta_gbp"] + 100.00
        )
        output_df.loc[math_candidates, "is_defect_flag"] = True
        output_df.loc[math_candidates, "defect_type"] = "MATH_MISMATCH"

        # 2. Chronology violation: move event before its subscription start.
        clean_mask = ~output_df["is_defect_flag"].astype(bool)
        chronology_sample_size = max(1, int(len(output_df) * self.defect_rates.chronology_violation))

        chronology_candidates = output_df[
            clean_mask & output_df["event_type"].isin(["renewal", "expansion", "contraction", "price_increase"])
        ].sample(
            n=min(
                chronology_sample_size,
                len(output_df[
                    clean_mask & output_df["event_type"].isin(["renewal", "expansion", "contraction", "price_increase"])
                ]),
            ),
            random_state=self.seed + 702,
        ).index

        subscription_starts = subscriptions_df.set_index("subscription_id")["contract_start_date"]

        for index in chronology_candidates:
            subscription_id = output_df.at[index, "subscription_id"]
            start_date = pd.to_datetime(subscription_starts.loc[subscription_id]).date()
            bad_date = start_date - timedelta(days=int(self.rng.integers(15, 120)))

            output_df.at[index, "event_date"] = bad_date.isoformat()
            output_df.at[index, "is_defect_flag"] = True
            output_df.at[index, "defect_type"] = "CHRONOLOGY_VIOLATION"

        # 3. Terminal event not zeroed.
        clean_mask = ~output_df["is_defect_flag"].astype(bool)
        terminal_candidates_df = output_df[
            clean_mask & output_df["event_type"].isin(["churn", "pause"])
        ]

        terminal_sample_size = int(len(output_df) * self.defect_rates.terminal_event_not_zeroed)

        if terminal_sample_size > 0 and not terminal_candidates_df.empty:
            terminal_candidates = terminal_candidates_df.sample(
                n=min(terminal_sample_size, len(terminal_candidates_df)),
                random_state=self.seed + 703,
            ).index

            for index in terminal_candidates:
                previous_mrr_local = float(output_df.at[index, "previous_mrr_local"])
                previous_mrr_gbp = float(output_df.at[index, "previous_mrr_gbp"])

                output_df.at[index, "new_mrr_local"] = round(previous_mrr_local * 0.20, 2)
                output_df.at[index, "new_mrr_gbp"] = round(previous_mrr_gbp * 0.20, 2)
                output_df.at[index, "new_arr_local"] = round(float(output_df.at[index, "new_mrr_local"]) * 12, 2)
                output_df.at[index, "new_arr_gbp"] = round(float(output_df.at[index, "new_mrr_gbp"]) * 12, 2)
                output_df.at[index, "mrr_delta_local"] = round(
                    float(output_df.at[index, "new_mrr_local"]) - previous_mrr_local,
                    2,
                )
                output_df.at[index, "mrr_delta_gbp"] = round(
                    float(output_df.at[index, "new_mrr_gbp"]) - previous_mrr_gbp,
                    2,
                )
                output_df.at[index, "arr_delta_local"] = round(
                    float(output_df.at[index, "new_arr_local"]) - float(output_df.at[index, "previous_arr_local"]),
                    2,
                )
                output_df.at[index, "arr_delta_gbp"] = round(
                    float(output_df.at[index, "new_arr_gbp"]) - float(output_df.at[index, "previous_arr_gbp"]),
                    2,
                )
                output_df.at[index, "is_defect_flag"] = True
                output_df.at[index, "defect_type"] = "TERMINAL_EVENT_NOT_ZEROED"

        # 4. Ghost event: append event with unknown subscription_id.
        ghost_count = max(1, int(len(output_df) * self.defect_rates.ghost_event))

        ghost_source = output_df[~output_df["is_defect_flag"].astype(bool)].sample(
            n=min(ghost_count, len(output_df[~output_df["is_defect_flag"].astype(bool)])),
            random_state=self.seed + 704,
        )

        ghost_records: list[dict] = []
        event_counter = starting_event_counter

        for _, source_event in ghost_source.iterrows():
            event_counter += 1
            ghost_event_id = f"EVT-{event_counter:08d}"
            ghost_record = source_event.to_dict()
            ghost_record.update(
                {
                    "event_pk": self._generate_pk(ghost_event_id),
                    "event_id": ghost_event_id,
                    "subscription_id": f"SUB-GHOST-{event_counter:06d}",
                    "is_defect_flag": True,
                    "defect_type": "GHOST_EVENT",
                }
            )
            ghost_records.append(ghost_record)

        if ghost_records:
            output_df = pd.concat(
                [output_df, pd.DataFrame(ghost_records)],
                ignore_index=True,
            )

        return output_df

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def generate(self) -> pd.DataFrame:
        """Generate subscription event stream."""
        logger.info("Generating Billing Subscription Events...")

        subscriptions_df = self._load_subscriptions()

        records: list[dict] = []
        event_counter = 0

        for _, subscription in subscriptions_df.iterrows():
            subscription_events, event_counter = self._generate_events_for_subscription(
                subscription=subscription,
                starting_event_counter=event_counter,
            )
            records.extend(subscription_events)

        df = pd.DataFrame(records)

        df = self._inject_defects(
            df=df,
            subscriptions_df=subscriptions_df,
            starting_event_counter=event_counter,
        )

        df = self._finalise_dataframe(df)

        self._validate_output(df=df, subscriptions_df=subscriptions_df)
        self._log_output_review(df=df, subscriptions_df=subscriptions_df)

        logger.info("Generated %s subscription event records.", f"{len(df):,}")

        return df

    @staticmethod
    def _finalise_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Apply final column order and stable sorting."""
        expected_columns = [
            "event_pk",
            "event_id",
            "subscription_id",
            "customer_id",
            "event_sequence",
            "event_date",
            "event_type",
            "event_reason",
            "previous_mrr_local",
            "new_mrr_local",
            "mrr_delta_local",
            "previous_mrr_gbp",
            "new_mrr_gbp",
            "mrr_delta_gbp",
            "previous_arr_local",
            "new_arr_local",
            "arr_delta_local",
            "previous_arr_gbp",
            "new_arr_gbp",
            "arr_delta_gbp",
            "currency",
            "source_system",
            "is_terminal_event",
            "is_defect_flag",
            "defect_type",
            "created_at",
            "updated_at",
        ]

        for column in expected_columns:
            if column not in df.columns:
                df[column] = None

        df = df[expected_columns].copy()

        df = df.sort_values(
            ["subscription_id", "event_sequence", "event_date", "event_id"]
        ).reset_index(drop=True)

        return df

    # ------------------------------------------------------------------
    # Validation and logging
    # ------------------------------------------------------------------

    def _validate_clean_timeline_continuity(self, df: pd.DataFrame) -> None:
        """
        Validate that fully clean event timelines carry MRR forward correctly.

        Important
        ---------
        If a subscription has any defective event, we exclude the whole subscription
        timeline from this continuity validation.

        Reason:
        A defective expansion/contraction/price_increase row may legitimately sit
        between two otherwise clean rows. If we remove only the defective row, the
        remaining clean rows can appear to break continuity even though the full
        generated timeline was internally coherent before defect injection.
        """
        working_df = df.copy()

        working_df["is_defect_flag"] = working_df["is_defect_flag"].astype(bool)

        # Exclude ghost subscriptions completely.
        working_df = working_df[
            ~working_df["subscription_id"].astype(str).str.startswith("SUB-GHOST")
        ].copy()

        # Identify subscriptions with any defect event.
        defective_subscription_ids = set(
            working_df.loc[
                working_df["is_defect_flag"],
                "subscription_id",
            ].astype(str)
        )

        # Validate only subscriptions with fully clean timelines.
        clean_df = working_df[
            ~working_df["subscription_id"].astype(str).isin(defective_subscription_ids)
        ].copy()

        if clean_df.empty:
            logger.warning(
                "No fully clean subscription timelines available for continuity validation."
            )
            return

        clean_df["event_date"] = pd.to_datetime(clean_df["event_date"], errors="coerce")

        clean_df = clean_df.sort_values(
            ["subscription_id", "event_sequence", "event_date", "event_id"]
        )

        clean_df["prior_new_mrr_gbp"] = (
            clean_df.groupby("subscription_id")["new_mrr_gbp"].shift(1)
        )
        clean_df["prior_new_mrr_local"] = (
            clean_df.groupby("subscription_id")["new_mrr_local"].shift(1)
        )

        gbp_continuity_breaks = clean_df[
            clean_df["prior_new_mrr_gbp"].notna()
            & (
                (clean_df["previous_mrr_gbp"] - clean_df["prior_new_mrr_gbp"]).abs()
                > 0.05
            )
        ]

        local_continuity_breaks = clean_df[
            clean_df["prior_new_mrr_local"].notna()
            & (
                (clean_df["previous_mrr_local"] - clean_df["prior_new_mrr_local"]).abs()
                > 0.05
            )
        ]

        if not gbp_continuity_breaks.empty or not local_continuity_breaks.empty:
            raise ValueError(
                "Fully clean subscription event timeline continuity check failed. "
                f"GBP breaks: {len(gbp_continuity_breaks):,}; "
                f"Local breaks: {len(local_continuity_breaks):,}."
            )

        logger.info(
            "Clean timeline continuity validation passed for %s fully clean subscriptions.",
            f"{clean_df['subscription_id'].nunique():,}",
        )
    
    def _validate_output(
        self,
        df: pd.DataFrame,
        subscriptions_df: pd.DataFrame,
    ) -> None:
        """Validate output structure while allowing intentional defects."""
        if df.empty:
            raise ValueError("No subscription event records generated.")

        if df["event_id"].duplicated().any():
            duplicate_count = int(df["event_id"].duplicated().sum())
            raise ValueError(f"Duplicate event_id values found: {duplicate_count:,}")

        if df["event_pk"].duplicated().any():
            duplicate_count = int(df["event_pk"].duplicated().sum())
            raise ValueError(f"Duplicate event_pk values found: {duplicate_count:,}")

        invalid_event_types = set(df["event_type"].dropna().unique()).difference(
            self.VALID_EVENT_TYPES
        )

        if invalid_event_types:
            raise ValueError(f"Invalid event_type values found: {sorted(invalid_event_types)}")

        for column in [
            "previous_mrr_local",
            "new_mrr_local",
            "mrr_delta_local",
            "previous_mrr_gbp",
            "new_mrr_gbp",
            "mrr_delta_gbp",
            "previous_arr_local",
            "new_arr_local",
            "arr_delta_local",
            "previous_arr_gbp",
            "new_arr_gbp",
            "arr_delta_gbp",
        ]:
            if pd.to_numeric(df[column], errors="coerce").isna().any():
                raise ValueError(f"Invalid numeric values found in {column}.")

        valid_subscription_ids = set(subscriptions_df["subscription_id"].astype(str))
        unknown_subscription_rows = ~df["subscription_id"].astype(str).isin(valid_subscription_ids)

        unknown_non_defect = unknown_subscription_rows & ~df["defect_type"].eq("GHOST_EVENT")

        if unknown_non_defect.any():
            bad_count = int(unknown_non_defect.sum())
            raise ValueError(
                f"Unknown subscription_id values found outside GHOST_EVENT defects: {bad_count:,}"
            )
        
        self._validate_clean_timeline_continuity(df)

        logger.info("Subscription event output structural validation passed.")

    def _log_output_review(
        self,
        df: pd.DataFrame,
        subscriptions_df: pd.DataFrame,
    ) -> None:
        """Log useful QA summaries for manual review."""
        logger.info("----- Billing Subscription Events Review -----")
        logger.info("Subscription master rows: %s", f"{len(subscriptions_df):,}")
        logger.info("Event rows: %s", f"{len(df):,}")
        logger.info(
            "Average events per subscription: %.2f",
            len(df) / len(subscriptions_df) if len(subscriptions_df) else 0,
        )

        logger.info(
            "Event type counts:\n%s",
            df["event_type"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Event reason counts:\n%s",
            df["event_reason"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "Defect type counts:\n%s",
            df["defect_type"].value_counts(dropna=False).to_string(),
        )

        logger.info(
            "ARR delta GBP by event type:\n%s",
            df.groupby("event_type")["arr_delta_gbp"].sum().round(2).to_string(),
        )

        clean_df = df[~df["is_defect_flag"].astype(bool)].copy()

        logger.info(
            "Clean ARR delta GBP by event type:\n%s",
            clean_df.groupby("event_type")["arr_delta_gbp"].sum().round(2).to_string(),
        )

        terminal_events = df[df["event_type"].isin(["churn", "pause"])]

        logger.info("Terminal event rows: %s", f"{len(terminal_events):,}")
        logger.info("----------------------------------------------")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(self, df: pd.DataFrame) -> Path:
        """Save subscription events to raw billing folder."""
        output_dir = get_raw_data_path("billing")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / self.output_filename
        df.to_csv(output_path, index=False)

        logger.info("Subscription events saved to %s", output_path)

        return output_path


def main() -> None:
    generator = SubscriptionEventsGenerator()
    events_df = generator.generate()
    generator.save(events_df)


if __name__ == "__main__":
    main()