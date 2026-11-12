import sys
from pathlib import Path


# C 指令的運算欄位，共 7 位元。
COMP = {
    "0":   "0101010",
    "1":   "0111111",
    "-1":  "0111010",
    "D":   "0001100",
    "A":   "0110000",
    "M":   "1110000",
    "!D":  "0001101",
    "!A":  "0110001",
    "!M":  "1110001",
    "-D":  "0001111",
    "-A":  "0110011",
    "-M":  "1110011",
    "D+1": "0011111",
    "A+1": "0110111",
    "M+1": "1110111",
    "D-1": "0001110",
    "A-1": "0110010",
    "M-1": "1110010",
    "D+A": "0000010",
    "D+M": "1000010",
    "D-A": "0010011",
    "D-M": "1010011",
    "A-D": "0000111",
    "M-D": "1000111",
    "D&A": "0000000",
    "D&M": "1000000",
    "D|A": "0010101",
    "D|M": "1010101",
}

# C 指令的目的地欄位，共 3 位元。
DEST = {
    "":    "000",
    "M":   "001",
    "D":   "010",
    "MD":  "011",
    "DM":  "011",
    "A":   "100",
    "AM":  "101",
    "AD":  "110",
    "AMD": "111",
    "ADM": "111",
}

# C 指令的跳躍欄位，共 3 位元。
JUMP = {
    "":    "000",
    "JGT": "001",
    "JEQ": "010",
    "JGE": "011",
    "JLT": "100",
    "JNE": "101",
    "JLE": "110",
    "JMP": "111",
}


def create_symbol_table():
    """建立預定義符號表，每次組譯都使用新的表。"""
    symbols = {
        "SP": 0,
        "LCL": 1,
        "ARG": 2,
        "THIS": 3,
        "THAT": 4,
        "SCREEN": 16384,
        "KBD": 24576,
    }

    for number in range(16):
        symbols[f"R{number}"] = number

    return symbols


def read_commands(source_path):
    """讀取來源檔，移除註解與空白。"""
    commands = []

    with source_path.open("r", encoding="utf-8-sig") as source:
        for line in source:
            # 只保留 // 之前的內容。
            line = line.split("//", 1)[0]

            # 移除空格、Tab 和換行字元。
            command = "".join(line.split())

            if command:
                commands.append(command)

    return commands


def collect_labels(commands, symbols):
    """第一趟掃描，記錄標籤並收集真正的指令。"""
    instructions = []

    for command in commands:
        if command.startswith("("):
            # 例如 (LOOP) 取出 LOOP。
            label = command[1:-1]

            # 已收集的指令數，就是下一條指令的 ROM 位址。
            symbols[label] = len(instructions)
        else:
            instructions.append(command)

    return instructions


def encode_c_instruction(command):
    """將 dest=comp;jump 轉換成 16 位元機器碼。"""
    dest = ""
    jump = ""

    # 先拆出跳躍欄位，例如 D=M;JGT。
    if ";" in command:
        command, jump = command.split(";", 1)

    # 再拆出目的地欄位。
    if "=" in command:
        dest, comp = command.split("=", 1)
    else:
        comp = command

    return "111" + COMP[comp] + DEST[dest] + JUMP[jump]


def translate(instructions, symbols):
    """第二趟掃描，配置變數位址並產生機器碼。"""
    machine_code = []
    next_variable_address = 16

    for instruction in instructions:
        if instruction.startswith("@"):
            value = instruction[1:]

            if value.isdecimal():
                address = int(value)
            else:
                # 第一趟已記錄所有標籤，因此未知符號是新變數。
                if value not in symbols:
                    symbols[value] = next_variable_address
                    next_variable_address += 1

                address = symbols[value]

            # 合法 A 指令的位址範圍是 0～32767。
            binary = format(address, "016b")
        else:
            binary = encode_c_instruction(instruction)

        machine_code.append(binary)

    return machine_code


def assemble(source_path):
    """將來源 .asm 組譯成同一資料夾下的同名 .hack。"""
    source_path = Path(source_path)
    output_path = source_path.with_suffix(".hack")

    commands = read_commands(source_path)
    symbols = create_symbol_table()

    # 第一趟，處理標籤。
    instructions = collect_labels(commands, symbols)

    # 第二趟，轉換指令及處理變數。
    machine_code = translate(instructions, symbols)

    # 使用 w 模式，已有同名檔案時會覆寫。
    with output_path.open(
        "w", encoding="ascii", newline="\n"
    ) as output:
        for instruction in machine_code:
            output.write(instruction + "\n")

    return output_path


def main():
    if len(sys.argv) != 2:
        print("使用方式：python assembler.py Prog.asm", file=sys.stderr)
        return 1

    source_path = Path(sys.argv[1])

    if source_path.suffix.lower() != ".asm":
        print("請提供 .asm 檔案。", file=sys.stderr)
        return 1

    output_path = assemble(source_path)
    print(f"組譯完成：{output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())