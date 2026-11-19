"""Nand2Tetris VM Translator (Projects 7 & 8) — single-file implementation."""

import argparse
from enum import Enum
from pathlib import Path
from typing import Sequence, TextIO


class CommandType(Enum):
    """Enumeration of all VM command types."""

    C_ARITHMETIC = "C_ARITHMETIC"
    C_PUSH = "C_PUSH"
    C_POP = "C_POP"
    C_LABEL = "C_LABEL"
    C_GOTO = "C_GOTO"
    C_IF = "C_IF"
    C_FUNCTION = "C_FUNCTION"
    C_RETURN = "C_RETURN"
    C_CALL = "C_CALL"


ARITHMETIC_COMMANDS = frozenset(
    {"add", "sub", "neg", "eq", "gt", "lt", "and", "or", "not"}
)

_KEYWORD_TO_COMMAND_TYPE = {
    "push": CommandType.C_PUSH,
    "pop": CommandType.C_POP,
    "label": CommandType.C_LABEL,
    "goto": CommandType.C_GOTO,
    "if-goto": CommandType.C_IF,
    "function": CommandType.C_FUNCTION,
    "return": CommandType.C_RETURN,
    "call": CommandType.C_CALL,
}

_ARG2_COMMAND_TYPES = frozenset(
    {
        CommandType.C_PUSH,
        CommandType.C_POP,
        CommandType.C_FUNCTION,
        CommandType.C_CALL,
    }
)

_SEGMENT_BASE_SYMBOLS = {
    "local": "LCL",
    "argument": "ARG",
    "this": "THIS",
    "that": "THAT",
}

_BINARY_ARITHMETIC_OPS = {
    "add": "M=D+M",
    "sub": "M=M-D",
    "and": "M=D&M",
    "or": "M=D|M",
}

_UNARY_ARITHMETIC_OPS = {
    "neg": "M=-M",
    "not": "M=!M",
}

_COMPARISON_JUMPS = {
    "eq": "JEQ",
    "gt": "JGT",
    "lt": "JLT",
}


class Parser:
    """Reads a single .vm file, ignores comments/whitespace, and exposes command tokens."""

    def __init__(self, input_path: str | Path) -> None:
        """Load and pre-clean all VM commands from the given .vm file."""
        raw_lines = Path(input_path).read_text(encoding="utf-8").splitlines()
        self._commands: list[str] = []
        for raw_line in raw_lines:
            cleaned = raw_line.split("//", 1)[0].strip()
            if cleaned:
                self._commands.append(" ".join(cleaned.split()))

        self._index: int = -1
        self._current_tokens: list[str] = []

    def hasMoreLines(self) -> bool:
        """Return True if there are remaining commands in the input."""
        return self._index + 1 < len(self._commands)

    def advance(self) -> None:
        """Read the next command from input and make it the current command."""
        if not self.hasMoreLines():
            raise RuntimeError("No more lines to advance to.")
        self._index += 1
        self._current_tokens = self._commands[self._index].split()

    def currentCommand(self) -> str:
        """Return the normalized current command string for assembly comments."""
        self._require_current_command()
        return " ".join(self._current_tokens)

    def commandType(self) -> CommandType:
        """Return the CommandType of the current VM command."""
        self._require_current_command()
        keyword = self._current_tokens[0]
        if keyword in ARITHMETIC_COMMANDS:
            return CommandType.C_ARITHMETIC
        if keyword in _KEYWORD_TO_COMMAND_TYPE:
            return _KEYWORD_TO_COMMAND_TYPE[keyword]
        raise ValueError(f"Unknown VM command: {self.currentCommand()!r}")

    def arg1(self) -> str:
        """Return the first argument of the current command (or command itself for C_ARITHMETIC)."""
        cmd_type = self.commandType()
        if cmd_type == CommandType.C_RETURN:
            raise RuntimeError("arg1() must not be called for C_RETURN commands.")
        if cmd_type == CommandType.C_ARITHMETIC:
            return self._current_tokens[0]
        if len(self._current_tokens) < 2:
            raise ValueError(f"Missing arg1 in VM command: {self.currentCommand()!r}")
        return self._current_tokens[1]

    def arg2(self) -> int:
        """Return the second integer argument of the current command."""
        cmd_type = self.commandType()
        if cmd_type not in _ARG2_COMMAND_TYPES:
            raise RuntimeError(
                f"arg2() is invalid for command type {cmd_type.value}."
            )
        if len(self._current_tokens) < 3:
            raise ValueError(f"Missing arg2 in VM command: {self.currentCommand()!r}")
        return int(self._current_tokens[2])

    def _require_current_command(self) -> None:
        if not self._current_tokens:
            raise RuntimeError("No current command; call advance() first.")


