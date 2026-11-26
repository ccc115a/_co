"""JackCompiler (Project 11): compiles .jack files into .vm files.

Usage:
    python JackCompiler.py <Xxx.jack | folder>

Each Xxx.jack is compiled to Xxx.vm in the same folder, so the folder can be
loaded straight into the VM emulator.
"""

import argparse
from pathlib import Path

from CompilationEngine import CompilationEngine
from JackTokenizer import JackTokenizer
from VMWriter import VMWriter


def compile_file(jack_file: Path) -> Path:
    vm_file = jack_file.with_suffix(".vm")
    tokenizer = JackTokenizer(jack_file)
    with VMWriter(vm_file) as writer:
        CompilationEngine(tokenizer, writer).compileClass()
    if tokenizer.hasMoreTokens():
        tokenizer.advance()
        raise SyntaxError(f"{jack_file.name}: unexpected token after class: {tokenizer.text()!r}")
    return vm_file


def jack_files(source: Path) -> list[Path]:
    if source.is_dir():
        return sorted(source.glob("*.jack"))
    if source.suffix == ".jack":
        return [source]
    raise ValueError(f"{source} is neither a .jack file nor a folder")


def main() -> None:
    parser = argparse.ArgumentParser(description="Jack compiler (Nand2Tetris project 11)")
    parser.add_argument("source", type=Path, help="a .jack file or a folder of .jack files")
    args = parser.parse_args()

    for jack_file in jack_files(args.source):
        print(f"{jack_file} -> {compile_file(jack_file)}")


if __name__ == "__main__":
    main()
