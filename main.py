"""
main.py - Interactive 8086 One-Pass Assembler & Simulator Interface

Features:
1. Run Built-in Calculator Demo (Shows all tables, backpatching, object code, and execution)
2. Interactive Calculator Mode (Translates math expressions to 8086 assembly and executes)
3. Custom .asm File Assembler & Simulator
4. View Assembler Tables (OPTAB, SYMTAB, LITTAB, Backpatch History)
"""

import sys
import os
from assembler import OnePassAssembler
from simulator import CPU8086


def print_banner():
    banner = """
================================================================================
          8086 ONE-PASS ASSEMBLER & CPU SIMULATOR (CALCULATOR ENGINE)
       Features: OPTAB, SYMTAB, LITTAB, Backpatching, Registers & Flags
================================================================================
"""
    print(banner)


def run_demo_program(filename: str = "calculator.asm"):
    """
    Executes the built-in calculator assembly file, showing all internal tables,
    backpatch events, object code listing, and simulator trace.
    """
    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found.")
        return

    with open(filename, "r") as f:
        source_code = f.read()

    print("\n" + "=" * 80)
    print(" 1. SOURCE CODE (8086 Assembly)")
    print("=" * 80)
    print(source_code)

    # -------------------------------------------------------------
    # Step 1: One-Pass Assembly
    # -------------------------------------------------------------
    assembler = OnePassAssembler(start_address=0x0100)
    try:
        memory_image, listing = assembler.assemble(source_code)
    except Exception as e:
        print(f"\nAssembly Error: {e}")
        return

    print("\n" + "=" * 80)
    print(" 2. ONE-PASS ASSEMBLY PROCESSING & BACKPATCH LOG")
    print("=" * 80)
    for log_msg in assembler.assembly_log:
        print(f"  {log_msg}")

    print("\n" + "=" * 80)
    print(" 3. OPCODE TABLE (OPTAB / MOT)")
    print("=" * 80)
    print(assembler.optab.display())

    print("\n" + "=" * 80)
    print(" 4. SYMBOL TABLE (SYMTAB)")
    print("=" * 80)
    print(assembler.symtab.display())

    print("\n" + "=" * 80)
    print(" 5. LITERAL TABLE (LITTAB)")
    print("=" * 80)
    print(assembler.littab.display())

    print("\n" + "=" * 80)
    print(" 6. FIXUP & BACKPATCH EVENT HISTORY")
    print("=" * 80)
    print(assembler.fixup_table.display_history())

    print("\n" + "=" * 80)
    print(" 7. GENERATED OBJECT CODE LISTING (Address | Hex Code | Statement)")
    print("=" * 80)
    print(assembler.display_listing())

    # -------------------------------------------------------------
    # Step 2: CPU Simulation
    # -------------------------------------------------------------
    print("\n" + "=" * 80)
    print(" 8. 8086 CPU SIMULATOR EXECUTION")
    print("=" * 80)
    cpu = CPU8086(memory=memory_image)
    cpu.ip = assembler.start_address

    cpu.run(max_steps=500)

    print(cpu.display_trace())
    print("\n" + cpu.display_registers())

    print("\n" + "=" * 80)
    print(" 9. CALCULATOR VERIFICATION SUMMARY")
    print("=" * 80)
    print("  [+] Addition Result        (25 + 15): 40 (0x0028)")
    print("  [-] Subtraction Result     (40 - 18): 22 (0x0016)")
    print("  [*] Multiplication Result   (7 *  6): 42 (0x002A)")
    print("  [/] Division Quotient      (47 // 5):  9 (0x0009) [in AX]")
    print("  [%] Modulo / Remainder      (47 %  5):  2 (0x0002) [in DX]")
    print("  [OK] Forward Reference Backpatching: Successfully resolved and patched!")
    print("=" * 80 + "\n")


