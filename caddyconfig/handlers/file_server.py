"""
Handler ``file_server`` – https://caddyserver.com/docs/json/apps/http/servers/routes/handle/file_server/
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import Field

from . import HandlerBase, register_handler


@register_handler("file_server")
class FileServerHandler(HandlerBase):
    """
    Serves static files.

    Attributes
    ----------
    handler : str
        Always ``"file_server"``.
    root : str | None
        Root directory.
    hide : list[str]
        Paths to hide.
    index_names : list[str]
        Index files.
    browse : bool
        Enables directory listing.
    canonical_uris : bool | None
    pass_thru : bool
        Continues if file is absent.
    """

    handler: str = "file_server"
    root: Optional[str] = None
    hide: list[str] = Field(default_factory=list)
    index_names: list[str] = Field(default_factory=list)
    browse: bool = False
    canonical_uris: Optional[bool] = None
    pass_thru: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"handler": self.handler}
        if self.root is not None:
            d["root"] = self.root
        if self.hide:
            d["hide"] = list(self.hide)
        if self.index_names:
            d["index_names"] = list(self.index_names)
        if self.browse:
            d["browse"] = {}
        if self.canonical_uris is not None:
            d["canonical_uris"] = self.canonical_uris
        if self.pass_thru:
            d["pass_thru"] = True
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileServerHandler":
        return cls(
            root=data.get("root"),
            hide=list(data.get("hide", [])),
            index_names=list(data.get("index_names", [])),
            browse="browse" in data,
            canonical_uris=data.get("canonical_uris"),
            pass_thru=data.get("pass_thru", False),
        )
