/**
 * app.js - Interactive Controller for 8086 One-Pass Assembler & Virtual CPU Simulator
 */

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initCalculator();
    initStudio();
    initOptabInspector();
    
    // Initial calculation on page load for immediate visual delight
    executeCalculator("45 + 17");
    loadSampleAsmIntoStudio();
});

/* ==========================================================================
   Tab Navigation
   ========================================================================== */
function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-tab');

            tabBtns.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const targetContent = document.getElementById(targetId);
            if (targetContent) targetContent.classList.add('active');
        });
    });

    // Inspector Subtabs
    const subtabBtns = document.querySelectorAll('.subtab-btn');
    const subtabContents = document.querySelectorAll('.subtab-content');

    subtabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-subtab');

            subtabBtns.forEach(b => b.classList.remove('active'));
            subtabContents.forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const targetContent = document.getElementById(targetId);
            if (targetContent) targetContent.classList.add('active');
        });
    });
}

/* ==========================================================================
   Calculator Controller
   ========================================================================== */
function initCalculator() {
    const form = document.getElementById('calc-form');
    const input = document.getElementById('calc-expression-input');
    const chips = document.querySelectorAll('.chip');

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        executeCalculator(input.value.trim());
    });

    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            const expr = chip.getAttribute('data-expr');
            input.value = expr;
            executeCalculator(expr);
        });
    });
}

async function executeCalculator(expression) {
    if (!expression) return;

    const btn = document.getElementById('btn-calc-execute');
    const spinner = btn.querySelector('.spinner');
    const btnText = btn.querySelector('.btn-text');

    try {
        if (spinner) spinner.hidden = false;
        if (btnText) btnText.textContent = "Simulating...";

        const response = await fetch('/api/calculate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ expression: expression })
        });

        const data = await response.json();

        if (!data.success) {
            alert("Calculation Error: " + (data.error || "Unknown error"));
            return;
        }

        renderCalculatorResults(data);

    } catch (err) {
        console.error("Calc request failed:", err);
        alert("Failed to connect to backend server: " + err.message);
    } finally {
        if (spinner) spinner.hidden = true;
        if (btnText) btnText.textContent = "Execute on 8086";
    }
}

function renderCalculatorResults(data) {
    // Result Showcase
    const resVal = document.getElementById('calc-result-val');
    const resReg = document.getElementById('calc-result-reg');
    const metaOp = document.getElementById('calc-meta-op');
    const metaMatch = document.getElementById('calc-meta-match');
    const metaHex = document.getElementById('calc-meta-hex');
    const metaSteps = document.getElementById('calc-meta-steps');
    const asmPreview = document.getElementById('calc-asm-preview');

    resVal.textContent = data.result;
    resReg.textContent = `Stored in ${data.result_reg}`;
    metaOp.textContent = `${data.operation_name} (${data.operator})`;
    metaMatch.textContent = `Match (${data.result} == ${data.expected})`;
    metaHex.textContent = `0x${data.result.toString(16).toUpperCase().padStart(4, '0')}`;
    metaSteps.textContent = `${data.cpu.step_count} CPU instructions`;
    asmPreview.textContent = data.asm_code.trim();

    // Mini Registers
    const miniGrid = document.getElementById('calc-registers-grid');
    miniGrid.innerHTML = '';
    const mainRegs = ['AX', 'BX', 'CX', 'DX'];

    mainRegs.forEach(regName => {
        const regInfo = data.cpu.registers[regName];
        const isTarget = (data.operator === '%' && regName === 'DX') || (data.operator !== '%' && regName === 'AX');
        const card = document.createElement('div');
        card.className = `mini-reg-card ${isTarget ? 'highlight' : ''}`;
        card.innerHTML = `
            <div class="mini-reg-name">${regName}</div>
            <div class="mini-reg-val">${regInfo.hex}</div>
            <div class="text-xs text-muted">${regInfo.dec}</div>
        `;
        miniGrid.appendChild(card);
    });

    // Flags
    updateFlagsUI('calc-flag-', data.cpu.flags);
}

/* ==========================================================================
   Assembly Studio Controller
   ========================================================================== */
