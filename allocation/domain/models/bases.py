from pydamain.domain import models  # type: ignore
from pydamain.domain.models import field  # type: ignore


class ValueObject(models.ValueObject):
    ...


class Entity(models.Entity):
    ...


class Aggregate(models.Aggregate):
    version_number: int = field(default=0, init=False)
