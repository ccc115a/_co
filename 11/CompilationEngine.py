"""CompilationEngine (Project 11): parses one Jack class and writes its VM code.

Same recursive-descent structure as the Project 10 parser, but each compileXxx
routine now emits VM commands through VMWriter instead of XML, and uses the
SymbolTable to map every variable to a VM segment and index.
"""

from JackTokenizer import JackTokenizer, TokenType
from SymbolTable import SEGMENT_OF_KIND, Kind, SymbolTable
from VMWriter import VMWriter

BINARY_OPS = {
    "+": ("add",),
    "-": ("sub",),
    "&": ("and",),
    "|": ("or",),
    "<": ("lt",),
    ">": ("gt",),
    "=": ("eq",),
    "*": ("call", "Math.multiply"),
    "/": ("call", "Math.divide"),
}
UNARY_OPS = {"-": "neg", "~": "not"}
STATEMENT_KEYWORDS = frozenset({"let", "if", "while", "do", "return"})


class CompilationEngine:
    def __init__(self, tokenizer: JackTokenizer, writer: VMWriter) -> None:
        self._tk = tokenizer
        self._vm = writer
        self._symbols = SymbolTable()
        self._class_name = ""
        self._label_count = 0

    # ---------- program structure ----------

    def compileClass(self) -> None:
        """'class' className '{' classVarDec* subroutineDec* '}'"""
        self._expect("class")
        self._class_name = self._expect_identifier()
        self._expect("{")
        while self._next_is("static", "field"):
            self.compileClassVarDec()
        while self._next_is("constructor", "function", "method"):
            self.compileSubroutine()
        self._expect("}")

    def compileClassVarDec(self) -> None:
        """('static' | 'field') type varName (',' varName)* ';'"""
        kind = Kind.STATIC if self._expect("static", "field") == "static" else Kind.FIELD
        self._define_var_list(kind)

    def compileSubroutine(self) -> None:
        """('constructor'|'function'|'method') ('void'|type) subroutineName '(' parameterList ')' subroutineBody"""
        subroutine_kind = self._expect("constructor", "function", "method")
        self._expect_type(allow_void=True)
        name = self._expect_identifier()

        self._symbols.reset()
        if subroutine_kind == "method":
            # The object a method runs on is passed as argument 0.
            self._symbols.define("this", self._class_name, Kind.ARG)

        self._expect("(")
        self.compileParameterList()
        self._expect(")")
        self.compileSubroutineBody(f"{self._class_name}.{name}", subroutine_kind)

    def compileParameterList(self) -> None:
        """((type varName) (',' type varName)*)?"""
        if self._next_is(")"):
            return
        while True:
            type_ = self._expect_type()
            self._symbols.define(self._expect_identifier(), type_, Kind.ARG)
            if not self._next_is(","):
                return
            self._expect(",")

    def compileSubroutineBody(self, full_name: str, subroutine_kind: str) -> None:
        """'{' varDec* statements '}'"""
        self._expect("{")
        while self._next_is("var"):
            self.compileVarDec()

        # The local count is known only after all varDecs, so `function` is written here.
        self._vm.writeFunction(full_name, self._symbols.varCount(Kind.VAR))
        if subroutine_kind == "constructor":
            # Allocate one word per field and make `this` point at the new block.
            self._vm.writePush("constant", self._symbols.varCount(Kind.FIELD))
            self._vm.writeCall("Memory.alloc", 1)
            self._vm.writePop("pointer", 0)
        elif subroutine_kind == "method":
            # Set `this` to the object passed in argument 0.
            self._vm.writePush("argument", 0)
            self._vm.writePop("pointer", 0)

        self.compileStatements()
        self._expect("}")

    def compileVarDec(self) -> None:
        """'var' type varName (',' varName)* ';'"""
        self._expect("var")
        self._define_var_list(Kind.VAR)

    # ---------- statements ----------

    def compileStatements(self) -> None:
        """statement*"""
        while self._next_is(*STATEMENT_KEYWORDS):
            {
                "let": self.compileLet,
                "if": self.compileIf,
                "while": self.compileWhile,
                "do": self.compileDo,
                "return": self.compileReturn,
            }[self._tk.peek()[1]]()

    def compileLet(self) -> None:
        """'let' varName ('[' expression ']')? '=' expression ';'"""
        self._expect("let")
        name = self._expect_identifier()

        if self._next_is("["):
            # Target address = base + index, computed before the right-hand side.
            self._expect("[")
            self._push_variable(name)
            self.compileExpression()
            self._expect("]")
            self._vm.writeArithmetic("add")
            self._expect("=")
            self.compileExpression()
            self._expect(";")
            # The right-hand side may itself use pointer 1 (e.g. a[i] = b[j]),
            # so park its value in temp 0 and only then set THAT.
            self._vm.writePop("temp", 0)
            self._vm.writePop("pointer", 1)
            self._vm.writePush("temp", 0)
            self._vm.writePop("that", 0)
        else:
            self._expect("=")
            self.compileExpression()
            self._expect(";")
            self._pop_variable(name)

    def compileIf(self) -> None:
        """'if' '(' expression ')' '{' statements '}' ('else' '{' statements '}')?"""
        else_label, end_label = self._new_label("IF_ELSE"), self._new_label("IF_END")
        self._expect("if")
        self._expect("(")
        self.compileExpression()
        self._expect(")")
        self._vm.writeArithmetic("not")
        self._vm.writeIf(else_label)
        self._expect("{")
        self.compileStatements()
        self._expect("}")
        self._vm.writeGoto(end_label)
        self._vm.writeLabel(else_label)
        if self._next_is("else"):
            self._expect("else")
            self._expect("{")
            self.compileStatements()
            self._expect("}")
        self._vm.writeLabel(end_label)

    def compileWhile(self) -> None:
        """'while' '(' expression ')' '{' statements '}'"""
        top_label, end_label = self._new_label("WHILE_EXP"), self._new_label("WHILE_END")
        self._expect("while")
        self._vm.writeLabel(top_label)
        self._expect("(")
        self.compileExpression()
        self._expect(")")
        self._vm.writeArithmetic("not")
        self._vm.writeIf(end_label)
        self._expect("{")
        self.compileStatements()
        self._expect("}")
        self._vm.writeGoto(top_label)
        self._vm.writeLabel(end_label)

    def compileDo(self) -> None:
        """'do' subroutineCall ';'  (the returned value is discarded)"""
        self._expect("do")
        self._compile_subroutine_call(self._expect_identifier())
        self._expect(";")
        self._vm.writePop("temp", 0)

    def compileReturn(self) -> None:
        """'return' expression? ';'  (void subroutines return 0)"""
        self._expect("return")
        if self._next_is(";"):
            self._vm.writePush("constant", 0)
        else:
            self.compileExpression()
        self._expect(";")
        self._vm.writeReturn()

    # ---------- expressions ----------

    def compileExpression(self) -> None:
        """term (op term)*  -- evaluated left to right, as Jack has no precedence."""
        self.compileTerm()
        while self._next_is(*BINARY_OPS):
            op = self._expect(*BINARY_OPS)
            self.compileTerm()
            command = BINARY_OPS[op]
            if command[0] == "call":
                self._vm.writeCall(command[1], 2)
            else:
                self._vm.writeArithmetic(command[0])

    def compileTerm(self) -> None:
        token_type, text = self._tk.peek()

        if token_type is TokenType.INT_CONST:
            self._tk.advance()
            self._vm.writePush("constant", self._tk.intVal())
        elif token_type is TokenType.STRING_CONST:
            self._tk.advance()
            self._compile_string(self._tk.stringVal())
        elif self._next_is("true"):
            self._expect("true")
            self._vm.writePush("constant", 0)
            self._vm.writeArithmetic("not")  # true is -1 (all bits on)
        elif self._next_is("false", "null"):
            self._expect("false", "null")
            self._vm.writePush("constant", 0)
        elif self._next_is("this"):
            self._expect("this")
            self._vm.writePush("pointer", 0)
        elif self._next_is("("):
            self._expect("(")
            self.compileExpression()
            self._expect(")")
        elif self._next_is(*UNARY_OPS):
            op = self._expect(*UNARY_OPS)
            self.compileTerm()
            self._vm.writeArithmetic(UNARY_OPS[op])
        elif token_type is TokenType.IDENTIFIER:
            name = self._expect_identifier()
            if self._next_is("["):
                # arr[i]: push arr + i, point THAT at it, read that 0.
                self._expect("[")
                self._push_variable(name)
                self.compileExpression()
                self._expect("]")
                self._vm.writeArithmetic("add")
                self._vm.writePop("pointer", 1)
                self._vm.writePush("that", 0)
            elif self._next_is("(", "."):
                self._compile_subroutine_call(name)
            else:
                self._push_variable(name)
        else:
            raise SyntaxError(f"unexpected token in term: {text!r}")

    def compileExpressionList(self) -> int:
        """(expression (',' expression)*)?  Pushes each value; returns how many."""
        if self._next_is(")"):
            return 0
        self.compileExpression()
        count = 1
        while self._next_is(","):
            self._expect(",")
            self.compileExpression()
            count += 1
        return count

    # ---------- code generation helpers ----------

    def _compile_subroutine_call(self, first_name: str) -> None:
        """Compile a call whose first identifier has already been read.

        foo(...)        -> method of this class: push this, call Cls.foo n+1
        obj.foo(...)    -> obj is a variable: push obj, call ObjType.foo n+1
        Cls.foo(...)    -> function or constructor: call Cls.foo n
        """
        n_args = 0
        if self._next_is("."):
            self._expect(".")
            subroutine = self._expect_identifier()
            symbol = self._symbols.lookup(first_name)
            if symbol is not None:
                self._push_variable(first_name)
                full_name = f"{symbol.type}.{subroutine}"
                n_args = 1
            else:
                full_name = f"{first_name}.{subroutine}"
        else:
            self._vm.writePush("pointer", 0)
            full_name = f"{self._class_name}.{first_name}"
            n_args = 1

        self._expect("(")
        n_args += self.compileExpressionList()
        self._expect(")")
        self._vm.writeCall(full_name, n_args)

    def _compile_string(self, text: str) -> None:
        """Build a String object: String.new(len), then appendChar for each character."""
        self._vm.writePush("constant", len(text))
        self._vm.writeCall("String.new", 1)
        for ch in text:
            self._vm.writePush("constant", ord(ch))
            self._vm.writeCall("String.appendChar", 2)

    def _push_variable(self, name: str) -> None:
        symbol = self._symbols.lookup(name)
        if symbol is None:
            raise NameError(f"{self._class_name}: undefined variable {name!r}")
        self._vm.writePush(SEGMENT_OF_KIND[symbol.kind], symbol.index)

    def _pop_variable(self, name: str) -> None:
        symbol = self._symbols.lookup(name)
        if symbol is None:
            raise NameError(f"{self._class_name}: undefined variable {name!r}")
        self._vm.writePop(SEGMENT_OF_KIND[symbol.kind], symbol.index)

    def _define_var_list(self, kind: Kind) -> None:
        """type varName (',' varName)* ';'  -- adds each name to the symbol table."""
        type_ = self._expect_type()
        self._symbols.define(self._expect_identifier(), type_, kind)
        while self._next_is(","):
            self._expect(",")
            self._symbols.define(self._expect_identifier(), type_, kind)
        self._expect(";")

    def _new_label(self, prefix: str) -> str:
        """A label unique within this class (VM labels are scoped per function anyway)."""
        label = f"{prefix}{self._label_count}"
        self._label_count += 1
        return label

    # ---------- token helpers ----------

    def _next_is(self, *texts: str) -> bool:
        nxt = self._tk.peek()
        return (
            nxt is not None
            and nxt[0] in (TokenType.KEYWORD, TokenType.SYMBOL)
            and nxt[1] in texts
        )

    def _expect(self, *texts: str) -> str:
        if not self._next_is(*texts):
            got = self._tk.peek()
            raise SyntaxError(
                f"{self._class_name}: expected {' or '.join(texts)}, "
                f"got {got[1] if got else 'end of file'!r}"
            )
        self._tk.advance()
        return self._tk.text()

    def _expect_identifier(self) -> str:
        nxt = self._tk.peek()
        if nxt is None or nxt[0] is not TokenType.IDENTIFIER:
            raise SyntaxError(
                f"{self._class_name}: expected an identifier, "
                f"got {nxt[1] if nxt else 'end of file'!r}"
            )
        self._tk.advance()
        return self._tk.text()

    def _expect_type(self, allow_void: bool = False) -> str:
        keywords = ("int", "char", "boolean", "void") if allow_void else ("int", "char", "boolean")
        if self._next_is(*keywords):
            return self._expect(*keywords)
        return self._expect_identifier()
