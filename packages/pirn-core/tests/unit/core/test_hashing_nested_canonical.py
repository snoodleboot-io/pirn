"""``content_hash`` honours ``__pirn_canonical__`` inside pydantic models (PIR-848).

``model_dump`` serialises a nested opaque value through its audit form. For a
connector that is a per-class constant, so a model literal such as
``Settings(connector=b)`` hashed equal to ``Settings(connector=a)`` and replay
served a's recording. These tests pin that the hook is reached in every field
shape a model can hold, that models without a hook hash exactly as before, and
that the audit (``model_dump``) output is unchanged.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel

from pirn.connectors.connector_base import ConnectorBase
from pirn.core.hashing import _canonicalise, content_hash


class Endpoint(ConnectorBase):
    """A connector whose audit form is the constant ``ConnectorBase`` dict."""

    def __init__(self, *, url: str) -> None:
        super().__init__()
        self.url = url


class Canonical:
    """A plain object with a content-controlled canonical form."""

    def __init__(self, label: str) -> None:
        self.label = label

    def __pirn_canonical__(self) -> dict[str, str]:
        return {"label": self.label}


class TypedField(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    connector: Endpoint


class AnyField(BaseModel):
    value: Any


class ListField(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    connectors: list[Endpoint]


class TupleField(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    pair: tuple[Endpoint, int]


class DictField(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    by_name: dict[str, Endpoint]


class Outer(BaseModel):
    inner: TypedField
    label: str


class AliasedField(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, serialize_by_alias=True)

    connector: Endpoint = Field(serialization_alias="conn")


class ExcludedField(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    connector: Endpoint = Field(exclude=True)
    label: str


class ExtraAllowed(BaseModel):
    model_config = ConfigDict(extra="allow")


class MixedAnyList(BaseModel):
    items: list[Any]


class EndpointRoot(RootModel[Any]):
    pass


class PlainModel(BaseModel):
    name: str
    when: dt.datetime
    tags: list[str]


def test_typed_connector_field_hashes_by_the_connector() -> None:
    # Arrange
    first = TypedField(connector=Endpoint(url="https://a"))
    second = TypedField(connector=Endpoint(url="https://b"))

    # Act
    hashes = {content_hash(first), content_hash(second)}

    # Assert
    assert len(hashes) == 2


def test_any_field_holding_a_connector_hashes_by_the_connector() -> None:
    # Arrange
    first = AnyField(value=Endpoint(url="https://a"))
    second = AnyField(value=Endpoint(url="https://b"))

    # Act
    hashes = {content_hash(first), content_hash(second)}

    # Assert
    assert len(hashes) == 2


def test_list_field_of_connectors_hashes_by_the_connectors() -> None:
    # Arrange
    first = ListField(connectors=[Endpoint(url="https://a")])
    second = ListField(connectors=[Endpoint(url="https://b")])

    # Act
    hashes = {content_hash(first), content_hash(second)}

    # Assert
    assert len(hashes) == 2


def test_tuple_field_holding_a_connector_hashes_by_the_connector() -> None:
    # Arrange
    first = TupleField(pair=(Endpoint(url="https://a"), 1))
    second = TupleField(pair=(Endpoint(url="https://b"), 1))

    # Act
    hashes = {content_hash(first), content_hash(second)}

    # Assert
    assert len(hashes) == 2


def test_dict_field_of_connectors_hashes_by_the_connectors() -> None:
    # Arrange
    first = DictField(by_name={"primary": Endpoint(url="https://a")})
    second = DictField(by_name={"primary": Endpoint(url="https://b")})

    # Act
    hashes = {content_hash(first), content_hash(second)}

    # Assert
    assert len(hashes) == 2


def test_connector_in_a_nested_model_hashes_by_the_connector() -> None:
    # Arrange
    first = Outer(inner=TypedField(connector=Endpoint(url="https://a")), label="x")
    second = Outer(inner=TypedField(connector=Endpoint(url="https://b")), label="x")

    # Act
    hashes = {content_hash(first), content_hash(second)}

    # Assert
    assert len(hashes) == 2


def test_serialization_alias_field_hashes_by_the_connector() -> None:
    # Arrange
    first = AliasedField(connector=Endpoint(url="https://a"))
    second = AliasedField(connector=Endpoint(url="https://b"))

    # Act
    hashes = {content_hash(first), content_hash(second)}

    # Assert
    assert len(hashes) == 2


def test_extra_field_holding_a_connector_hashes_by_the_connector() -> None:
    # Arrange
    first = ExtraAllowed.model_validate({"connector": Endpoint(url="https://a")})
    second = ExtraAllowed.model_validate({"connector": Endpoint(url="https://b")})

    # Act
    hashes = {content_hash(first), content_hash(second)}

    # Assert
    assert len(hashes) == 2


def test_root_model_holding_a_connector_hashes_by_the_connector() -> None:
    # Arrange
    first = EndpointRoot(Endpoint(url="https://a"))
    second = EndpointRoot(Endpoint(url="https://b"))

    # Act
    hashes = {content_hash(first), content_hash(second)}

    # Assert
    assert len(hashes) == 2


def test_excluded_connector_field_stays_out_of_the_hash() -> None:
    # Arrange
    first = ExcludedField(connector=Endpoint(url="https://a"), label="x")
    second = ExcludedField(connector=Endpoint(url="https://b"), label="x")

    # Act
    hashes = {content_hash(first), content_hash(second)}

    # Assert
    assert len(hashes) == 1


def test_same_model_instance_hashes_stably() -> None:
    # Arrange
    model = ListField(connectors=[Endpoint(url="https://a"), Endpoint(url="https://b")])

    # Act
    hashes = {content_hash(model) for _ in range(5)}

    # Assert
    assert len(hashes) == 1


def test_non_hook_siblings_keep_their_dumped_form_and_stay_hashable() -> None:
    # Arrange — a datetime has no canonical form of its own; only the dump can
    # represent it, so the merge must leave it dumped.
    moment = dt.datetime(2026, 9, 12, tzinfo=dt.UTC)
    connector = Endpoint(url="https://a")
    model = MixedAnyList(items=[connector, moment])

    # Act
    canonical = _canonicalise(model)

    # Assert
    assert canonical == {
        "__model__": "MixedAnyList",
        "data": _canonicalise(
            {"items": [connector.__pirn_canonical__(), moment.isoformat().replace("+00:00", "Z")]}
        ),
    }
    assert ":unhashable:" not in content_hash(model)


def test_plain_object_hook_nested_in_any_field_drives_the_hash() -> None:
    # Arrange — pydantic cannot serialise it at all; the hook gives it a form.
    first = AnyField(value=Canonical("one"))
    second = AnyField(value=Canonical("two"))

    # Act
    hashes = {content_hash(first), content_hash(second)}

    # Assert
    assert len(hashes) == 2


def test_model_without_hooks_hashes_exactly_as_before() -> None:
    # Arrange
    model = PlainModel(name="n", when=dt.datetime(2026, 9, 12, tzinfo=dt.UTC), tags=["a", "b"])

    # Act
    canonical = _canonicalise(model)

    # Assert — the pre-PIR-848 formula: the dumped JSON, canonicalised.
    assert canonical == {
        "__model__": "PlainModel",
        "data": _canonicalise(model.model_dump(mode="json")),
    }


def test_model_dump_audit_output_is_unchanged() -> None:
    # Arrange
    model = TypedField(connector=Endpoint(url="https://a"))

    # Act
    dumped = model.model_dump(mode="json")

    # Assert
    assert dumped == {"connector": {"connector": "Endpoint", "has_credential": False}}
