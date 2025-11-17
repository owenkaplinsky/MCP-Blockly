import * as Blockly from 'blockly';
import { blocks } from './blocks/text';
import { forBlock } from './generators/python';
import { pythonGenerator } from 'blockly/python';
import { save, load } from './serialization';
import { toolbox } from './toolbox';
import '@blockly/toolbox-search';
import './index.css';

// Register the blocks and generator with Blockly
Blockly.common.defineBlocks(blocks);
Object.assign(pythonGenerator.forBlock, forBlock);

// Set up UI elements and inject Blockly
const blocklyDiv = document.getElementById('blocklyDiv');

// Create a custom theme (Scratch-like colors and hats)
const myTheme = Blockly.Theme.defineTheme('myScratchTheme', {
  base: Blockly.Themes.Classic,
  startHats: true,
  blockStyles: {
    logic_blocks: {
      colourPrimary: '#5C81A6',
      colourSecondary: '#4A6D8B',
      colourTertiary: '#3B5572',
    },
    loop_blocks: {
      colourPrimary: '#5CA65C',
      colourSecondary: '#498949',
      colourTertiary: '#3B723B',
    },
  },
  categoryStyles: {
    logic_category: { colour: '#5C81A6' },
    loop_category: { colour: '#5CA65C' },
  },
  componentStyles: {
    workspaceBackgroundColour: '#f0f0f0',
    toolboxBackgroundColour: '#ffffff',
  },
});

// Inject Blockly with theme + renderer
const ws = Blockly.inject(blocklyDiv, {
  toolbox,
  grid: {
    spacing: 35,
    length: 3,
    colour: '#ccc',
    snap: false
  },
  renderer: 'zelos',
  theme: myTheme,
});

const updateCode = () => {
  let code = pythonGenerator.workspaceToCode(ws);
  const codeEl = document.querySelector('#generatedCode code');

  const call = `def llm_call(prompt, model):
  global history
  from openai import OpenAI
  import os

  client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

  messages = [{"role": "user", "content": prompt}]

  completion = client.chat.completions.create(model=model, messages=messages)
  return completion.choices[0].message.content.strip()
  
`;

  const blocks = ws.getAllBlocks(false);
  const hasCall = blocks.some(block => block.type === 'llm_call');

  if (hasCall) {
    code = call + code;
  }

  code = "import gradio as gr\n\n" + code

  if (codeEl) {
    codeEl.textContent = code;
  }

  // Send generated Python code to backend
  fetch("http://127.0.0.1:7860/update_code", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  })
    .then(() => {
      console.log("[Blockly] Sent updated Python code to backend");
    })
    .catch((err) => {
      console.error("[Blockly] Error sending Python code:", err);
    });
};

try {
  load(ws);
} catch (e) {
  console.warn('Workspace load failed, clearing storage:', e);
  localStorage.clear();
}

// Ensure there's always one MCP block in the workspace
const existingMcpBlocks = ws.getBlocksByType('create_mcp');
if (existingMcpBlocks.length === 0) {
  // Create the MCP block
  const mcpBlock = ws.newBlock('create_mcp');
  mcpBlock.initSvg();
  mcpBlock.setDeletable(false);
  mcpBlock.setMovable(true);  // Allow moving but not deleting

  // Position it in a reasonable spot
  mcpBlock.moveBy(50, 50);
  mcpBlock.render();
}

updateCode();

ws.addChangeListener((e) => {
  if (e.isUiEvent) return;

  save(ws);
});

ws.addChangeListener((event) => {
  if (event.isUiEvent) return;

  if (event.type === Blockly.Events.BLOCK_MOVE) {
    if (event.oldParentId && !event.newParentId) {
      const removedBlock = ws.getBlockById(event.blockId);
      const oldParent = ws.getBlockById(event.oldParentId);

      if (
        removedBlock &&
        oldParent &&
        (removedBlock.type.startsWith('input_reference_') && (oldParent.type === 'create_mcp' || oldParent.type === 'tool_def'))
      ) {
        // Only duplicate if removed from a mutator input (X0, X1, X2, etc.)
        // NOT from other inputs like RETURN, BODY, or title input
        const inputName = event.oldInputName;
        const isMutatorInput = inputName && /^X\d+$/.test(inputName);

        if (isMutatorInput) {
          Blockly.Events.disable();
          try {
            // Create a new block of the same reference type
            const newRefBlock = ws.newBlock(removedBlock.type);
            newRefBlock.initSvg();
            newRefBlock.setDeletable(false);  // This one stays in the MCP block
            // Mark the new reference block with its owner (same as the parent)
            newRefBlock._ownerBlockId = oldParent.id;

            const input = oldParent.getInput(inputName);
            if (input) {
              input.connection.connect(newRefBlock.outputConnection);
            }

            // Update the parent block's reference tracking
            if (removedBlock.type.startsWith('input_reference_')) {
              const varName = removedBlock.type.replace('input_reference_', '');
              if (oldParent.inputRefBlocks_) {
                oldParent.inputRefBlocks_.set(varName, newRefBlock);
              }
            }

            // Make the dragged-out block deletable
            removedBlock.setDeletable(true);

            ws.render(); // ensure workspace updates immediately
          } finally {
            Blockly.Events.enable();
          }
        }
      }
    }
  }

  save(ws);
});

ws.addChangeListener((e) => {
  if (e.isUiEvent || e.type == Blockly.Events.FINISHED_LOADING || ws.isDragging()) {
    return;
  }
  updateCode();
});