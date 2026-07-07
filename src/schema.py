from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator

class Chunk(BaseModel):
    id: str
    text: str
    version: Literal["v1", "v2", "both"]
    release_label: str
    chunk_type: Literal["prose", "code", "changelog", "migration"]
    source_file: str
    header_path: list[str]=Field(default_factory=list)
    symbol_name: Optional[str]=None
    linked_files: list[str]=Field(default_factory=list)

    @model_validator(mode="after")
    def code_chunks_name_their_symbol(self):
        if self.chunk_type == "code" and not self.symbol_name:
            raise ValueError("code chunks must carry a symbol_name")
        return self