function initStudio() {
    const btnAssemble = document.getElementById('btn-assemble-run');
    const editor = document.getElementById('asm-editor');
    const btnLoadCalc = document.getElementById('btn-load-calculator-asm');
    const btnLoadBackpatch = document.getElementById('btn-load-backpatch-demo');
    const btnClear = document.getElementById('btn-clear-editor');

    btnAssemble.addEventListener('click', () => {
        executeStudioAssembly(editor.value);
    });

    btnLoadCalc.addEventListener('click', loadSampleAsmIntoStudio);

    btnLoadBackpatch.addEventListener('click', () => {
        editor.value = `; =========================================================
; Backpatching & Forward Reference Demonstration
; The JMP instruction refers to 'FORWARD_TARGET' BEFORE
; its memory address is known. The One-Pass Assembler emits
; a 16-bit placeholder (00 00) and backpatches it later!
; =========================================================
ORG 0100H
START:
    MOV AX, 100
    JMP FORWARD_TARGET   ; Forward reference! Fixup entry recorded.
    MOV BX, 50           ; Skipped instruction
FORWARD_TARGET:
    ADD AX, 25           ; Label resolved! Memory at JMP backpatched!
    HLT
END
`;
    });

    btnClear.addEventListener('click', () => {
        editor.value = '';
    });
}

async function loadSampleAsmIntoStudio() {
    try {
        const res = await fetch('/api/sample-asm');
        const data = await res.json();
        if (data.success) {
            const editor = document.getElementById('asm-editor');
            editor.value = data.source;
        }
    } catch (e) {
        console.warn("Could not load sample assembly:", e);
    }
}

async function executeStudioAssembly(sourceCode) {
    if (!sourceCode.trim()) {
        alert("Please enter 8086 assembly source code.");
        return;
    }

    const btn = document.getElementById('btn-assemble-run');
    const spinner = btn.querySelector('.spinner');
    const btnText = btn.querySelector('.btn-text');

    try {
        if (spinner) spinner.hidden = false;
        if (btnText) btnText.textContent = "Assembling & Simulating...";

        const response = await fetch('/api/assemble-and-run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source_code: sourceCode })
        });

        const data = await response.json();

        if (!data.success) {
            alert(data.error || "Assembly or Simulation failed.");
            return;
        }

        renderStudioResults(data);

    } catch (err) {
        console.error("Studio assemble failed:", err);
        alert("Error connecting to server: " + err.message);
    } finally {
        if (spinner) spinner.hidden = true;
        if (btnText) btnText.textContent = "Assemble & Execute (One-Pass)";
    }
}

