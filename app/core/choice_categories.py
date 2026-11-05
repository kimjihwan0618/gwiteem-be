"""카테고리 표시명·순서·신규 등록 허용 여부를 한 파일에서 읽는다."""
import tomllib
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, AfterValidator, model_validator


class ChoiceCategoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,19}$")
    label: str = Field(min_length=1, max_length=30)
    enabled: bool = True


class CategoryCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    categories: list[ChoiceCategoryItem] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_codes(self) -> "CategoryCatalog":
        if len({item.code for item in self.categories}) != len(self.categories):
            raise ValueError("카테고리 코드는 중복될 수 없습니다.")
        return self


with (Path(__file__).resolve().parents[1] / "choice_categories.toml").open("rb") as source:
    CATEGORIES = tuple(CategoryCatalog.model_validate(tomllib.load(source)).categories)


def validate_category(value: str) -> str:
    if not any(item.code == value for item in CATEGORIES):
        raise ValueError("지원하지 않는 카테고리입니다.")
    return value


def validate_creation_category(value: str) -> str:
    if not any(item.code == value and item.enabled for item in CATEGORIES):
        raise ValueError("현재 등록할 수 없는 카테고리입니다.")
    return value


def category_label(value: str) -> str:
    return next((item.label for item in CATEGORIES if item.code == value), value)


ChoiceCategory = Annotated[str, AfterValidator(validate_category)]
CreationCategory = Annotated[str, AfterValidator(validate_creation_category)]
