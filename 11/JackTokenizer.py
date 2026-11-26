"""JackTokenizer (Project 10): splits a .jack source file into Jack tokens."""

import re
from enum import Enum
from pathlib import Path


class TokenType(Enum):
    """The five Jack token types; values are the XML tag names."""

    KEYWORD = "keyword"
    SYMBOL = "symbol"
    IDENTIFIER = "identifier"
    INT_CONST = "integerConstant"
    STRING_CONST = "stringConstant"


KEYWORDS = frozenset(
    {
        "class", "constructor", "function", "method", "field", "static",
        "var", "int", "char", "boolean", "void", "true", "false", "null",
        "this", "let", "do", "if", "else", "while", "return",
    }
)

SYMBOLS = frozenset("{}()[].,;+-*/&|<>=~")

# Order matters: comments and strings are matched before symbols, so a "/" that
# starts a comment, or a symbol inside a string, is never read as a symbol.
_TOKEN_RE = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<line_comment>//[^\n]*)
    | (?P<block_comment>/\*.*?\*/)
    | (?P<string>"[^"\n]*")
    | (?P<int>\d+)
    | (?P<word>[A-Za-z_][A-Za-z0-9_]*)
    | (?P<symbol>[{}()\[\].,;+\-*/&|<>=~])
    """,
    re.VERBOSE | re.DOTALL,
)

MAX_INT = 32767


def tokenize(source: str) -> list[tuple[TokenType, str]]:
    """Return every token of `source` as (type, text), skipping whitespace and comments."""
    tokens: list[tuple[TokenType, str]] = []
    pos = 0
    while pos < len(source):
        match = _TOKEN_RE.match(source, pos)
        if match is None:
            line = source.count("\n", 0, pos) + 1
            raise SyntaxError(f"line {line}: unexpected character {source[pos]!r}")
        kind, text = match.lastgroup, match.group()
        pos = match.end()

        if kind in ("ws", "line_comment", "block_comment"):
            continue
        if kind == "string":
            tokens.append((TokenType.STRING_CONST, text[1:-1]))
        elif kind == "int":
            if int(text) > MAX_INT:
                raise SyntaxError(f"integer constant out of range: {text}")
            tokens.append((TokenType.INT_CONST, text))
        elif kind == "word":
            token_type = TokenType.KEYWORD if text in KEYWORDS else TokenType.IDENTIFIER
            tokens.append((token_type, text))
        else:
            tokens.append((TokenType.SYMBOL, text))
    return tokens


class JackTokenizer:
    """Gives access to the tokens of a .jack file one at a time (API from Lecture 10)."""

    def __init__(self, input_path: str | Path) -> None:
        source = Path(input_path).read_text(encoding="utf-8")
        self._tokens = tokenize(source)
        self._index = -1  # no current token until the first advance()

    def hasMoreTokens(self) -> bool:
        return self._index + 1 < len(self._tokens)

    def advance(self) -> None:
        """Make the next token the current token."""
        if not self.hasMoreTokens():
            raise IndexError("advance() called with no more tokens")
        self._index += 1

    def peek(self, offset: int = 1) -> tuple[TokenType, str] | None:
        """Look ahead without advancing (the parser needs one token of lookahead)."""
        i = self._index + offset
        return self._tokens[i] if 0 <= i < len(self._tokens) else None

    def tokenType(self) -> TokenType:
        return self._tokens[self._index][0]

    def text(self) -> str:
        """The current token's text, whatever its type."""
        return self._tokens[self._index][1]

    def keyWord(self) -> str:
        return self._expect(TokenType.KEYWORD)

    def symbol(self) -> str:
        return self._expect(TokenType.SYMBOL)

    def identifier(self) -> str:
        return self._expect(TokenType.IDENTIFIER)

    def intVal(self) -> int:
        return int(self._expect(TokenType.INT_CONST))

    def stringVal(self) -> str:
        return self._expect(TokenType.STRING_CONST)

    def _expect(self, token_type: TokenType) -> str:
        if self.tokenType() is not token_type:
            raise TypeError(
                f"current token {self.text()!r} is {self.tokenType().value}, "
                f"not {token_type.value}"
            )
        return self.text()


_XML_ESCAPES = {"<": "&lt;", ">": "&gt;", '"': "&quot;", "&": "&amp;"}


def xml_escape(text: str) -> str:
    """Escape the four characters that XML reserves."""
    return "".join(_XML_ESCAPES.get(ch, ch) for ch in text)


def token_xml(token_type: TokenType, text: str) -> str:
    """One token as an XML line, e.g. `<symbol> &lt; </symbol>`."""
    return f"<{token_type.value}> {xml_escape(text)} </{token_type.value}>"
