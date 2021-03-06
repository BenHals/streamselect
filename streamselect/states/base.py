""" Base state class"""
from __future__ import annotations

from typing import Callable

from river import utils
from river.base import Classifier
from river.base.typing import ClfTarget

from streamselect.concept_representations import ConceptRepresentation
from streamselect.utils import Observation


class State:  # pylint: disable=too-few-public-methods
    """A base state containing a Classifier and ConceptRepresentation"""

    def __init__(
        self,
        classifier: Classifier,
        representation_constructor: Callable[[int], ConceptRepresentation],
        state_id: int = -1,
        train_representation: bool = True,
    ) -> None:
        self.state_id = state_id
        self.classifier = classifier
        self.representation_constructor = representation_constructor
        # Mapping between concept ids and representations using  self.classifier.
        self.concept_representation: dict[int, ConceptRepresentation] = {
            self.state_id: self.representation_constructor(self.state_id)
        }
        self.train_representation = train_representation

        self.seen_weight = 0.0
        self.active_seen_weight = 0.0
        self.weight_since_last_active = 0.0
        self.last_trained_active_timestep = -1.0

    def learn_one(self, supervised_observation: Observation, force_train_classifier: bool = False) -> State:
        """Train the classifier and concept representation.
        concept_id determines the concept the observation is thought to be drawn from.
        The state classifier is NOT trained on observations with a concept_id which does not match
        the state_id unless force_train_classifier is set, however other statistics are updated.

        Parameters
        ----------

        supervised_observation: Observation
            The observation to train on. Must be supervised, i.e., have a valid y value.
            The prediction on the observation is not used, but a new one is added to ensure
            that the most up to date predictions are used.

        force_train_classifier: bool
            Default: False
            Forces the state classifier to train on an observation regardless of which concept_id
            the observation is from. When false, only observations with with an active_state_id
            matching the state_id are used to train the classifier.

        """
        concept_id = supervised_observation.active_state_id if not force_train_classifier else self.state_id
        if self.train_representation:
            representation = self.concept_representation.setdefault(
                concept_id, self.representation_constructor(self.state_id)
            )
            # Make a prediction without training statistics,
            # to avoid training twice.
            with utils.pure_inference_mode():
                p = self.classifier.predict_one(supervised_observation.x)
                supervised_observation.add_prediction(p, self.state_id)
            representation.learn_one(supervised_observation)

        # We only train the classifier on data from the associated concept.
        if concept_id != self.state_id:
            return self

        # We only train the classifier on data from the associated concept.
        if supervised_observation.y is None:
            raise ValueError("Attempting to train on unsupervised observation. ")

        # Some classifiers cannot take sample_weight.
        # Try/except to avoid branching
        try:
            self.classifier.learn_one(
                x=supervised_observation.x,
                y=supervised_observation.y,
                sample_weight=supervised_observation.sample_weight,
            )
        except TypeError:
            self.classifier.learn_one(x=supervised_observation.x, y=supervised_observation.y)

        self.last_trained_active_timestep = supervised_observation.seen_at
        return self

    def predict_one(
        self, unsupervised_observation: Observation, force_train_own_representation: bool = False
    ) -> ClfTarget:
        """Make a prediction using the state classifier.
        Also trains unsupervised components of the classifier and concept representation.

        Parameters
        ----------

        unsupervised_observation: Observation
            An unsupervised observation, may have a None y.
            Predictions for the state_id will be added to observation.predictions.

        force_train_own_representation: Bool
            Default: False
            Forces the state to train the concept_representation representing data with the current state_id.
            If false, we train the representation representing the active_state_id associated with the observation.
        """
        p = self.classifier.predict_one(unsupervised_observation.x)
        unsupervised_observation.add_prediction(p, self.state_id)
        if self.train_representation:
            concept_id = (
                unsupervised_observation.active_state_id if not force_train_own_representation else self.state_id
            )
            representation = self.concept_representation.setdefault(
                concept_id, self.representation_constructor(self.state_id)
            )
            representation.predict_one(unsupervised_observation)
        return p

    def step(self, sample_weight: float = 1.0, is_active: bool = True) -> None:
        """Step states tracking statistics"""
        self.seen_weight += sample_weight
        self.weight_since_last_active += sample_weight
        if is_active:
            self.active_seen_weight += sample_weight
            self.weight_since_last_active = 0

    def get_self_representation(self) -> ConceptRepresentation:
        """Get the concept representation using this states classifier,
        on data drawn from this concept."""
        return self.concept_representation[self.state_id]

    def deactivate_train_representation(self) -> None:
        """Deactivate training representation.
        Some representations are not trained, e.g., implied error rate."""
        self.train_representation = False
