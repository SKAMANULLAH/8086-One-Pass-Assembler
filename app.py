"""
app.py - Flask Web Server & API for 8086 One-Pass Assembler and CPU Simulator
Exposes REST endpoints for:
1. Interactive Calculator expression evaluation
2. Custom 8086 Assembly code compilation & CPU emulation
3. Inspection of internal tables (OPTAB, SYMTAB, LITTAB, FixupTable)
"""

import os
import re
import argparse
from typing import Dict, Any, Tuple
from flask import Flask, render_template, request, jsonify

from assembler import OnePassAssembler
from simulator import CPU8086
from structures import OpcodeTable

app = Flask(__name__)


def serialize_assembler_state(assembler: OnePassAssembler) -> Dict[str, Any]:
    """Helper to serialize internal assembler structures into JSON-friendly dicts."""
    # SYMTAB
    symtab_list = []
    for name, entry in sorted(assembler.symtab.table.items()):
        symtab_list.append({
            "name": entry.name,
            "address": f"0x{entry.address:04X}" if entry.address is not None else "UNRESOLVED",
            "defined": entry.defined,
            "references": [f"0x{ref:04X}" for ref in entry.references]
        })

    # LITTAB
    littab_list = []
    for entry in assembler.littab.literals:
        littab_list.append({
            "literal": entry.literal,
            "value": entry.value,
            "address": f"0x{entry.address:04X}" if entry.address is not None else "PENDING",
            "allocated": entry.allocated
        })

    # Fixup History (Backpatch events)
    fixup_history = []
    for event in assembler.fixup_table.backpatch_history:
        fixup_history.append({
            "symbol": event["symbol"],
            "target_address": f"0x{event['target_address']:04X}",
            "patched_at": f"0x{event['patched_at']:04X}",
            "instruction_lc": f"0x{event['instruction_lc']:04X}"
        })

    # Listing
    listing_list = []
    for line in assembler.listing:
        hex_bytes = " ".join(f"{b:02X}" for b in line.generated_bytes)
        listing_list.append({
            "line_no": line.line_no,
            "lc": f"0x{line.lc:04X}",
            "bytes": hex_bytes,
            "source": line.raw_line
        })

    return {
        "symtab": symtab_list,
        "littab": littab_list,
        "fixup_history": fixup_history,
        "listing": listing_list,
        "log": assembler.assembly_log
    }


def serialize_cpu_state(cpu: CPU8086) -> Dict[str, Any]:
    """Helper to serialize 8086 CPU registers, flags, and trace."""
    sp_val = cpu.get_reg16(4)
    bp_val = cpu.get_reg16(5)
    si_val = cpu.get_reg16(6)
    di_val = cpu.get_reg16(7)
    return {
        "registers": {
            "AX": {"hex": f"0x{cpu.ax:04X}", "dec": cpu.ax, "high": f"0x{cpu.ah:02X}", "low": f"0x{cpu.al:02X}"},
            "BX": {"hex": f"0x{cpu.bx:04X}", "dec": cpu.bx, "high": f"0x{cpu.bh:02X}", "low": f"0x{cpu.bl:02X}"},
            "CX": {"hex": f"0x{cpu.cx:04X}", "dec": cpu.cx, "high": f"0x{cpu.ch:02X}", "low": f"0x{cpu.cl:02X}"},
            "DX": {"hex": f"0x{cpu.dx:04X}", "dec": cpu.dx, "high": f"0x{cpu.dh:02X}", "low": f"0x{cpu.dl:02X}"},
            "SP": {"hex": f"0x{sp_val:04X}", "dec": sp_val},
            "BP": {"hex": f"0x{bp_val:04X}", "dec": bp_val},
            "SI": {"hex": f"0x{si_val:04X}", "dec": si_val},
            "DI": {"hex": f"0x{di_val:04X}", "dec": di_val},
            "IP": {"hex": f"0x{cpu.ip:04X}", "dec": cpu.ip},
        },
        "flags": {
            "ZF": cpu.zf,
            "SF": cpu.sf,
            "CF": cpu.cf,
            "OF": cpu.of
        },
        "halted": cpu.halted,
        "step_count": cpu.step_count,
        "trace": cpu.execution_trace
    }


def get_optab_list():
    """Returns static OPTAB entries for UI inspector."""
    optab = OpcodeTable()
    optab_list = []
    for mnemonic, entries in sorted(optab.table.items()):
        for e in entries:
            optab_list.append({
                "mnemonic": e.mnemonic,
                "opcode": f"0x{e.opcode:02X}",
                "size": e.size,
                "format": e.operands_format,
                "description": e.description
            })
    return optab_list


@app.route("/")
def index():
    """Serves the Single Page Application."""
    return render_template("index.html")


@app.route("/health")
def health():
    """Health check endpoint for AWS EC2 monitoring / load balancer."""
    return jsonify({"status": "healthy", "service": "8086-one-pass-simulator"})


@app.route("/api/tables", methods=["GET"])
def get_tables():
    """Returns built-in system tables (e.g. OPTAB) on page load."""
    return jsonify({
        "success": True,
        "optab": get_optab_list()
    })


