from typing import List, Union

from river.base.typing import ClfTarget
from river.stats import RollingMean

from streamselect.concept_representations import ConceptRepresentation

from .meta_feature_distributions import SingleValueDistribution


class ErrorRateRepresentation(ConceptRepresentation):
    """A concept representation which represents a concept
    using the error rate of a given classifier over a recent window of size w.
    With zero observations, we default to an error rate of 0.0 to represent maximum performance.
    This is a common (implied) comparison target when testing error_rate."""

    def __init__(self, window_size: int):
        super().__init__()
        self.recent_error_rate = RollingMean(window_size)
        self.values = [0.0]
        self.distribution = [SingleValueDistribution()]

    def learn_one(self, x: dict, y: ClfTarget, p: Union[ClfTarget, None] = None) -> None:
        self.recent_error_rate.update(1 if p != y else 0)
        avg_error_rate = self.recent_error_rate.get()
        self.values[0] = avg_error_rate
        self.distribution[0].learn_one(avg_error_rate)

    def predict_one(self, x: dict, p: Union[ClfTarget, None] = None) -> None:
        pass

    def get_values(self) -> List:
        return self.values
