# 8086 One-Pass Assembler & CPU Simulator (Calculator Engine)

An academic-grade implementation of a **One-Pass Assembler** and **8086 Virtual CPU Simulator** written in Python, designed to support basic calculator operations (`+`, `-`, `*`, `/`, `%`) and demonstrate system software data structures.

---

## 📑 Table of Contents
1. [Key Features](#key-features)
2. [Data Structures Used](#data-structures-used)
3. [Working Principle of One-Pass Assembler & Backpatching](#working-principle-of-one-pass-assembler--backpatching)
4. [Calculator Operations in 8086](#calculator-operations-in-8086)
5. [Project Structure](#project-structure)
6. [How to Run](#how-to-run)
7. [Viva / Oral Exam Questions & Answers (For Full Marks)](#viva--oral-exam-questions--answers-for-full-marks)

---

## 🌟 Key Features

* **Strict One-Pass Principle**: The assembler processes code from top to bottom in a single pass.
* **Forward Reference Resolution**: Implements **Backpatching** via a Fixup Table.
* **Academic Data Structures**: Fully transparent and printable `OPTAB`, `SYMTAB`, and `LITTAB`.
* **8086 CPU Emulation**:
  * 16-bit Registers: `AX`, `BX`, `CX`, `DX`, `SP`, `BP`, `SI`, `DI`, `IP`.
  * 8-bit Sub-registers: `AH`, `AL`, `BH`, `BL`, `CH`, `CL`, `DH`, `DL`.
  * Flags: `ZF` (Zero), `SF` (Sign), `CF` (Carry), `OF` (Overflow).
  * 64 KB Linear Memory byte array.
* **Full Calculator Operations**:
  * Addition (`+`) via `ADD`
  * Subtraction (`-`) via `SUB`
  * Multiplication (`*`) via `MUL` (product in `DX:AX`)
  * Division (`/`) via `DIV` (quotient in `AX`)
  * Modulo (`%`) via `DIV` (remainder in `DX`)

---

## 🗂️ Data Structures Used

| Structure Name | Purpose | Underlying Data Structure |
| :--- | :--- | :--- |
| **`OPTAB` (Opcode Table)** | Stores built-in 8086 instructions, machine opcodes, sizes, and formats. | **Hash Map / Dictionary** (`Dict[str, List[OpcodeEntry]]`) |
| **`SYMTAB` (Symbol Table)** | Stores user-defined labels, their memory addresses, definition status, and references. | **Hash Map / Dictionary** (`Dict[str, SymbolEntry]`) |
| **`LITTAB` (Literal Table)** | Stores hardcoded constant values (`=10`, `=2`) and allocates memory at `END`. | **List of Records / Structs** (`List[LiteralEntry]`) |
| **`Fixup Table` (Backpatching)** | Stores unresolved forward references and their memory placeholder locations. | **Hash Map of Lists** (`Dict[str, List[FixupEntry]]`) |
| **`Memory Buffer`** | Emulates the 64 KB physical RAM of the 8086 processor. | **Byte Array** (`bytearray(65536)`) |
| **`Register File`** | Simulates 16-bit processor registers and flags. | **Integer Array & Bitmask Properties** |

---

## 🔄 Working Principle of One-Pass Assembler & Backpatching

### The Forward Reference Problem
When an instruction like `JMP CALC_ADD` is encountered at address `0x0100`, but `CALC_ADD` is defined further down at `0x0104`:
* The assembler **does not yet know** the address of `CALC_ADD`.
* In a **Two-Pass Assembler**, Pass 1 only records label addresses, and Pass 2 generates code.
* In a **One-Pass Assembler**, code is generated **immediately**.

### The Solution: Backpatching
1. **Emit Placeholder**: When the forward jump is encountered at `0x0100`, the assembler emits `EA 00 00` (where `00 00` at `0x0101..0x0102` is a placeholder).
2. **Record Fixup**: It adds an entry in the `FixupTable`:
   ```
   FixupTable["CALC_ADD"] = [0x0101]
   ```
3. **Resolve and Overwrite**: When the line `CALC_ADD:` is parsed at address `0x0104`:
   * `CALC_ADD` is registered in `SYMTAB` with address `0x0104`.
   * The assembler checks `FixupTable` for `"CALC_ADD"`.
   * It immediately goes back to address `0x0101` in the memory image and **patches** it with `0x0104` (in Little-Endian: `04 01`).

---

## 🧮 Calculator Operations in 8086

| Math Operation | 8086 Instruction | Operands | Register Storage & Semantics |
| :--- | :--- | :--- | :--- |
| **Addition (`+`)** | `ADD` | `ADD AX, BX` | `AX = AX + BX`, updates `ZF`, `SF`, `CF`, `OF`. |
| **Subtraction (`-`)** | `SUB` | `SUB AX, BX` | `AX = AX - BX`, updates `ZF`, `SF`, `CF`, `OF`. |
| **Multiplication (`*`)** | `MUL` | `MUL BX` | Unsigned 16-bit multiply: `DX:AX = AX * BX`. High 16 bits in `DX`, Low 16 bits in `AX`. |
| **Division (`/`)** | `DIV` | `DIV BX` | Divides 32-bit `DX:AX` by `BX`. **Quotient is stored in `AX`**. |
| **Modulo (`%`)** | `DIV` | `DIV BX` | Divides 32-bit `DX:AX` by `BX`. **Remainder is stored in `DX`**. |

---

## 📁 Project Structure

```
friendly-hubble/
├── structures.py           # OPTAB, SYMTAB, LITTAB, and FixupTable data structures
├── assembler.py            # One-Pass Assembler engine with backpatching
├── simulator.py            # 8086 Virtual CPU, ALU (+, -, *, /, %), and Memory
├── calculator.asm          # Sample 8086 assembly program demonstrating all operations
├── main.py                 # CLI interface (Full Demo, Interactive Calculator, File Runner)
├── app.py                  # Flask Web Server & REST API for Web UI
├── templates/
│   └── index.html          # Responsive Dark Mode Web Application
├── static/
│   ├── css/style.css       # Glassmorphism design & JetBrains Mono styling
│   └── js/app.js           # Calculator controller & visual studio inspector
├── nginx.conf              # Nginx Reverse Proxy config (Port 80 -> 127.0.0.1:5000)
├── friendly-hubble.service # Systemd service unit for 24/7 Gunicorn background run
├── ec2_setup.sh            # 1-Command Automated AWS EC2 Deployment Script
├── requirements.txt        # Flask and Gunicorn dependencies
├── tests/
│   ├── test_system.py      # Core Assembler & CPU unit tests
│   └── test_web_api.py     # Web server and API unit tests
└── README.md               # Complete documentation & viva prep
```

---

## 🚀 How to Run

### 1. Run the Web UI Locally
```bash
python app.py
```
Open **`http://localhost:5000`** in your browser to access the Interactive Calculator, 8086 Assembly Studio, and live register dashboards.

### 2. Run in Terminal (CLI Mode)
* Full Demo: `python main.py --demo`
* Interactive CLI Menu: `python main.py`

### 3. Run Automated Tests
```bash
python -m unittest discover tests
```

---

## 🌐 Deploy to AWS EC2 with Nginx (Port 80 Worldwide)

This project includes a **1-command setup script** that configures **Nginx on Port 80** + **Gunicorn** + **Systemd** so your web application runs 24/7 without needing port `:5000` in the URL:

1. **Launch EC2 Instance**: Ubuntu 22.04 LTS (Free Tier `t2.micro`).
2. **Security Group**: Open **SSH (Port 22)** and **HTTP (Port 80)** to `0.0.0.0/0`.
3. **SSH into EC2**:
   ```bash
   ssh -i your-key.pem ubuntu@<your-ec2-public-ip>
   ```
4. **Clone & Run Automated Setup**:
   ```bash
   git clone <your-repo-url> friendly-hubble
   cd friendly-hubble
   sudo bash ec2_setup.sh
   ```
5. **Access Live Worldwide**: Open `http://<your-ec2-public-ip>` directly in any browser!


---

## 🎓 Viva / Oral Exam Questions & Answers (For Full Marks)

### Q1: What is the main difference between a One-Pass and a Two-Pass Assembler?
> **Answer**: A Two-Pass Assembler scans the source code twice: Pass 1 constructs the Symbol Table (`SYMTAB`) and determines all addresses, while Pass 2 generates the machine/object code. A One-Pass Assembler scans the code only once, generating object code immediately as it goes.

### Q2: How does a One-Pass Assembler solve the Forward Reference Problem?
> **Answer**: It uses a technique called **Backpatching**. When an instruction refers to an undefined label, dummy placeholder bytes (like `00 00`) are placed in the object code, and an entry is made in a **Fixup Table**. Once the label definition is encountered later in the source code, the assembler uses the Fixup Table to revisit the placeholder address in memory and overwrite it with the newly resolved address.

### Q3: What is the purpose of LITTAB (Literal Table)?
> **Answer**: `LITTAB` tracks literals (constants prefixed with `=`, such as `=10`). Unlike immediate values that are embedded directly within instruction bytes, literals are assigned their own memory addresses in a literal pool (created by directives like `LTORG` or `END`).

### Q4: In 8086, how are Division (`/`) and Modulo (`%`) performed using the same instruction?
> **Answer**: The 8086 `DIV` instruction divides the 32-bit dividend in `DX:AX` by a 16-bit register divisor. The processor automatically calculates both parts:
> * The **Quotient** (result of `/`) is placed in the **`AX`** register.
> * The **Remainder** (result of `%`) is placed in the **`DX`** register.

### Q5: What data structure is best suited for SYMTAB and OPTAB and why?
> **Answer**: A **Hash Map (Hash Table / Dictionary)** is ideal because it provides average $O(1)$ constant time complexity for insertions and lookups, which is critical for fast symbol resolution and mnemonic matching during compilation/assembly.
