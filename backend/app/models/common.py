"""Shared helpers for MongoDB document serialization with Pydantic v2."""
from typing import Any

from bson import ObjectId
from pydantic import BaseModel, field_validator, model_serializer


class PyObjectId(str):
    """String subclass that validates MongoDB ObjectIds."""

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: Any) -> str:
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError(f"Invalid ObjectId: {v!r}")

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        return core_schema.no_info_plain_validator_function(
            cls.validate,
            serialization=core_schema.to_string_ser_schema(),
        )


def mongo_doc_to_dict(doc: dict) -> dict:
    """Convert a MongoDB document's _id to 'id' string."""
    if doc is None:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc
