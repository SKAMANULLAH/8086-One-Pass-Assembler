"""
structures.py - Core Data Structures for 8086 One-Pass Assembler

Contains:
1. Symbol Table (SYMTAB) & SymbolEntry
2. Opcode Table (OPTAB) & OpcodeEntry
3. Literal Table (LITTAB) & LiteralEntry
4. Fixup / Backpatch Table & FixupEntry
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class OpcodeEntry:
    """Represents an entry in the Opcode Table (OPTAB)."""
    mnemonic: str
    opcode: int              # Primary opcode byte (hex)
    size: int                # Instruction size in bytes
    operands_format: str     # e.g., "reg,imm16", "reg,reg", "reg", "none", "label"
    description: str


@dataclass
class SymbolEntry:
    """Represents an entry in the Symbol Table (SYMTAB)."""
    name: str
    address: Optional[int] = None   # Resolved memory address (None if forward-referenced)
    defined: bool = False           # True once definition line is encountered
    references: List[int] = field(default_factory=list)  # Addresses where this symbol was referenced


@dataclass
class LiteralEntry:
    """Represents an entry in the Literal Table (LITTAB)."""
    literal: str             # e.g., "=10", "=0x1F"
    value: int               # Evaluated numerical value
    address: Optional[int] = None  # Memory address where literal is placed
    allocated: bool = False  # True once memory has been allocated


@dataclass
class FixupEntry:
    """
    Represents an unresolved reference waiting for Backpatching.
    When a symbol is referenced before it is defined (Forward Reference),
    we record the memory address where the placeholder was written.
    """
    patch_address: int       # Address in memory/object code to overwrite
    instruction_lc: int      # Location counter where the instruction started
    symbol_name: str         # Symbol being referenced
    operand_type: str = "abs16"  # "abs16" (16-bit address) or "rel8" (relative jump)


class OpcodeTable:
    """
    OPTAB (Machine Opcode Table)
    Stores built-in 8086 instructions, their hex opcodes, and formats.
    """
    def __init__(self):
        self.table: Dict[str, List[OpcodeEntry]] = {}
        self._init_default_table()

    def _init_default_table(self):
        # Key 8086 instructions needed for calculator and control flow
        entries = [
            # MOV instructions
            OpcodeEntry("MOV", 0xB8, 3, "reg,imm16", "Move 16-bit immediate to register (0xB8 + reg)"),
            OpcodeEntry("MOV", 0x89, 2, "reg,reg",   "Move 16-bit register to register"),
            OpcodeEntry("MOV", 0xA1, 3, "ax,[addr]", "Move memory word to AX"),
            OpcodeEntry("MOV", 0xA3, 3, "[addr],ax", "Move AX to memory word"),
            
            # Arithmetic (Calculator operations)
            OpcodeEntry("ADD", 0x01, 2, "reg,reg",   "Add register to register (+ operation)"),
            OpcodeEntry("ADD", 0x81, 4, "reg,imm16", "Add 16-bit immediate to register (+ operation)"),
            OpcodeEntry("SUB", 0x29, 2, "reg,reg",   "Subtract register from register (- operation)"),
            OpcodeEntry("SUB", 0x81, 4, "reg,imm16", "Subtract 16-bit immediate from register (- operation)"),
            OpcodeEntry("MUL", 0xF7, 2, "reg",       "Unsigned multiply AX by register (* operation, result in DX:AX)"),
            OpcodeEntry("DIV", 0xF7, 2, "reg",       "Unsigned divide DX:AX by register (/ quotient in AX, % modulo in DX)"),
            
            # Comparison & Logic
            OpcodeEntry("CMP", 0x39, 2, "reg,reg",   "Compare register with register"),
            OpcodeEntry("CMP", 0x81, 4, "reg,imm16", "Compare register with 16-bit immediate"),
            
            # Branching (to demonstrate forward references and backpatching)
            OpcodeEntry("JMP", 0xEA, 3, "label",     "Unconditional Direct Jump (16-bit address)"),
            OpcodeEntry("JE",  0x74, 3, "label",     "Jump if Equal / Zero Flag is set"),
            OpcodeEntry("JZ",  0x74, 3, "label",     "Jump if Zero"),
            OpcodeEntry("JNE", 0x75, 3, "label",     "Jump if Not Equal / Zero Flag clear"),
            OpcodeEntry("JNZ", 0x75, 3, "label",     "Jump if Not Zero"),
            
            # Control
            OpcodeEntry("HLT", 0xF4, 1, "none",      "Halt CPU execution"),
            OpcodeEntry("NOP", 0x90, 1, "none",      "No operation")
        ]
        for entry in entries:
            if entry.mnemonic not in self.table:
                self.table[entry.mnemonic] = []
            self.table[entry.mnemonic].append(entry)

    def lookup(self, mnemonic: str) -> Optional[List[OpcodeEntry]]:
        """Finds opcode entries matching the mnemonic."""
        return self.table.get(mnemonic.upper())

    def display(self) -> str:
        """Formats the OPTAB for display/printing."""
        lines = [
            "=" * 70,
            f"{'MNEMONIC':<10} {'OPCODE':<10} {'SIZE':<8} {'FORMAT':<14} {'DESCRIPTION'}",
            "=" * 70
        ]
        for mnem, entries in self.table.items():
            for e in entries:
                lines.append(f"{e.mnemonic:<10} 0x{e.opcode:02X}       {e.size} bytes  {e.operands_format:<14} {e.description}")
        lines.append("=" * 70)
        return "\n".join(lines)


class SymbolTable:
    """
    SYMTAB (Symbol Table)
    Stores labels, their defined status, and allocated memory addresses.
    """
    def __init__(self):
        self.table: Dict[str, SymbolEntry] = {}

    def insert(self, name: str, address: Optional[int] = None, defined: bool = False) -> SymbolEntry:
        """Inserts or updates a symbol in the table."""
        name = name.upper()
        if name in self.table:
            entry = self.table[name]
            if defined:
                entry.address = address
                entry.defined = True
            return entry
        else:
            entry = SymbolEntry(name=name, address=address, defined=defined)
            self.table[name] = entry
            return entry

    def lookup(self, name: str) -> Optional[SymbolEntry]:
        """Looks up a symbol by name."""
        return self.table.get(name.upper())

    def add_reference(self, name: str, ref_address: int):
        """Records an address where this symbol was referenced."""
        name = name.upper()
        if name not in self.table:
            self.insert(name, address=None, defined=False)
        self.table[name].references.append(ref_address)

    def display(self) -> str:
        """Formats the SYMTAB for display/printing."""
        lines = [
            "=" * 60,
            f"{'SYMBOL':<15} {'ADDRESS':<12} {'DEFINED?':<12} {'REFERENCES'}",
            "=" * 60
        ]
        for name, entry in sorted(self.table.items()):
            addr_str = f"0x{entry.address:04X}" if entry.address is not None else "UNRESOLVED"
            def_str = "YES" if entry.defined else "NO (Forward)"
            refs_str = ", ".join([f"0x{r:04X}" for r in entry.references]) if entry.references else "None"
            lines.append(f"{entry.name:<15} {addr_str:<12} {def_str:<12} {refs_str}")
        lines.append("=" * 60)
        return "\n".join(lines)


class LiteralTable:
    """
    LITTAB (Literal Table)
    Stores constants/literals (e.g. =10, =0x20) and allocates memory addresses for them.
    """
    def __init__(self):
        self.literals: List[LiteralEntry] = []

    def insert(self, literal: str, value: int) -> LiteralEntry:
        """Inserts a literal if not already present."""
        literal = literal.strip()
        for entry in self.literals:
            if entry.literal == literal:
                return entry
        entry = LiteralEntry(literal=literal, value=value)
        self.literals.append(entry)
        return entry

    def allocate_pool(self, start_lc: int) -> int:
        """
        Allocates memory addresses for all unallocated literals in the pool (e.g., at END).
        Returns the updated Location Counter (LC).
        """
        current_lc = start_lc
        for entry in self.literals:
            if not entry.allocated:
                entry.address = current_lc
                entry.allocated = True
                current_lc += 2  # 16-bit word literal
        return current_lc

    def display(self) -> str:
        """Formats the LITTAB for display/printing."""
        lines = [
            "=" * 60,
            f"{'LITERAL':<15} {'VALUE (DEC)':<15} {'ADDRESS':<15} {'ALLOCATED?'}",
            "=" * 60
        ]
        if not self.literals:
            lines.append("  (No literals used)")
        else:
            for e in self.literals:
                addr_str = f"0x{e.address:04X}" if e.address is not None else "PENDING"
                alloc_str = "YES" if e.allocated else "NO"
                lines.append(f"{e.literal:<15} {e.value:<15} {addr_str:<15} {alloc_str}")
        lines.append("=" * 60)
        return "\n".join(lines)


class FixupTable:
    """
    Fixup / Backpatch Table
    Records forward references that need their placeholder addresses
    patched once the target symbol address is known.
    """
    def __init__(self):
        # Maps symbol_name -> list of FixupEntry
        self.pending_fixups: Dict[str, List[FixupEntry]] = {}
        # History of all backpatch events for educational reporting
        self.backpatch_history: List[Dict[str, Any]] = []

    def add_fixup(self, symbol_name: str, patch_address: int, instruction_lc: int, operand_type: str = "abs16"):
        """Records a forward reference needing backpatching."""
        symbol_name = symbol_name.upper()
        if symbol_name not in self.pending_fixups:
            self.pending_fixups[symbol_name] = []
        entry = FixupEntry(
            patch_address=patch_address,
            instruction_lc=instruction_lc,
            symbol_name=symbol_name,
            operand_type=operand_type
        )
        self.pending_fixups[symbol_name].append(entry)

    def backpatch(self, symbol_name: str, resolved_address: int, memory_buffer: bytearray) -> List[FixupEntry]:
        """
        Executes backpatching!
        Finds all placeholder locations for `symbol_name`, overwrites them
        in `memory_buffer` with `resolved_address`, and removes them from pending.
        """
        symbol_name = symbol_name.upper()
        if symbol_name not in self.pending_fixups:
            return []

        resolved_entries = self.pending_fixups.pop(symbol_name)
        for entry in resolved_entries:
            # Overwrite the 16-bit placeholder (Little-Endian: low byte, high byte)
            low_byte = resolved_address & 0xFF
            high_byte = (resolved_address >> 8) & 0xFF
            
            memory_buffer[entry.patch_address] = low_byte
            memory_buffer[entry.patch_address + 1] = high_byte
            
            # Record in history for reporting
            self.backpatch_history.append({
                "symbol": symbol_name,
                "target_address": resolved_address,
                "patched_at": entry.patch_address,
                "instruction_lc": entry.instruction_lc
            })

        return resolved_entries

    def has_unresolved(self) -> bool:
        """Returns True if any forward references remain unpatched."""
        return len(self.pending_fixups) > 0

    def display_history(self) -> str:
        """Formats the backpatch event log."""
        lines = [
            "=" * 75,
            f"{'SYMBOL':<15} {'RESOLVED ADDR':<16} {'PATCHED AT ADDR':<18} {'INSTRUCTION LC'}",
            "=" * 75
        ]
        if not self.backpatch_history:
            lines.append("  (No backpatching events were required)")
        else:
            for item in self.backpatch_history:
                lines.append(
                    f"{item['symbol']:<15} "
                    f"0x{item['target_address']:04X}           "
                    f"0x{item['patched_at']:04X}             "
                    f"0x{item['instruction_lc']:04X}"
                )
        lines.append("=" * 75)
        return "\n".join(lines)