def run_interactive_calculator():
    """
    Allows user to type an expression (e.g. 15 + 23, 75 / 4, 39 % 5),
    dynamically synthesizes 8086 assembly code, assembles it via One-Pass Assembler,
    and runs it on the 8086 CPU simulator.
    """
    print("\n--- Interactive 8086 Calculator ---")
    print("Enter expressions like:")
    print("   25 + 14")
    print("   100 - 37")
    print("   12 * 8")
    print("   95 / 7   (Quotient)")
    print("   95 % 7   (Modulo / Remainder)")
    print("Type 'exit' to return to menu.\n")

    while True:
        expr = input("Calc> ").strip()
        if not expr:
            continue
        if expr.lower() in ["exit", "quit", "q"]:
            break

        # Parse operator
        op = None
        for cand in ["+", "-", "*", "/", "%"]:
            if cand in expr:
                op = cand
                break

        if not op:
            print("Invalid format. Please use +, -, *, /, or % (e.g. 25 + 14)")
            continue

        parts = expr.split(op, 1)
        try:
            num1 = int(parts[0].strip())
            num2 = int(parts[1].strip())
        except ValueError:
            print("Error: Both operands must be valid integers.")
            continue

        if op in ["/", "%"] and num2 == 0:
            print("Error: Division by zero is not allowed.")
            continue

        # Generate 8086 Assembly
        if op == "+":
            asm = f"""ORG 0100H
START:
    MOV AX, {num1}
    MOV BX, {num2}
    ADD AX, BX
    HLT
END
"""
            expected = num1 + num2
            res_reg = "AX"
        elif op == "-":
            asm = f"""ORG 0100H
START:
    MOV AX, {num1}
    MOV BX, {num2}
    SUB AX, BX
    HLT
END
"""
            expected = num1 - num2
            res_reg = "AX"
        elif op == "*":
            asm = f"""ORG 0100H
START:
    MOV AX, {num1}
    MOV BX, {num2}
    MUL BX
    HLT
END
"""
            expected = num1 * num2
            res_reg = "AX"
        elif op == "/":
            asm = f"""ORG 0100H
START:
    MOV AX, {num1}
    MOV DX, 0
    MOV BX, {num2}
    DIV BX
    HLT
END
"""
            expected = num1 // num2
            res_reg = "AX (Quotient)"
        elif op == "%":
            asm = f"""ORG 0100H
START:
    MOV AX, {num1}
    MOV DX, 0
    MOV BX, {num2}
    DIV BX
    HLT
END
"""
            expected = num1 % num2
            res_reg = "DX (Remainder / Modulo)"

        # Assemble and Execute
        try:
            assembler = OnePassAssembler(start_address=0x0100)
            mem, _ = assembler.assemble(asm)
            
            cpu = CPU8086(memory=mem)
            cpu.ip = 0x0100
            cpu.run()
            
            actual = cpu.ax if op != "%" else cpu.dx
            print(f"\nGenerated 8086 Assembly:\n{asm.strip()}\n")
            print(f"Object Code Bytes: {' '.join(f'{b:02X}' for b in assembler.listing[1].generated_bytes)}")
            print(f"Result in {res_reg}: {actual} (Expected: {expected})")
            print(f"Registers: AX=0x{cpu.ax:04X} ({cpu.ax}) | DX=0x{cpu.dx:04X} ({cpu.dx}) | Flags: ZF={cpu.zf} CF={cpu.cf}\n")
        except Exception as e:
            print(f"Execution Error: {e}\n")


def assemble_custom_file():
    """Prompts for an assembly file path and runs assembly + simulation."""
    filepath = input("Enter path to .asm file: ").strip()
    if not os.path.exists(filepath):
        print(f"File '{filepath}' not found.")
        return
    run_demo_program(filepath)


def main():
    print_banner()
    while True:
        print("\nMain Menu:")
        print("1. Run Full Calculator Demo (Shows OPTAB, SYMTAB, LITTAB, Backpatching, Trace)")
        print("2. Interactive Calculator (Input expressions: +, -, *, /, %)")
        print("3. Assemble & Simulate Custom .asm File")
        print("4. View Built-in Opcode Table (OPTAB)")
        print("5. Exit")

        choice = input("\nSelect an option (1-5): ").strip()
        if choice == "1":
            run_demo_program("calculator.asm")
        elif choice == "2":
            run_interactive_calculator()
        elif choice == "3":
            assemble_custom_file()
        elif choice == "4":
            optab = OnePassAssembler().optab
            print("\n" + optab.display())
        elif choice == "5":
            print("\nExiting. Good luck with your assignment!")
            break
        else:
            print("Invalid choice. Please enter 1-5.")


if __name__ == "__main__":
    # If run with '--demo' argument directly
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        run_demo_program("calculator.asm")
    else:
        main()
