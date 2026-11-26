"""JackAnalyzer (Project 10): tokenizes and parses .jack files into XML.

Usage:
    python JackAnalyzer.py <Xxx.jack | folder> [-o OUTPUT_DIR]

For every Xxx.jack it writes XxxT.xml (token list) and Xxx.xml (parse tree).
Output goes to OUTPUT_DIR, by default an `output` folder next to the sources,
so the supplied compare files with the same names are not overwritten.
"""

import argparse
from pathlib import Path

from CompilationEngine import CompilationEngine
from JackTokenizer import JackTokenizer, token_xml


def write_tokens(jack_file: Path, out_file: Path) -> None:
    """Write the token list wrapped in <tokens> ... </tokens>."""
    tokenizer = JackTokenizer(jack_file)
    with out_file.open("w", encoding="utf-8", newline="\n") as out:
        out.write("<tokens>\n")
        while tokenizer.hasMoreTokens():
            tokenizer.advance()
            out.write(token_xml(tokenizer.tokenType(), tokenizer.text()) + "\n")
        out.write("</tokens>\n")


def write_parse_tree(jack_file: Path, out_file: Path) -> None:
    tokenizer = JackTokenizer(jack_file)
    with out_file.open("w", encoding="utf-8", newline="\n") as out:
        engine = CompilationEngine(tokenizer, out)
        engine.compileClass()
        if tokenizer.hasMoreTokens():
            tokenizer.advance()
            raise SyntaxError(f"{jack_file.name}: unexpected token after class: {tokenizer.text()!r}")


def jack_files(source: Path) -> list[Path]:
    if source.is_dir():
        return sorted(source.glob("*.jack"))
    if source.suffix == ".jack":
        return [source]
    raise ValueError(f"{source} is neither a .jack file nor a folder")


def main() -> None:
    parser = argparse.ArgumentParser(description="Jack syntax analyzer (Nand2Tetris project 10)")
    parser.add_argument("source", type=Path, help="a .jack file or a folder of .jack files")
    parser.add_argument("-o", "--output-dir", type=Path, help="where to write the .xml files")
    args = parser.parse_args()

    files = jack_files(args.source)
    source_dir = args.source if args.source.is_dir() else args.source.parent
    out_dir = args.output_dir or source_dir / "output"
    out_dir.mkdir(parents=True, exist_ok=True)

    for jack_file in files:
        write_tokens(jack_file, out_dir / f"{jack_file.stem}T.xml")
        write_parse_tree(jack_file, out_dir / f"{jack_file.stem}.xml")
        print(f"{jack_file} -> {out_dir / jack_file.stem}T.xml, {jack_file.stem}.xml")


if __name__ == "__main__":
    main()