@app.route("/api/sample-asm", methods=["GET"])
def get_sample_asm():
    """Returns the pre-packaged calculator.asm file."""
    asm_path = os.path.join(os.path.dirname(__file__), "calculator.asm")
    if os.path.exists(asm_path):
        with open(asm_path, "r") as f:
            content = f.read()
        return jsonify({"success": True, "source": content, "filename": "calculator.asm"})
    return jsonify({"success": False, "error": "calculator.asm not found"}), 404


@app.route("/api/calculate", methods=["POST"])
def calculate():
    """
    Parses a simple math expression (e.g. '45 + 17', '95 / 6', '95 % 6'),
    generates 8086 assembly, assembles it via OnePassAssembler, and executes it.
    """
    data = request.get_json(force=True, silent=True) or {}
    expr = data.get("expression", "").strip()

    if not expr:
        num1 = data.get("num1")
        op = data.get("op")
        num2 = data.get("num2")
    else:
        # Match pattern: num1 op num2
        match = re.match(r"^\s*(\d+)\s*([\+\-\*/%])\s*(\d+)\s*$", expr)
        if not match:
            return jsonify({
                "success": False,
                "error": f"Invalid expression '{expr}'. Format: <number> <operator> <number> (e.g., 45 + 17, 95 / 6, 95 % 6)"
            }), 400
        num1, op, num2 = int(match.group(1)), match.group(2), int(match.group(3))

    num1 = int(num1)
    num2 = int(num2)

    # 16-bit unsigned bounds
    if not (0 <= num1 <= 65535 and 0 <= num2 <= 65535):
        return jsonify({
            "success": False,
            "error": "Operands must be within 16-bit range (0 to 65535)."
        }), 400

    if op in ["/", "%"] and num2 == 0:
        return jsonify({
            "success": False,
            "error": "Division by zero is not permitted in 8086 processor."
        }), 400

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
        expected = (num1 + num2) & 0xFFFF
        res_reg = "AX"
        op_name = "Addition"
    elif op == "-":
        asm = f"""ORG 0100H
START:
    MOV AX, {num1}
    MOV BX, {num2}
    SUB AX, BX
    HLT
END
"""
        expected = (num1 - num2) & 0xFFFF
        res_reg = "AX"
        op_name = "Subtraction"
    elif op == "*":
        asm = f"""ORG 0100H
START:
    MOV AX, {num1}
    MOV BX, {num2}
    MUL BX
    HLT
END
"""
        expected = (num1 * num2) & 0xFFFF
        res_reg = "AX (Low 16-bit product)"
        op_name = "Multiplication"
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
        op_name = "Division"
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
        op_name = "Modulo"
    else:
        return jsonify({"success": False, "error": f"Unsupported operator '{op}'"}), 400

    # Assemble & Execute
    try:
        assembler = OnePassAssembler(start_address=0x0100)
        memory_image, _ = assembler.assemble(asm)

        cpu = CPU8086(memory=memory_image)
        cpu.ip = 0x0100
        cpu.run(max_steps=500)

        actual = cpu.dx if op == "%" else cpu.ax
        asm_state = serialize_assembler_state(assembler)
        cpu_state = serialize_cpu_state(cpu)

        return jsonify({
            "success": True,
            "expression": f"{num1} {op} {num2}",
            "operator": op,
            "operation_name": op_name,
            "num1": num1,
            "num2": num2,
            "expected": expected,
            "result": actual,
            "result_reg": res_reg,
            "asm_code": asm,
            "assembler": asm_state,
            "cpu": cpu_state
        })

    except Exception as e:
        return jsonify({"success": False, "error": f"Assembly/Execution error: {str(e)}"}), 500


@app.route("/api/assemble-and-run", methods=["POST"])
def assemble_and_run():
    """
    Assembles user-provided 8086 assembly source code in one pass,
    backpatches forward references, and simulates CPU execution.
    """
    data = request.get_json(force=True, silent=True) or {}
    source_code = data.get("source_code", "").strip()

    if not source_code:
        return jsonify({"success": False, "error": "Source code cannot be empty."}), 400

    try:
        assembler = OnePassAssembler(start_address=0x0100)
        memory_image, _ = assembler.assemble(source_code)
    except Exception as e:
        return jsonify({
            "success": False,
            "error_phase": "assembler",
            "error": f"Assembly Error: {str(e)}"
        }), 400

    try:
        cpu = CPU8086(memory=memory_image)
        cpu.ip = assembler.start_address
        cpu.run(max_steps=2000)
    except Exception as e:
        return jsonify({
            "success": False,
            "error_phase": "simulator",
            "error": f"CPU Simulation Error: {str(e)}"
        }), 500

    asm_state = serialize_assembler_state(assembler)
    cpu_state = serialize_cpu_state(cpu)

    return jsonify({
        "success": True,
        "assembler": asm_state,
        "cpu": cpu_state
    })


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run 8086 Web Simulator")
    parser.add_argument("--host", default="0.0.0.0", help="Binding host")
    parser.add_argument("--port", type=int, default=5000, help="Port to run server on")
    args = parser.parse_args()

    print(f"[INFO] Starting 8086 Assembler & Simulator Web Server on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)
