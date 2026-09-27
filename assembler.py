"""
assembler.py - 8086 One-Pass Assembler Implementation

Implements:
- Single sequential scan (One-Pass Assembler)
- Forward reference resolution via Backpatching / Fixup Table
- Symbol Table (SYMTAB), Opcode Table (OPTAB), Literal Table (LITTAB)
- Object Code generation and Assembly Listing
"""

import re
from typing import Dict, List, Tuple, Optional, Any
from structures import OpcodeTable, SymbolTable, LiteralTable, FixupTable


# 8086 16-bit Register to ID mapping (Standard 8086 architecture)
REGISTER_MAP_16 = {
    "AX": 0, "CX": 1, "DX": 2, "BX": 3,
    "SP": 4, "BP": 5, "SI": 6, "DI": 7
}

REGISTER_MAP_8 = {
    "AL": 0, "CL": 1, "DL": 2, "BL": 3,
    "AH": 4, "CH": 5, "DH": 6, "BH": 7
}


class AssemblyLine:
    """Represents a single parsed line of 8086 assembly."""
    def __init__(self, raw_line: str, line_no: int):
        self.raw_line = raw_line
        self.line_no = line_no
        self.label: Optional[str] = None
        self.mnemonic: Optional[str] = None
        self.operands: List[str] = []
        self.comment: Optional[str] = None
        self.lc: int = 0
        self.generated_bytes: bytearray = bytearray()


