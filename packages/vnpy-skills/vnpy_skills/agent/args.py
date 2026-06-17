"""Agent 通用工具的参数模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReadSkillFileArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    skill: str = Field(min_length=1, description="skill 名称")
    path: str = Field(min_length=1, description="相对 skill 根目录的路径")

    @field_validator("skill", "path", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ListSkillFilesArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    skill: str = Field(min_length=1, description="skill 名称")
    subdir: str = Field(default="", description="子目录")

    @field_validator("skill", "subdir", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class RunPythonArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    skill: str = Field(min_length=1, description="skill 名称")
    code: str = Field(default="", description="要执行的 Python 源码")
    script_path: str = Field(default="", description="skill 内脚本相对路径")

    @field_validator("skill", "code", "script_path", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value