class CodeWriter:
    """Translates parsed VM commands into Hack assembly code and writes them to an .asm file."""

    def __init__(
        self, output_path: str | Path, write_bootstrap: bool = False
    ) -> None:
        """Open the output .asm file and optionally emit bootstrap code."""
        self._output_path = Path(output_path)
        self._out: TextIO = self._output_path.open(
            "w", encoding="utf-8", newline="\n"
        )
        self._closed: bool = False
        self._file_name: str = ""
        self._current_function: str = ""
        self._cmp_counter: int = 0
        self._ret_counters: dict[str, int] = {}

        if write_bootstrap:
            self.writeInit()

    def __enter__(self) -> "CodeWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def setFileName(self, file_name: str) -> None:
        """Inform CodeWriter that translation of a new .vm file has started."""
        self._file_name = Path(file_name).stem
        self._current_function = ""

    def writeInit(self) -> None:
        """Write bootstrap assembly code (SP = 256; call Sys.init 0)."""
        self._emit(
            "// Bootstrap code",
            "@256",
            "D=A",
            "@SP",
            "M=D",
        )
        self.writeCall("Sys.init", 0)

    def writeArithmetic(self, command: str) -> None:
        """Write assembly code implementing an arithmetic-logical VM command."""
        self._emit(f"// {command}")

        if command in _BINARY_ARITHMETIC_OPS:
            op = _BINARY_ARITHMETIC_OPS[command]
            self._emit("@SP", "AM=M-1", "D=M", "A=A-1", op)
            return

        if command in _UNARY_ARITHMETIC_OPS:
            op = _UNARY_ARITHMETIC_OPS[command]
            self._emit("@SP", "A=M-1", op)
            return

        if command in _COMPARISON_JUMPS:
            jump = _COMPARISON_JUMPS[command]
            end_label = f"CMP_END.{self._cmp_counter}"
            self._cmp_counter += 1
            self._emit(
                "@SP",
                "AM=M-1",
                "D=M",
                "A=A-1",
                "D=M-D",
                "M=-1",
                f"@{end_label}",
                f"D;{jump}",
                "@SP",
                "A=M-1",
                "M=0",
                f"({end_label})",
            )
            return

        raise ValueError(f"Unsupported arithmetic command: {command!r}")

    def writePushPop(
        self, command: CommandType, segment: str, index: int
    ) -> None:
        """Write assembly code implementing a push or pop VM command."""
        if command not in (CommandType.C_PUSH, CommandType.C_POP):
            raise ValueError(f"writePushPop requires C_PUSH or C_POP, got {command}")
        if index < 0:
            raise ValueError(f"Segment index must be non-negative, got {index}")

        is_push = command == CommandType.C_PUSH
        action = "push" if is_push else "pop"
        self._emit(f"// {action} {segment} {index}")

        if segment == "constant":
            if not is_push:
                raise ValueError("Cannot pop into the constant segment.")
            self._emit(f"@{index}", "D=A")
            self._push_d()
            return

        if segment in _SEGMENT_BASE_SYMBOLS:
            base = _SEGMENT_BASE_SYMBOLS[segment]
            if is_push:
                self._emit(f"@{base}", "D=M", f"@{index}", "A=D+A", "D=M")
                self._push_d()
            else:
                self._emit(f"@{base}", "D=M", f"@{index}", "D=D+A", "@R13", "M=D")
                self._pop_to_d()
                self._emit("@R13", "A=M", "M=D")
            return

        if segment == "temp":
            if index > 7:
                raise ValueError(f"temp segment index out of range (0..7): {index}")
            self._emit_direct_push_pop(is_push, str(5 + index))
            return

        if segment == "pointer":
            if index not in (0, 1):
                raise ValueError(f"pointer segment index must be 0 or 1, got {index}")
            target = "THIS" if index == 0 else "THAT"
            self._emit_direct_push_pop(is_push, target)
            return

        if segment == "static":
            if not self._file_name:
                raise RuntimeError(
                    "setFileName() must be called before translating static segment."
                )
            self._emit_direct_push_pop(is_push, f"{self._file_name}.{index}")
            return

        raise ValueError(f"Unsupported memory segment: {segment!r}")

    def writeLabel(self, label: str) -> None:
        """Write assembly code implementing the VM label command."""
        scoped = self._scoped_label(label)
        self._emit(f"// label {label}", f"({scoped})")

    def writeGoto(self, label: str) -> None:
        """Write assembly code implementing the VM goto command."""
        scoped = self._scoped_label(label)
        self._emit(f"// goto {label}", f"@{scoped}", "0;JMP")

    def writeIf(self, label: str) -> None:
        """Write assembly code implementing the VM if-goto command."""
        scoped = self._scoped_label(label)
        self._emit(f"// if-goto {label}")
        self._pop_to_d()
        self._emit(f"@{scoped}", "D;JNE")

    def writeFunction(self, function_name: str, n_vars: int) -> None:
        """Write assembly code implementing the VM function declaration."""
        if n_vars < 0:
            raise ValueError(f"nVars must be non-negative, got {n_vars}")
        self._current_function = function_name
        self._emit(f"// function {function_name} {n_vars}", f"({function_name})")
        for _ in range(n_vars):
            self._emit("@SP", "M=M+1", "A=M-1", "M=0")

    def writeCall(self, function_name: str, n_args: int) -> None:
        """Write assembly code implementing the VM call command."""
        if n_args < 0:
            raise ValueError(f"nArgs must be non-negative, got {n_args}")

        caller = self._current_function or "BOOTSTRAP"
        ret_index = self._ret_counters.get(caller, 0) + 1
        self._ret_counters[caller] = ret_index
        ret_label = f"{caller}$ret.{ret_index}"

        self._emit(f"// call {function_name} {n_args}")
        # Push return address (ROM label address via D=A)
        self._emit(f"@{ret_label}", "D=A")
        self._push_d()

        # Save caller's frame pointers
        for seg in ("LCL", "ARG", "THIS", "THAT"):
            self._emit(f"@{seg}", "D=M")
            self._push_d()

        # Reposition ARG = SP - (5 + nArgs) and LCL = SP
        self._emit(
            "@SP",
            "D=M",
            f"@{5 + n_args}",
            "D=D-A",
            "@ARG",
            "M=D",
            "@SP",
            "D=M",
            "@LCL",
            "M=D",
            f"@{function_name}",
            "0;JMP",
            f"({ret_label})",
        )

    def writeReturn(self) -> None:
        """Write assembly code implementing the VM return command."""
        self._emit(
            "// return",
            # endFrame (R13) = LCL
            "@LCL",
            "D=M",
            "@R13",
            "M=D",
            # retAddr (R14) = *(endFrame - 5), saved before *ARG = pop()
            "@5",
            "A=D-A",
            "D=M",
            "@R14",
            "M=D",
        )
        # *ARG = pop()
        self._pop_to_d()
        self._emit(
            "@ARG",
            "A=M",
            "M=D",
            # SP = ARG + 1
            "@ARG",
            "D=M+1",
            "@SP",
            "M=D",
        )
        # Restore THAT, THIS, ARG, LCL from *(endFrame - 1..4)
        for seg in ("THAT", "THIS", "ARG", "LCL"):
            self._emit("@R13", "AM=M-1", "D=M", f"@{seg}", "M=D")
        # Jump to saved return address
        self._emit("@R14", "A=M", "0;JMP")

    def close(self) -> None:
        """Close the output assembly file."""
        if not self._closed:
            self._out.close()
            self._closed = True

    def _emit(self, *lines: str) -> None:
        for line in lines:
            self._out.write(f"{line}\n")

    def _push_d(self) -> None:
        self._emit("@SP", "M=M+1", "A=M-1", "M=D")

    def _pop_to_d(self) -> None:
        self._emit("@SP", "AM=M-1", "D=M")

    def _emit_direct_push_pop(self, is_push: bool, symbol: str) -> None:
        if is_push:
            self._emit(f"@{symbol}", "D=M")
            self._push_d()
        else:
            self._pop_to_d()
            self._emit(f"@{symbol}", "M=D")

    def _scoped_label(self, label: str) -> str:
        if self._current_function:
            return f"{self._current_function}${label}"
        return label


