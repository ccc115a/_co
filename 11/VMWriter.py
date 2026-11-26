"""VMWriter (Project 11): writes VM commands to a .vm file (API from Lecture 11)."""

from pathlib import Path

SEGMENTS = frozenset({"constant", "argument", "local", "static", "this", "that", "pointer", "temp"})
ARITHMETIC = frozenset({"add", "sub", "neg", "eq", "gt", "lt", "and", "or", "not"})


class VMWriter:
    def __init__(self, output_path: str | Path) -> None:
        self._out = Path(output_path).open("w", encoding="utf-8", newline="\n")

    def __enter__(self) -> "VMWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def writePush(self, segment: str, index: int) -> None:
        self._check_segment(segment)
        self._emit(f"push {segment} {index}")

    def writePop(self, segment: str, index: int) -> None:
        self._check_segment(segment)
        if segment == "constant":
            raise ValueError("cannot pop to the constant segment")
        self._emit(f"pop {segment} {index}")

    def writeArithmetic(self, command: str) -> None:
        if command not in ARITHMETIC:
            raise ValueError(f"unknown arithmetic command {command!r}")
        self._emit(command)

    def writeLabel(self, label: str) -> None:
        self._out.write(f"label {label}\n")

    def writeGoto(self, label: str) -> None:
        self._emit(f"goto {label}")

    def writeIf(self, label: str) -> None:
        self._emit(f"if-goto {label}")

    def writeCall(self, name: str, n_args: int) -> None:
        self._emit(f"call {name} {n_args}")

    def writeFunction(self, name: str, n_vars: int) -> None:
        self._out.write(f"function {name} {n_vars}\n")

    def writeReturn(self) -> None:
        self._emit("return")

    def close(self) -> None:
        self._out.close()

    def _emit(self, command: str) -> None:
        self._out.write(f"    {command}\n")

    @staticmethod
    def _check_segment(segment: str) -> None:
        if segment not in SEGMENTS:
            raise ValueError(f"unknown segment {segment!r}")
