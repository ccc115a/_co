"""CompilationEngine (Project 10): recursive-descent parser that emits the parse tree as XML.

Each compileXxx method parses one rule of the Jack grammar (Lecture 10) and
writes `<xxx>` ... `</xxx>` around the tokens and sub-rules it consumes.
"""

from typing import TextIO

from JackTokenizer import JackTokenizer, TokenType, token_xml

OPS = frozenset("+-*/&|<>=")
UNARY_OPS = frozenset("-~")
KEYWORD_CONSTANTS = frozenset({"true", "false", "null", "this"})
STATEMENT_KEYWORDS = frozenset({"let", "if", "while", "do", "return"})


class CompilationEngine:
    def __init__(self, tokenizer: JackTokenizer, output: TextIO) -> None:
        self._tk = tokenizer
        self._out = output
        self._depth = 0

    # ---------- program structure ----------

    def compileClass(self) -> None:
        """'class' className '{' classVarDec* subroutineDec* '}'"""
        self._open("class")
        self._eat("class")
        self._eat_identifier()
        self._eat("{")
        while self._next_is("static", "field"):
            self.compileClassVarDec()
        while self._next_is("constructor", "function", "method"):
            self.compileSubroutine()
        self._eat("}")
        self._close("class")

    def compileClassVarDec(self) -> None:
        """('static' | 'field') type varName (',' varName)* ';'"""
        self._open("classVarDec")
        self._eat("static", "field")
        self._eat_type()
        self._eat_var_name_list()
        self._close("classVarDec")

    def compileSubroutine(self) -> None:
        """('constructor'|'function'|'method') ('void'|type) subroutineName '(' parameterList ')' subroutineBody"""
        self._open("subroutineDec")
        self._eat("constructor", "function", "method")
        self._eat_type(allow_void=True)
        self._eat_identifier()
        self._eat("(")
        self.compileParameterList()
        self._eat(")")
        self.compileSubroutineBody()
        self._close("subroutineDec")

    def compileParameterList(self) -> None:
        """((type varName) (',' type varName)*)?"""
        self._open("parameterList")
        if not self._next_is(")"):
            self._eat_type()
            self._eat_identifier()
            while self._next_is(","):
                self._eat(",")
                self._eat_type()
                self._eat_identifier()
        self._close("parameterList")

    def compileSubroutineBody(self) -> None:
        """'{' varDec* statements '}'"""
        self._open("subroutineBody")
        self._eat("{")
        while self._next_is("var"):
            self.compileVarDec()
        self.compileStatements()
        self._eat("}")
        self._close("subroutineBody")

    def compileVarDec(self) -> None:
        """'var' type varName (',' varName)* ';'"""
        self._open("varDec")
        self._eat("var")
        self._eat_type()
        self._eat_var_name_list()
        self._close("varDec")

    # ---------- statements ----------

    def compileStatements(self) -> None:
        """statement*"""
        self._open("statements")
        while self._next_is(*STATEMENT_KEYWORDS):
            keyword = self._tk.peek()[1]
            {
                "let": self.compileLet,
                "if": self.compileIf,
                "while": self.compileWhile,
                "do": self.compileDo,
                "return": self.compileReturn,
            }[keyword]()
        self._close("statements")

    def compileLet(self) -> None:
        """'let' varName ('[' expression ']')? '=' expression ';'"""
        self._open("letStatement")
        self._eat("let")
        self._eat_identifier()
        if self._next_is("["):
            self._eat("[")
            self.compileExpression()
            self._eat("]")
        self._eat("=")
        self.compileExpression()
        self._eat(";")
        self._close("letStatement")

    def compileIf(self) -> None:
        """'if' '(' expression ')' '{' statements '}' ('else' '{' statements '}')?"""
        self._open("ifStatement")
        self._eat("if")
        self._eat("(")
        self.compileExpression()
        self._eat(")")
        self._eat("{")
        self.compileStatements()
        self._eat("}")
        if self._next_is("else"):
            self._eat("else")
            self._eat("{")
            self.compileStatements()
            self._eat("}")
        self._close("ifStatement")

    def compileWhile(self) -> None:
        """'while' '(' expression ')' '{' statements '}'"""
        self._open("whileStatement")
        self._eat("while")
        self._eat("(")
        self.compileExpression()
        self._eat(")")
        self._eat("{")
        self.compileStatements()
        self._eat("}")
        self._close("whileStatement")

    def compileDo(self) -> None:
        """'do' subroutineCall ';'"""
        self._open("doStatement")
        self._eat("do")
        self._eat_subroutine_call()
        self._eat(";")
        self._close("doStatement")

    def compileReturn(self) -> None:
        """'return' expression? ';'"""
        self._open("returnStatement")
        self._eat("return")
        if not self._next_is(";"):
            self.compileExpression()
        self._eat(";")
        self._close("returnStatement")

    # ---------- expressions ----------

    def compileExpression(self) -> None:
        """term (op term)*"""
        self._open("expression")
        self.compileTerm()
        while self._next_is(*OPS):
            self._eat()
            self.compileTerm()
        self._close("expression")

    def compileTerm(self) -> None:
        """integerConstant | stringConstant | keywordConstant | varName |
        varName '[' expression ']' | subroutineCall | '(' expression ')' | unaryOp term"""
        self._open("term")
        token_type, text = self._tk.peek()
        if token_type in (TokenType.INT_CONST, TokenType.STRING_CONST):
            self._eat()
        elif token_type is TokenType.KEYWORD and text in KEYWORD_CONSTANTS:
            self._eat()
        elif self._next_is("("):
            self._eat("(")
            self.compileExpression()
            self._eat(")")
        elif self._next_is(*UNARY_OPS):
            self._eat()
            self.compileTerm()
        elif token_type is TokenType.IDENTIFIER:
            # One token of lookahead tells a variable, an array entry and a call apart.
            after = self._tk.peek(2)
            after_text = after[1] if after and after[0] is TokenType.SYMBOL else None
            if after_text == "[":
                self._eat_identifier()
                self._eat("[")
                self.compileExpression()
                self._eat("]")
            elif after_text in ("(", "."):
                self._eat_subroutine_call()
            else:
                self._eat_identifier()
        else:
            raise SyntaxError(f"unexpected token in term: {text!r}")
        self._close("term")

    def compileExpressionList(self) -> int:
        """(expression (',' expression)*)?  Returns the number of expressions."""
        self._open("expressionList")
        count = 0
        if not self._next_is(")"):
            self.compileExpression()
            count = 1
            while self._next_is(","):
                self._eat(",")
                self.compileExpression()
                count += 1
        self._close("expressionList")
        return count

    # ---------- shared pieces (not separate XML elements) ----------

    def _eat_subroutine_call(self) -> None:
        """subroutineName '(' expressionList ')' | (className|varName) '.' subroutineName '(' expressionList ')'"""
        self._eat_identifier()
        if self._next_is("."):
            self._eat(".")
            self._eat_identifier()
        self._eat("(")
        self.compileExpressionList()
        self._eat(")")

    def _eat_type(self, allow_void: bool = False) -> None:
        """'int' | 'char' | 'boolean' | className  (plus 'void' for return types)"""
        keywords = ("int", "char", "boolean", "void") if allow_void else ("int", "char", "boolean")
        if self._next_is(*keywords):
            self._eat()
        else:
            self._eat_identifier()

    def _eat_var_name_list(self) -> None:
        """varName (',' varName)* ';'"""
        self._eat_identifier()
        while self._next_is(","):
            self._eat(",")
            self._eat_identifier()
        self._eat(";")

    # ---------- token / XML helpers ----------

    def _next_is(self, *texts: str) -> bool:
        """True if the next token is a keyword or symbol whose text is one of `texts`."""
        nxt = self._tk.peek()
        return (
            nxt is not None
            and nxt[0] in (TokenType.KEYWORD, TokenType.SYMBOL)
            and nxt[1] in texts
        )

    def _eat(self, *expected: str) -> str:
        """Advance to the next token, check it is one of `expected` (if given), and write it."""
        if expected and not self._next_is(*expected):
            got = self._tk.peek()
            raise SyntaxError(f"expected {' or '.join(expected)}, got {got[1] if got else 'end of file'!r}")
        self._tk.advance()
        self._write(token_xml(self._tk.tokenType(), self._tk.text()))
        return self._tk.text()

    def _eat_identifier(self) -> str:
        nxt = self._tk.peek()
        if nxt is None or nxt[0] is not TokenType.IDENTIFIER:
            raise SyntaxError(f"expected an identifier, got {nxt[1] if nxt else 'end of file'!r}")
        return self._eat()

    def _open(self, tag: str) -> None:
        self._write(f"<{tag}>")
        self._depth += 1

    def _close(self, tag: str) -> None:
        self._depth -= 1
        self._write(f"</{tag}>")

    def _write(self, line: str) -> None:
        self._out.write("  " * self._depth + line + "\n")