def _translate_file(vm_file: Path, writer: CodeWriter) -> None:
    """Parse and emit assembly for a single .vm file."""
    writer.setFileName(vm_file.name)
    parser = Parser(vm_file)
    while parser.hasMoreLines():
        parser.advance()
        cmd_type = parser.commandType()
        if cmd_type == CommandType.C_ARITHMETIC:
            writer.writeArithmetic(parser.arg1())
        elif cmd_type in (CommandType.C_PUSH, CommandType.C_POP):
            writer.writePushPop(cmd_type, parser.arg1(), parser.arg2())
        elif cmd_type == CommandType.C_LABEL:
            writer.writeLabel(parser.arg1())
        elif cmd_type == CommandType.C_GOTO:
            writer.writeGoto(parser.arg1())
        elif cmd_type == CommandType.C_IF:
            writer.writeIf(parser.arg1())
        elif cmd_type == CommandType.C_FUNCTION:
            writer.writeFunction(parser.arg1(), parser.arg2())
        elif cmd_type == CommandType.C_CALL:
            writer.writeCall(parser.arg1(), parser.arg2())
        elif cmd_type == CommandType.C_RETURN:
            writer.writeReturn()


def translate(source: str | Path, bootstrap: bool | None = None) -> Path:
    """Translate a .vm file or a directory of .vm files into a single .asm file."""
    source_path = Path(source)
    if not source_path.exists():
        raise FileNotFoundError(f"Source path not found: {source_path}")

    if source_path.is_file():
        if source_path.suffix.lower() != ".vm":
            raise ValueError(f"Expected a .vm file, got: {source_path}")
        vm_files = [source_path]
        output_path = source_path.with_suffix(".asm")
        default_bootstrap = False
    elif source_path.is_dir():
        vm_files = sorted(source_path.glob("*.vm"), key=lambda p: p.name)
        if not vm_files:
            raise FileNotFoundError(
                f"No .vm files found in directory: {source_path}"
            )
        output_path = source_path / f"{source_path.resolve().name}.asm"
        default_bootstrap = len(vm_files) > 1 or any(
            f.name == "Sys.vm" for f in vm_files
        )
    else:
        raise ValueError(f"Unsupported source path: {source_path}")

    write_bootstrap = default_bootstrap if bootstrap is None else bootstrap

    with CodeWriter(output_path, write_bootstrap=write_bootstrap) as writer:
        for vm_file in vm_files:
            _translate_file(vm_file, writer)

    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for VMTranslator."""
    arg_parser = argparse.ArgumentParser(
        description="Translate Nand2Tetris VM (.vm) file or directory into Hack assembly (.asm)."
    )
    arg_parser.add_argument(
        "source",
        help="Path to a .vm file or a directory containing .vm files.",
    )
    boot_group = arg_parser.add_mutually_exclusive_group()
    boot_group.add_argument(
        "--bootstrap",
        dest="bootstrap",
        action="store_true",
        default=None,
        help="Force emitting bootstrap code (SP=256; call Sys.init 0).",
    )
    boot_group.add_argument(
        "--no-bootstrap",
        dest="bootstrap",
        action="store_false",
        help="Disable emitting bootstrap code.",
    )
    return arg_parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""
    arg_parser = build_arg_parser()
    args = arg_parser.parse_args(argv)
    output_path = translate(args.source, bootstrap=args.bootstrap)
    print(f"Generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
