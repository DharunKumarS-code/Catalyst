from bson import ObjectId
from bson.errors import InvalidId


def to_object_id(value: str | ObjectId | None) -> ObjectId | None:
    """Parse an id from a path or token; None when malformed (callers answer 404)."""
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None