function renderStudioResults(data) {
    const cpuBadge = document.getElementById('cpu-status-badge');
    if (cpuBadge) {
        cpuBadge.textContent = data.cpu.halted ? `Halted at ${data.cpu.registers.IP.hex}` : `Running (${data.cpu.step_count} steps)`;
        cpuBadge.className = data.cpu.halted ? "badge-success" : "badge-subtle";
    }

    // 1. Render Full 8086 Registers
    const regGrid = document.getElementById('studio-registers-grid');
    regGrid.innerHTML = '';

    const regOrder = ['AX', 'BX', 'CX', 'DX', 'SP', 'BP', 'SI', 'DI'];
    regOrder.forEach(name => {
        const reg = data.cpu.registers[name];
        const card = document.createElement('div');
        card.className = 'reg-card';

        let subHtml = '';
        if (reg.high !== undefined && reg.low !== undefined) {
            subHtml = `
                <div class="reg-sub-halves">
                    <span>${name[0]}H: ${reg.high}</span>
                    <span>${name[0]}L: ${reg.low}</span>
                </div>
            `;
        } else {
            subHtml = `
                <div class="reg-sub-halves">
                    <span>Dec: ${reg.dec}</span>
                </div>
            `;
        }

        card.innerHTML = `
            <div class="reg-card-top">
                <span>${name}</span>
                <span>${reg.dec}</span>
            </div>
            <div class="reg-val-hex">${reg.hex}</div>
            ${subHtml}
        `;
        regGrid.appendChild(card);
    });

    // 2. Render Flags
    updateFlagsUI('studio-flag-', data.cpu.flags);

    // 3. Render Fixup & Backpatch Events
    const backpatchList = document.getElementById('studio-backpatch-list');
    const fixupCountPill = document.getElementById('fixup-count-pill');
    const history = data.assembler.fixup_history;

    fixupCountPill.textContent = `${history.length} Backpatch Events`;

    if (!history || history.length === 0) {
        backpatchList.innerHTML = `<p class="text-muted text-sm empty-state">No forward references needed backpatching in this program.</p>`;
    } else {
        backpatchList.innerHTML = '';
        history.forEach(evt => {
            const item = document.createElement('div');
            item.className = 'backpatch-item';
            item.innerHTML = `
                <div>
                    <span class="backpatch-symbol">${evt.symbol}</span>
                    <span class="backpatch-detail">&rarr; Resolved Address: <strong>${evt.target_address}</strong></span>
                </div>
                <div class="backpatch-detail">
                    Patched at memory <strong>${evt.patched_at}</strong> (Instruction at ${evt.instruction_lc})
                </div>
            `;
            backpatchList.appendChild(item);
        });
    }

    // 4. Render Object Code Listing
    const listingTbody = document.querySelector('#table-listing tbody');
    listingTbody.innerHTML = '';
    data.assembler.listing.forEach(row => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row.line_no}</td>
            <td class="font-mono text-emerald">${row.lc}</td>
            <td class="font-mono">${row.bytes || '-'}</td>
            <td><code>${escapeHtml(row.source)}</code></td>
        `;
        listingTbody.appendChild(tr);
    });

    // 5. Render SYMTAB
    const symtabTbody = document.querySelector('#table-symtab tbody');
    symtabTbody.innerHTML = '';
    if (data.assembler.symtab.length === 0) {
        symtabTbody.innerHTML = `<tr><td colspan="4" class="text-muted text-center">No symbols defined.</td></tr>`;
    } else {
        data.assembler.symtab.forEach(sym => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="font-mono" style="color: #818cf8; font-weight: bold;">${sym.name}</td>
                <td class="font-mono">${sym.address}</td>
                <td><span class="${sym.defined ? 'badge-success' : 'badge-subtle'}">${sym.defined ? 'YES' : 'NO (Forward)'}</span></td>
                <td class="font-mono text-muted">${sym.references.length > 0 ? sym.references.join(', ') : 'None'}</td>
            `;
            symtabTbody.appendChild(tr);
        });
    }

    // 6. Render LITTAB
    const littabTbody = document.querySelector('#table-littab tbody');
    littabTbody.innerHTML = '';
    if (data.assembler.littab.length === 0) {
        littabTbody.innerHTML = `<tr><td colspan="4" class="text-muted text-center">No literals used.</td></tr>`;
    } else {
        data.assembler.littab.forEach(lit => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="font-mono">${lit.literal}</td>
                <td>${lit.value}</td>
                <td class="font-mono">${lit.address}</td>
                <td><span class="${lit.allocated ? 'badge-success' : 'badge-subtle'}">${lit.allocated ? 'ALLOCATED' : 'PENDING'}</span></td>
            `;
            littabTbody.appendChild(tr);
        });
    }

    // 7. CPU Trace
    const traceBlock = document.getElementById('studio-trace-block');
    traceBlock.textContent = data.cpu.trace.join('\n') || "No trace generated.";

    // 8. Assembly Log
    const logContainer = document.getElementById('studio-log-container');
    logContainer.innerHTML = '';
    data.assembler.log.forEach(msg => {
        const p = document.createElement('div');
        const isBackpatch = msg.includes('Backpatched') || msg.includes('Fixup');
        p.className = `log-entry ${isBackpatch ? 'backpatch-log' : ''}`;
        p.textContent = msg;
        logContainer.appendChild(p);
    });
}

/* ==========================================================================
   OPTAB Inspector
   ========================================================================== */
async function initOptabInspector() {
    try {
        const res = await fetch('/api/tables');
        const data = await res.json();
        if (data.success && data.optab) {
            renderOptabTable(data.optab);

            const searchInput = document.getElementById('optab-search');
            searchInput.addEventListener('input', (e) => {
                const query = e.target.value.toUpperCase();
                const filtered = data.optab.filter(item => 
                    item.mnemonic.includes(query) || item.description.toUpperCase().includes(query)
                );
                renderOptabTable(filtered);
            });
        }
    } catch (e) {
        console.warn("Could not load OPTAB:", e);
    }
}

function renderOptabTable(optabList) {
    const tbody = document.querySelector('#table-optab tbody');
    tbody.innerHTML = '';
    if (optabList.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-muted text-center">No matching opcodes found.</td></tr>`;
        return;
    }

    optabList.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="font-mono" style="color: #60a5fa; font-weight: bold;">${item.mnemonic}</td>
            <td class="font-mono text-emerald">${item.opcode}</td>
            <td>${item.size} bytes</td>
            <td class="font-mono text-muted">${item.format}</td>
            <td>${item.description}</td>
        `;
        tbody.appendChild(tr);
    });
}

/* ==========================================================================
   Helper Utilities
   ========================================================================== */
function updateFlagsUI(prefix, flags) {
    const flagNames = ['zf', 'sf', 'cf', 'of'];
    flagNames.forEach(f => {
        const chip = document.getElementById(`${prefix}${f}`);
        if (chip) {
            const isSet = flags[f.toUpperCase()] === 1;
            if (isSet) {
                chip.classList.add('active');
            } else {
                chip.classList.remove('active');
            }
        }
    });
}

function escapeHtml(string) {
    const entityMap = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    };
    return String(string).replace(/[&<>"']/g, s => entityMap[s]);
}
