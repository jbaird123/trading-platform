# Validates: [PM-5.5]
"""Tests for position sizing strategies."""

from __future__ import annotations

import pytest
from trading_platform.portfolio.position_sizing import (
    FixedRatioPositionSizer,
    FixedSizePositionSizer,
    PositionSizer,
)


class TestFixedSizePositionSizer:
    """Tests for the FixedSizePositionSizer class."""

    def test_returns_fixed_size_regardless_of_equity(self):
        """Fixed sizer should return same size regardless of equity changes."""
        sizer = FixedSizePositionSizer(size=2.0)
        contract_size = 10000.0

        result1 = sizer.calculate_size(
            current_equity=100000.0,
            initial_equity=100000.0,
            contract_size=contract_size,
        )
        assert result1.contracts == 2.0
        assert result1.units == 20000.0
        assert result1.method == "fixed"

        # After profits
        result2 = sizer.calculate_size(
            current_equity=150000.0,
            initial_equity=100000.0,
            contract_size=contract_size,
        )
        assert result2.contracts == 2.0
        assert result2.units == 20000.0

        # After losses
        result3 = sizer.calculate_size(
            current_equity=50000.0,
            initial_equity=100000.0,
            contract_size=contract_size,
        )
        assert result3.contracts == 2.0
        assert result3.units == 20000.0

    def test_rejects_non_positive_size(self):
        """Fixed sizer should reject zero or negative sizes."""
        with pytest.raises(ValueError, match="positive"):
            FixedSizePositionSizer(size=0.0)
        with pytest.raises(ValueError, match="positive"):
            FixedSizePositionSizer(size=-1.0)

    def test_to_dict_serialization(self):
        """Fixed sizer should serialize correctly."""
        sizer = FixedSizePositionSizer(size=3.0)
        config = sizer.to_dict()
        assert config == {"method": "fixed", "size": 3.0}