class OnePassAssembler:
    """
    8086 One-Pass Assembler
    Processes assembly code in ONE pass from start to finish.
    Unresolved forward references are placed in the FixupTable and backpatched
    the exact moment their target label is encountered.
    """
    def __init__(self, start_address: int = 0x0100):
        self.optab = OpcodeTable()
        self.symtab = SymbolTable()
        self.littab = LiteralTable()
        self.fixup_table = FixupTable()
        
        self.start_address = start_address
        self.lc = start_address  # Location Counter
        self.memory = bytearray(65536)  # 64 KB memory image
        self.listing: List[AssemblyLine] = []
        self.assembly_log: List[str] = []

    def parse_line(self, raw_line: str, line_no: int) -> Optional[AssemblyLine]:
        """
        Parses a single assembly line into:
        [Label:] [Mnemonic] [Operands] [; Comment]
        """
        line_obj = AssemblyLine(raw_line, line_no)
        content = raw_line.strip()
        
        # Check for comments
        if ";" in content:
            parts = content.split(";", 1)
            content = parts[0].strip()
            line_obj.comment = parts[1].strip()

        if not content:
            # Empty line or comment-only
            return None if line_obj.comment is None else line_obj

        # Check for label (e.g. "START:" or "LOOP1:")
        if ":" in content:
            label_part, rest = content.split(":", 1)
            line_obj.label = label_part.strip().upper()
            content = rest.strip()
        elif " " in content:
            # Check if first word is a label without colon (e.g. "VAR1 DW 5")
            first_token = content.split()[0].upper()
            if first_token in ["DB", "DW", "ORG", "END"] or self.optab.lookup(first_token):
                pass  # It's an instruction or directive
            elif len(content.split()) > 1 and content.split()[1].upper() in ["DB", "DW", "EQU"]:
                line_obj.label = first_token
                content = content[len(first_token):].strip()

        if not content:
            return line_obj

        # Extract mnemonic and operands
        tokens = content.split(None, 1)
        line_obj.mnemonic = tokens[0].upper()
        
        if len(tokens) > 1:
            operands_str = tokens[1].strip()
            # Split operands by comma (preserving bracketed content)
            raw_ops = [op.strip() for op in operands_str.split(",")]
            line_obj.operands = raw_ops

        return line_obj

    def parse_number(self, value_str: str) -> int:
        """Parses decimal, hexadecimal (e.g. 0x10 or 10H), or binary (e.g. 1010B)."""
        val = value_str.strip().upper()
        if val.startswith("0X"):
            return int(val, 16)
        elif val.endswith("H"):
            return int(val[:-1], 16)
        elif val.endswith("B") and all(c in "01" for c in val[:-1]):
            return int(val[:-1], 2)
        else:
            return int(val)

    def assemble(self, source_code: str) -> Tuple[bytearray, List[AssemblyLine]]:
        """
        Runs the ONE-PASS assembly algorithm on source code.
        """
        lines = source_code.splitlines()
        self.lc = self.start_address
        self.listing = []
        self.assembly_log = []

        for line_no, raw_line in enumerate(lines, start=1):
            line_obj = self.parse_line(raw_line, line_no)
            if line_obj is None or (line_obj.mnemonic is None and line_obj.label is None):
                continue

            line_obj.lc = self.lc

            # STEP 1: Handle Label Definition
            if line_obj.label:
                label_name = line_obj.label
                existing_sym = self.symtab.lookup(label_name)
                
                if existing_sym and existing_sym.defined:
                    raise ValueError(f"Duplicate symbol definition: '{label_name}' at line {line_no}")

                # Insert/Update in Symbol Table with current Location Counter
                self.symtab.insert(label_name, address=self.lc, defined=True)
                self.assembly_log.append(f"[Line {line_no:2d}] Defined Symbol '{label_name}' at 0x{self.lc:04X}")

                # BACKPATCHING: Check if there are any forward references waiting for this label!
                patched_entries = self.fixup_table.backpatch(label_name, self.lc, self.memory)
                for entry in patched_entries:
                    self.assembly_log.append(
                        f"           ---> [BACKPATCH] Overwrote placeholder at 0x{entry.patch_address:04X} "
                        f"with resolved target address 0x{self.lc:04X}"
                    )

            # If no mnemonic (just a label line), continue
            if not line_obj.mnemonic:
                self.listing.append(line_obj)
                continue

            # STEP 2: Handle Assembler Directives
            mnemonic = line_obj.mnemonic
            if mnemonic == "ORG":
                if not line_obj.operands:
                    raise ValueError(f"ORG requires an address at line {line_no}")
                self.lc = self.parse_number(line_obj.operands[0])
                line_obj.lc = self.lc
                self.assembly_log.append(f"[Line {line_no:2d}] ORG directive set LC to 0x{self.lc:04X}")
                self.listing.append(line_obj)
                continue

            elif mnemonic == "DB":  # Define Byte
                if not line_obj.operands:
                    raise ValueError(f"DB requires a value at line {line_no}")
                val = self.parse_number(line_obj.operands[0]) & 0xFF
                self.memory[self.lc] = val
                line_obj.generated_bytes.append(val)
                self.lc += 1
                self.listing.append(line_obj)
                continue

            elif mnemonic == "DW":  # Define Word (16-bit)
                if not line_obj.operands:
                    raise ValueError(f"DW requires a value at line {line_no}")
                val = self.parse_number(line_obj.operands[0]) & 0xFFFF
                low = val & 0xFF
                high = (val >> 8) & 0xFF
                self.memory[self.lc] = low
                self.memory[self.lc + 1] = high
                line_obj.generated_bytes.extend([low, high])
                self.lc += 2
                self.listing.append(line_obj)
                continue

            elif mnemonic == "END":
                # Allocate pool for any literals in LITTAB
                new_lc = self.littab.allocate_pool(self.lc)
                for entry in self.littab.literals:
                    if entry.address is not None and entry.address >= self.lc:
                        val = entry.value & 0xFFFF
                        low = val & 0xFF
                        high = (val >> 8) & 0xFF
                        self.memory[entry.address] = low
                        self.memory[entry.address + 1] = high
                        self.assembly_log.append(
                            f"[END] Allocated Literal '{entry.literal}' at 0x{entry.address:04X} = {val}"
                        )
                self.lc = new_lc
                self.listing.append(line_obj)
                break

            # STEP 3: Handle Machine Instructions
            self._assemble_instruction(line_obj)
            self.listing.append(line_obj)

        # Final check: any unpatched forward references?
        if self.fixup_table.has_unresolved():
            unresolved = list(self.fixup_table.pending_fixups.keys())
            raise ValueError(f"Error: Unresolved forward references at end of assembly: {unresolved}")

        return self.memory, self.listing

    def _assemble_instruction(self, line_obj: AssemblyLine):
        """Assembles a single instruction and writes object code to memory."""
        mnem = line_obj.mnemonic
        ops = line_obj.operands
        start_lc = self.lc

        # -------------------------------------------------------------
        # HLT & NOP (No operands)
        # -------------------------------------------------------------
        if mnem == "HLT":
            self.memory[self.lc] = 0xF4
            line_obj.generated_bytes.append(0xF4)
            self.lc += 1
            return

        if mnem == "NOP":
            self.memory[self.lc] = 0x90
            line_obj.generated_bytes.append(0x90)
            self.lc += 1
            return

        # -------------------------------------------------------------
        # Branch Instructions: JMP, JE, JZ, JNE, JNZ
        # Explicit Forward Reference / Backpatching Demonstration!
        # -------------------------------------------------------------
        if mnem in ["JMP", "JE", "JZ", "JNE", "JNZ"]:
            if len(ops) != 1:
                raise ValueError(f"{mnem} requires 1 label operand at line {line_obj.line_no}")
            target_label = ops[0].upper()
            
            opcode = 0xEA if mnem == "JMP" else (0x74 if mnem in ["JE", "JZ"] else 0x75)
            self.memory[self.lc] = opcode
            line_obj.generated_bytes.append(opcode)
            
            patch_addr = self.lc + 1
            sym_entry = self.symtab.lookup(target_label)
            
            if sym_entry and sym_entry.defined and sym_entry.address is not None:
                # Backward reference: Target address is already known!
                target_addr = sym_entry.address
                low = target_addr & 0xFF
                high = (target_addr >> 8) & 0xFF
                self.memory[patch_addr] = low
                self.memory[patch_addr + 1] = high
                line_obj.generated_bytes.extend([low, high])
                self.symtab.add_reference(target_label, start_lc)
                self.assembly_log.append(
                    f"[Line {line_obj.line_no:2d}] {mnem} {target_label}: Resolved backward reference to 0x{target_addr:04X}"
                )
            else:
                # FORWARD REFERENCE: Target address is NOT known yet!
                # Write placeholder dummy bytes (00 00) and register in FixupTable!
                self.memory[patch_addr] = 0x00
                self.memory[patch_addr + 1] = 0x00
                line_obj.generated_bytes.extend([0x00, 0x00])
                
                self.symtab.add_reference(target_label, start_lc)
                self.fixup_table.add_fixup(target_label, patch_address=patch_addr, instruction_lc=start_lc)
                self.assembly_log.append(
                    f"[Line {line_obj.line_no:2d}] {mnem} {target_label}: FORWARD REFERENCE detected! "
                    f"Wrote placeholder [00 00] at 0x{patch_addr:04X}, added to Fixup Table"
                )
                
            self.lc += 3
            return

        # -------------------------------------------------------------
        # Single-operand Arithmetic: MUL, DIV (Calculator *, /, %)
        # -------------------------------------------------------------
        if mnem in ["MUL", "DIV"]:
            if len(ops) != 1:
                raise ValueError(f"{mnem} requires 1 register operand at line {line_obj.line_no}")
            reg_name = ops[0].upper()
            if reg_name not in REGISTER_MAP_16:
                raise ValueError(f"Unsupported operand '{reg_name}' for {mnem} at line {line_obj.line_no}")
            
            reg_id = REGISTER_MAP_16[reg_name]
            opcode = 0xF7
            # ModR/M: 11 (reg-to-reg) | sub-opcode (4 for MUL, 6 for DIV) | reg_id
            sub_op = 4 if mnem == "MUL" else 6
            modrm = 0xC0 | (sub_op << 3) | reg_id
            
            self.memory[self.lc] = opcode
            self.memory[self.lc + 1] = modrm
            line_obj.generated_bytes.extend([opcode, modrm])
            self.lc += 2
            return

        # -------------------------------------------------------------
        # Two-operand Instructions: MOV, ADD, SUB, CMP
        # -------------------------------------------------------------
        if len(ops) != 2:
            raise ValueError(f"{mnem} requires 2 operands at line {line_obj.line_no}")

        op1 = ops[0].upper()
        op2 = ops[1].upper()

        # Check for Memory Direct Move: MOV [addr], AX or MOV AX, [addr]
        if mnem == "MOV" and (op1.startswith("[") and op1.endswith("]")):
            # MOV [VAR], AX
            mem_target = op1[1:-1].strip()
            if op2 != "AX":
                raise ValueError("Direct memory store supported for AX register in this configuration")
            opcode = 0xA3
            self.memory[self.lc] = opcode
            line_obj.generated_bytes.append(opcode)
            patch_addr = self.lc + 1
            self._handle_address_or_forward_ref(mem_target, patch_addr, start_lc, line_obj)
            self.lc += 3
            return

        if mnem == "MOV" and (op2.startswith("[") and op2.endswith("]")):
            # MOV AX, [VAR]
            mem_target = op2[1:-1].strip()
            if op1 != "AX":
                raise ValueError("Direct memory load supported for AX register in this configuration")
            opcode = 0xA1
            self.memory[self.lc] = opcode
            line_obj.generated_bytes.append(opcode)
            patch_addr = self.lc + 1
            self._handle_address_or_forward_ref(mem_target, patch_addr, start_lc, line_obj)
            self.lc += 3
            return

        # Both registers: e.g. MOV AX, BX / ADD AX, BX / SUB AX, BX / CMP AX, BX
        if op1 in REGISTER_MAP_16 and op2 in REGISTER_MAP_16:
            dest_id = REGISTER_MAP_16[op1]
            src_id = REGISTER_MAP_16[op2]
            
            opcodes = {"MOV": 0x89, "ADD": 0x01, "SUB": 0x29, "CMP": 0x39}
            opcode = opcodes[mnem]
            # ModR/M byte: 11 (reg-reg) | src (3 bits) | dest (3 bits)
            modrm = 0xC0 | (src_id << 3) | dest_id
            
            self.memory[self.lc] = opcode
            self.memory[self.lc + 1] = modrm
            line_obj.generated_bytes.extend([opcode, modrm])
            self.lc += 2
            return

        # Register and Immediate / Literal: e.g. MOV AX, 10 / ADD AX, 5 / MOV AX, =20
        if op1 in REGISTER_MAP_16:
            reg_id = REGISTER_MAP_16[op1]
            
            # Resolve immediate value or literal
            if op2.startswith("="):
                # Literal table entry!
                lit_val = self.parse_number(op2[1:])
                self.littab.insert(op2, lit_val)
                imm_val = lit_val
                self.assembly_log.append(f"[Line {line_obj.line_no:2d}] Added literal '{op2}' = {lit_val} to LITTAB")
            else:
                imm_val = self.parse_number(op2)

            imm_val = imm_val & 0xFFFF
            low = imm_val & 0xFF
            high = (imm_val >> 8) & 0xFF

            if mnem == "MOV":
                # MOV reg, imm16: Opcode = 0xB8 + reg_id
                opcode = 0xB8 + reg_id
                self.memory[self.lc] = opcode
                self.memory[self.lc + 1] = low
                self.memory[self.lc + 2] = high
                line_obj.generated_bytes.extend([opcode, low, high])
                self.lc += 3
                return

            elif mnem in ["ADD", "SUB", "CMP"]:
                # 0x81 ModR/M imm_low imm_high
                opcode = 0x81
                sub_ops = {"ADD": 0, "SUB": 5, "CMP": 7}
                modrm = 0xC0 | (sub_ops[mnem] << 3) | reg_id
                
                self.memory[self.lc] = opcode
                self.memory[self.lc + 1] = modrm
                self.memory[self.lc + 2] = low
                self.memory[self.lc + 3] = high
                line_obj.generated_bytes.extend([opcode, modrm, low, high])
                self.lc += 4
                return

        raise ValueError(f"Unsupported instruction format: {line_obj.raw_line}")

    def _handle_address_or_forward_ref(self, target_label: str, patch_addr: int, start_lc: int, line_obj: AssemblyLine):
        """Helper to resolve a memory label or place a forward fixup."""
        sym_entry = self.symtab.lookup(target_label)
        if sym_entry and sym_entry.defined and sym_entry.address is not None:
            addr = sym_entry.address
            low = addr & 0xFF
            high = (addr >> 8) & 0xFF
            self.memory[patch_addr] = low
            self.memory[patch_addr + 1] = high
            line_obj.generated_bytes.extend([low, high])
            self.symtab.add_reference(target_label, start_lc)
        else:
            # Forward reference!
            self.memory[patch_addr] = 0x00
            self.memory[patch_addr + 1] = 0x00
            line_obj.generated_bytes.extend([0x00, 0x00])
            self.symtab.add_reference(target_label, start_lc)
            self.fixup_table.add_fixup(target_label, patch_address=patch_addr, instruction_lc=start_lc)
            self.assembly_log.append(
                f"[Line {line_obj.line_no:2d}] Forward reference to '{target_label}' at 0x{patch_addr:04X}"
            )

    def display_listing(self) -> str:
        """Generates formatted assembly listing (Address | Object Code | Source Line)."""
        lines = [
            "=" * 80,
            f"{'LOC':<8} {'OBJECT CODE':<20} {'LINE':<6} {'SOURCE STATEMENT'}",
            "=" * 80
        ]
        for item in self.listing:
            if item.generated_bytes:
                hex_bytes = " ".join(f"{b:02X}" for b in item.generated_bytes)
            else:
                hex_bytes = ""
            lines.append(f"0x{item.lc:04X}   {hex_bytes:<20} {item.line_no:<6} {item.raw_line.strip()}")
        lines.append("=" * 80)
        return "\n".join(lines)
