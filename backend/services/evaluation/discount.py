from __future__ import annotations

from libs.schemas.base import DimScores, Discount, MetacogDimension, ScaffoldLevel


class DiscountPolicy:
    def build(self, scaffold_level: ScaffoldLevel | None) -> list[Discount]:
        if scaffold_level is None or scaffold_level == ScaffoldLevel.L1:
            return []
        if scaffold_level == ScaffoldLevel.L2:
            return [
                Discount(
                    reason="scaffold_l2_support",
                    dimension=MetacogDimension.MONITOR,
                    multiplier=0.9,
                ),
                Discount(
                    reason="scaffold_l2_support",
                    dimension=MetacogDimension.EVALUATE,
                    multiplier=0.9,
                ),
            ]
        return [
            Discount(
                reason="scaffold_l3_support",
                dimension=MetacogDimension.PLAN,
                multiplier=0.8,
            ),
            Discount(
                reason="scaffold_l3_support",
                dimension=MetacogDimension.MONITOR,
                multiplier=0.75,
            ),
            Discount(
                reason="scaffold_l3_support",
                dimension=MetacogDimension.EVALUATE,
                multiplier=0.75,
            ),
        ]

    def apply(self, scores: DimScores, discounts: list[Discount]) -> DimScores:
        factors = {
            MetacogDimension.PLAN: 1.0,
            MetacogDimension.MONITOR: 1.0,
            MetacogDimension.EVALUATE: 1.0,
            MetacogDimension.ADAPT: 1.0,
        }
        for discount in discounts:
            factors[discount.dimension] *= discount.multiplier
        return DimScores(
            plan=round(scores.plan * factors[MetacogDimension.PLAN], 2),
            monitor=round(scores.monitor * factors[MetacogDimension.MONITOR], 2),
            evaluate=round(scores.evaluate * factors[MetacogDimension.EVALUATE], 2),
            adapt=round(scores.adapt * factors[MetacogDimension.ADAPT], 2),
        )