class TestFixedRatioPositionSizer:
    """Tests for the FixedRatioPositionSizer class (Ryan Jones method)."""

    def test_initial_contracts_at_zero_profit(self):
        """Should return initial_contracts when profit is zero."""
        sizer = FixedRatioPositionSizer(delta=500.0, initial_contracts=1)
        result = sizer.calculate_size(
            current_equity=100000.0,
            initial_equity=100000.0,
            contract_size=10000.0,
        )
        assert result.contracts == 1.0
        assert result.units == 10000.0
        assert result.method == "fixed_ratio"

    def test_scales_up_with_profit(self):
        """Should increase contracts as profit accumulates."""
        sizer = FixedRatioPositionSizer(delta=500.0, initial_contracts=1)
        contract_size = 10000.0

        # At $0 profit: 1 contract
        result0 = sizer.calculate_size(100000.0, 100000.0, contract_size)
        assert result0.contracts == pytest.approx(1.0)

        # Formula: N = 0.5 × [(1 + 8 × P / delta)^0.5 + 1]
        # At $500 profit: N = 0.5 × [(1 + 8*500/500)^0.5 + 1] = 0.5 × [3 + 1] = 2
        result500 = sizer.calculate_size(100500.0, 100000.0, contract_size)
        assert result500.contracts == pytest.approx(2.0)

        # At $1500 profit: N = 0.5 × [(1 + 8*1500/500)^0.5 + 1] = 0.5 × [5 + 1] = 3
        result1500 = sizer.calculate_size(101500.0, 100000.0, contract_size)
        assert result1500.contracts == pytest.approx(3.0)

        # At $3000 profit: N = 0.5 × [(1 + 8*3000/500)^0.5 + 1] = 0.5 × [7 + 1] = 4
        result3000 = sizer.calculate_size(103000.0, 100000.0, contract_size)
        assert result3000.contracts == pytest.approx(4.0)

    def test_fixed_ratio_formula_verification(self):
        """Verify the Fixed Ratio formula matches Ryan Jones's book."""
        delta = 1000.0
        sizer = FixedRatioPositionSizer(delta=delta, initial_contracts=1)

        # Test several profit levels manually
        test_cases = [
            (0, 1.0),  # 0 profit = 1 contract
            (1000, 2.0),  # P=delta: N = 0.5 × [√9 + 1] = 2
            (3000, 3.0),  # P=3×delta: N = 0.5 × [√25 + 1] = 3
            (6000, 4.0),  # P=6×delta: N = 0.5 × [√49 + 1] = 4
            (10000, 5.0),  # P=10×delta: N = 0.5 × [√81 + 1] = 5
        ]

        for profit, expected_contracts in test_cases:
            result = sizer.calculate_size(
                current_equity=100000.0 + profit,
                initial_equity=100000.0,
                contract_size=1.0,  # Use 1.0 to see raw contract count
            )
            assert result.contracts == pytest.approx(
                expected_contracts
            ), f"At profit={profit}, expected {expected_contracts} contracts"

    def test_scales_down_during_drawdown(self):
        """Should decrease contracts during drawdown."""
        sizer = FixedRatioPositionSizer(delta=500.0, initial_contracts=1)

        # First scale up to 3 contracts
        _ = sizer.calculate_size(101500.0, 100000.0, 1.0)

        # Now draw down - should scale back
        result_dd = sizer.calculate_size(100500.0, 100000.0, 1.0)
        # During drawdown, contracts should be reduced
        assert result_dd.contracts < 3.0
        assert result_dd.contracts >= 1.0

    def test_delta_fraction_accelerates_drawdown_scaling(self):
        """delta_fraction should make scale-down faster during drawdown."""
        # Sizer without delta_fraction
        sizer_no_frac = FixedRatioPositionSizer(delta=1000.0, initial_contracts=1)

        # Sizer with delta_fraction=0.5 (scale down twice as fast)
        sizer_with_frac = FixedRatioPositionSizer(
            delta=1000.0, initial_contracts=1, delta_fraction=0.5
        )

        # Build up to 3 contracts
        sizer_no_frac.calculate_size(103000.0, 100000.0, 1.0)
        sizer_with_frac.calculate_size(103000.0, 100000.0, 1.0)

        # Now enter drawdown (back to $500 profit from $3000)
        result_no_frac = sizer_no_frac.calculate_size(100500.0, 100000.0, 1.0)
        result_with_frac = sizer_with_frac.calculate_size(100500.0, 100000.0, 1.0)

        # With delta_fraction, should scale down more aggressively
        assert result_with_frac.contracts <= result_no_frac.contracts

    def test_never_goes_below_initial_contracts(self):
        """Should never return fewer than initial_contracts."""
        sizer = FixedRatioPositionSizer(delta=500.0, initial_contracts=2)

        # Even with losses, should not go below 2
        result = sizer.calculate_size(50000.0, 100000.0, 1.0)
        assert result.contracts >= 2.0

    def test_rejects_invalid_delta(self):
        """Should reject non-positive delta."""
        with pytest.raises(ValueError, match="positive"):
            FixedRatioPositionSizer(delta=0.0)
        with pytest.raises(ValueError, match="positive"):
            FixedRatioPositionSizer(delta=-100.0)

    def test_rejects_invalid_initial_contracts(self):
        """Should reject initial_contracts less than 1."""
        with pytest.raises(ValueError, match="at least 1"):
            FixedRatioPositionSizer(delta=500.0, initial_contracts=0)

    def test_rejects_invalid_delta_fraction(self):
        """Should reject delta_fraction outside (0, 1] range."""
        with pytest.raises(ValueError, match="delta_fraction"):
            FixedRatioPositionSizer(delta=500.0, delta_fraction=0.0)
        with pytest.raises(ValueError, match="delta_fraction"):
            FixedRatioPositionSizer(delta=500.0, delta_fraction=1.5)
        with pytest.raises(ValueError, match="delta_fraction"):
            FixedRatioPositionSizer(delta=500.0, delta_fraction=-0.5)

    def test_to_dict_serialization(self):
        """Fixed ratio sizer should serialize correctly."""
        sizer = FixedRatioPositionSizer(
            delta=1000.0, initial_contracts=2, delta_fraction=0.5
        )
        config = sizer.to_dict()
        assert config == {
            "method": "fixed_ratio",
            "delta": 1000.0,
            "initial_contracts": 2,
            "delta_fraction": 0.5,
        }

    def test_to_dict_without_delta_fraction(self):
        """Serialization should omit delta_fraction if not set."""
        sizer = FixedRatioPositionSizer(delta=500.0)
        config = sizer.to_dict()
        assert "delta_fraction" not in config

    def test_reset_high_water_mark(self):
        """reset_high_water_mark should reset tracking state."""
        sizer = FixedRatioPositionSizer(delta=500.0, initial_contracts=1)

        # Build up
        _ = sizer.calculate_size(101500.0, 100000.0, 1.0)

        # Reset
        sizer.reset_high_water_mark()

        # Should behave like fresh start
        result = sizer.calculate_size(100000.0, 100000.0, 1.0)
        assert result.contracts == 1.0


