"""SymbolTable (Project 11): two-level table of Jack variables (Lecture 11).

Class level holds STATIC and FIELD variables; subroutine level holds ARG and VAR
variables and is cleared by reset() at the start of every subroutine.
Each kind keeps its own running index starting at 0.
"""

from dataclasses import dataclass
from enum import Enum


class Kind(Enum):
    STATIC = "static"
    FIELD = "field"
    ARG = "arg"
    VAR = "var"


# VM memory segment that holds each kind of variable.
SEGMENT_OF_KIND = {
    Kind.STATIC: "static",
    Kind.FIELD: "this",
    Kind.ARG: "argument",
    Kind.VAR: "local",
}

_CLASS_KINDS = (Kind.STATIC, Kind.FIELD)


@dataclass(frozen=True)
class Symbol:
    type: str
    kind: Kind
    index: int


class SymbolTable:
    def __init__(self) -> None:
        self._class_scope: dict[str, Symbol] = {}
        self._subroutine_scope: dict[str, Symbol] = {}
        self._counts = {kind: 0 for kind in Kind}

    def reset(self) -> None:
        """Start a new subroutine scope (the book's startSubroutine)."""
        self._subroutine_scope.clear()
        self._counts[Kind.ARG] = 0
        self._counts[Kind.VAR] = 0

    def define(self, name: str, type_: str, kind: Kind) -> None:
        """Add a variable, giving it the next index of its kind."""
        scope = self._class_scope if kind in _CLASS_KINDS else self._subroutine_scope
        if name in scope:
            raise NameError(f"variable {name!r} is already defined in this scope")
        scope[name] = Symbol(type_, kind, self._counts[kind])
        self._counts[kind] += 1

    def varCount(self, kind: Kind) -> int:
        return self._counts[kind]

    def lookup(self, name: str) -> Symbol | None:
        """Subroutine scope first, then class scope; None if the name is not a variable."""
        return self._subroutine_scope.get(name) or self._class_scope.get(name)

    def kindOf(self, name: str) -> Kind | None:
        symbol = self.lookup(name)
        return symbol.kind if symbol else None

    def typeOf(self, name: str) -> str:
        return self._require(name).type

    def indexOf(self, name: str) -> int:
        return self._require(name).index

    def _require(self, name: str) -> Symbol:
        symbol = self.lookup(name)
        if symbol is None:
            raise NameError(f"undefined variable {name!r}")
        return symbol
