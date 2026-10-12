"""Golden fixture: SQLModel-style models."""
from sqlmodel import Field, SQLModel


class WidgetBase(SQLModel):
    title: str = Field(max_length=255)
    count: int | None = None


class Widget(WidgetBase, table=True):
    id: int = Field(primary_key=True)
    owner: str


class Named(WidgetBase, table=True):
    __tablename__ = "custom_names"
    code: str = "x"


class Plain(SQLModel):
    note: str