class TestPositionSizerFactory:
    """Tests for the PositionSizer.from_config() factory method."""

    def test_creates_fixed_sizer_from_config(self):
        """Should create FixedSizePositionSizer from config."""
        config = {"method": "fixed", "size": 2.5}
        sizer = PositionSizer.from_config(config)
        assert isinstance(sizer, FixedSizePositionSizer)
        result = sizer.calculate_size(100000.0, 100000.0, 1.0)
        assert result.contracts == 2.5

    def test_creates_fixed_sizer_with_default_size(self):
        """Should use default size=1.0 if not specified."""
        config = {"method": "fixed"}
        sizer = PositionSizer.from_config(config)
        result = sizer.calculate_size(100000.0, 100000.0, 1.0)
        assert result.contracts == 1.0

    def test_creates_fixed_ratio_sizer_from_config(self):
        """Should create FixedRatioPositionSizer from config."""
        config = {
            "method": "fixed_ratio",
            "delta": 500.0,
            "initial_contracts": 2,
            "delta_fraction": 0.75,
        }
        sizer = PositionSizer.from_config(config)
        assert isinstance(sizer, FixedRatioPositionSizer)

    def test_fixed_ratio_requires_delta(self):
        """Should raise ValueError if delta is missing for fixed_ratio."""
        config = {"method": "fixed_ratio"}
        with pytest.raises(ValueError, match="delta"):
            PositionSizer.from_config(config)

    def test_defaults_to_fixed_method(self):
        """Should default to 'fixed' method if not specified."""
        config = {"size": 3.0}
        sizer = PositionSizer.from_config(config)
        assert isinstance(sizer, FixedSizePositionSizer)

    def test_rejects_unknown_method(self):
        """Should raise ValueError for unknown method."""
        config = {"method": "kelly_criterion"}
        with pytest.raises(ValueError, match="Unknown.*kelly_criterion"):
            PositionSizer.from_config(config)


class TestContractSizeMultiplier:
    """Tests for contract_size as a multiplier for position units."""

    def test_fixed_sizer_applies_contract_size(self):
        """Fixed sizer should multiply contracts by contract_size."""
        sizer = FixedSizePositionSizer(size=2.0)

        # Mini lot
        result_mini = sizer.calculate_size(100000.0, 100000.0, 10000.0)
        assert result_mini.contracts == 2.0
        assert result_mini.units == 20000.0

        # Standard lot
        result_standard = sizer.calculate_size(100000.0, 100000.0, 100000.0)
        assert result_standard.contracts == 2.0
        assert result_standard.units == 200000.0

        # Micro lot
        result_micro = sizer.calculate_size(100000.0, 100000.0, 1000.0)
        assert result_micro.contracts == 2.0
        assert result_micro.units == 2000.0

    def test_fixed_ratio_applies_contract_size(self):
        """Fixed ratio sizer should multiply contracts by contract_size."""
        sizer = FixedRatioPositionSizer(delta=1000.0, initial_contracts=1)

        # At $1000 profit = 2 contracts
        # Mini lot (10000 units per contract)
        result_mini = sizer.calculate_size(101000.0, 100000.0, 10000.0)
        assert result_mini.contracts == pytest.approx(2.0)
        assert result_mini.units == pytest.approx(20000.0)

        # Standard lot (100000 units per contract)
        result_standard = sizer.calculate_size(101000.0, 100000.0, 100000.0)
        assert result_standard.contracts == pytest.approx(2.0)
        assert result_standard.units == pytest.approx(200000.0)
