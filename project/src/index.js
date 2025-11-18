import * as Blockly from 'blockly';
import { blocks } from './blocks/text';
import { forBlock } from './generators/python';
import { pythonGenerator } from 'blockly/python';
import { chatGenerator, forBlock as chatForBlock } from './generators/chat';
import { save, load } from './serialization';
import { toolbox } from './toolbox';
import '@blockly/toolbox-search';
import DarkTheme from '@blockly/theme-dark';
import './index.css';

// Register the blocks and generator with Blockly
Blockly.common.defineBlocks(blocks);
Object.assign(pythonGenerator.forBlock, forBlock);

// Register chat generator blocks
Object.assign(chatGenerator.forBlock, chatForBlock);

// Set up UI elements and inject Blockly
const blocklyDiv = document.getElementById('blocklyDiv');

// Inject Blockly with theme + renderer
const ws = Blockly.inject(blocklyDiv, {
  toolbox,
  grid: {
    spacing: 35,
    length: 3,
    colour: '#ccc',
    snap: false
  },
  disable: false,
  collapse: false,
  zoom: {
    controls: true,
    wheel: true,
    startScale: 1.0,
    maxScale: 3,
    minScale: 0.3,
    scaleSpeed: 1.2,
    pinch: true
  },
  renderer: 'zelos',
  theme: DarkTheme,
});

window.workspace = ws;

Blockly.ContextMenuItems.registerCommentOptions();

const newButton = document.querySelector('#newButton');

newButton.addEventListener("click", () => {
  ws.clear()

  // Create the MCP block
  const mcpBlock = ws.newBlock('create_mcp');
  mcpBlock.initSvg();
  mcpBlock.setDeletable(false);
  mcpBlock.setMovable(true);  // Allow moving but not deleting

  // Position it in a reasonable spot
  mcpBlock.moveBy(50, 50);
  mcpBlock.render();
});

loadButton.addEventListener("click", () => {
  const input = document.createElement('input');
  let fileContent;
  input.type = 'file';
  input.accept = '.txt'; // Specify the file types you want to accept
  input.onchange = function (event) {
    const file = event.target.files[0];
    const reader = new FileReader();
    reader.onload = function (event) {
      fileContent = JSON.parse(event.target.result); // Parse directly without decoding
      Blockly.serialization.workspaces.load(fileContent, ws);
    };
    reader.readAsText(file);
  };
  input.click();
});

saveButton.addEventListener("click", () => {
  const state = Blockly.serialization.workspaces.save(ws);
  const stateString = JSON.stringify(state);

  var filename = "mcpBlockly_project.txt";
  var element = document.createElement('a');

  element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(stateString));
  element.setAttribute('download', filename);
  element.style.display = 'none';
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
});

// Download Code button
const downloadCodeButton = document.querySelector('#downloadCodeButton');
downloadCodeButton.addEventListener("click", () => {
  // Get the current generated code
  const codeEl = document.querySelector('#generatedCode code');
  const code = codeEl ? codeEl.textContent : '';
  
  if (!code) {
    alert('No code to download');
    return;
  }

  var filename = "mcp_generated.py";
  var element = document.createElement('a');
  
  element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(code));
  element.setAttribute('download', filename);
  element.style.display = 'none';
  document.body.appendChild(element);
  element.click();
  document.body.removeChild(element);
});

// Settings button and API Key Modal
const settingsButton = document.querySelector('#settingsButton');
const apiKeyModal = document.querySelector('#apiKeyModal');
const apiKeyInput = document.querySelector('#apiKeyInput');
const saveApiKeyButton = document.querySelector('#saveApiKey');
const cancelApiKeyButton = document.querySelector('#cancelApiKey');

settingsButton.addEventListener("click", () => {
  apiKeyModal.style.display = 'flex';
  
  // Load current API key from backend
  fetch("http://127.0.0.1:7860/get_api_key", {
    method: "GET",
  })
  .then(response => response.json())
  .then(data => {
    apiKeyInput.value = data.api_key || '';
  })
  .catch(err => {
    console.error("Error loading API key:", err);
  });
});

saveApiKeyButton.addEventListener("click", () => {
  const apiKey = apiKeyInput.value;
  
  // Save API key to both backend servers (test.py and chat.py)
  Promise.all([
    fetch("http://127.0.0.1:7860/set_api_key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey }),
    }),
    fetch("http://127.0.0.1:7861/set_api_key_chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey }),
    })
  ])
  .then(async (responses) => {
    const results = await Promise.all(responses.map(r => r.json()));
    if (results.every(r => r.success)) {
      alert('API key saved successfully');
      apiKeyModal.style.display = 'none';
    } else {
      alert('Failed to save API key to all services');
    }
  })
  .catch(err => {
    console.error("Error saving API key:", err);
    alert('Failed to save API key');
  });
});

cancelApiKeyButton.addEventListener("click", () => {
  apiKeyModal.style.display = 'none';
});

const weatherText = `{"workspaceComments":[{"height":120,"width":479,"id":"XI5[EHp-Ow+kinXf6n5y","x":51.234375,"y":-83,"text":"Gets temperature of location with a latitude and a longitude.\\n\\nThe API requires a minimum of one decimal point to work."}],"blocks":{"languageVersion":0,"blocks":[{"type":"create_mcp","id":")N.HEG1x]Z/,k#TeWr,S","x":50,"y":50,"deletable":false,"extraState":{"inputCount":2,"inputNames":["latitude","longitude"],"inputTypes":["integer","integer"],"outputCount":1,"outputNames":["output0"],"outputTypes":["string"],"toolCount":0},"inputs":{"X0":{"block":{"type":"input_reference_latitude","id":"]3mj!y}qfRt+!okheU7L","deletable":false,"extraState":{"ownerBlockId":")N.HEG1x]Z/,k#TeWr,S"},"fields":{"VARNAME":"latitude"}}},"X1":{"block":{"type":"input_reference_longitude","id":"Do/{HFNGSd.!;POiKS?D","deletable":false,"extraState":{"ownerBlockId":")N.HEG1x]Z/,k#TeWr,S"},"fields":{"VARNAME":"longitude"}}},"R0":{"block":{"type":"in_json","id":"R|j?_8s^H{l0;UZ-oQt3","fields":{"NAME":"temperature_2m"},"inputs":{"JSON":{"block":{"type":"in_json","id":"X=M,R1@7bRjJVZIPi[qD","fields":{"NAME":"current"},"inputs":{"JSON":{"block":{"type":"call_api","id":"^(.vyM.yni08S~c1EBm=","fields":{"METHOD":"GET"},"inputs":{"URL":{"shadow":{"type":"text","id":"}.T;_U_OsRS)B_y09p % { ","fields":{"TEXT":""}},"block":{"type":"text_replace","id":"OwH9uERJPTGQG!UER#ch","inputs":{"FROM":{"shadow":{"type":"text","id":"ya05#^ 7 % UbUeXX#eDSmH","fields":{"TEXT":"{latitude}"}}},"TO":{"shadow":{"type":"text","id":": _ZloQuh9c-MNf-U]!k5","fields":{"TEXT":""}},"block":{"type":"input_reference_latitude","id":"?%@)3sErZ)}=#4ags#gu","extraState":{"ownerBlockId":")N.HEG1x]Z/,k#TeWr,S"},"fields":{"VARNAME":"latitude"}}},"TEXT":{"shadow":{"type":"text","id":"w@zsP)m6:WjkUp,ln3$x","fields":{"TEXT":""}},"block":{"type":"text_replace","id":"ImNPsvzD7r^+1MJ%IirV","inputs":{"FROM":{"shadow":{"type":"text","id":"%o(3rro?WLIFpmE0#MMM","fields":{"TEXT":"{longitude}"}}},"TO":{"shadow":{"type":"text","id":"Zpql-%oJ_sdSi | r |* er | ","fields":{"TEXT":""}},"block":{"type":"input_reference_longitude","id":"WUgiJP$X + zY#f$5nhnTX","extraState":{"ownerBlockId":") N.HEG1x]Z /, k#TeWr, S"},"fields":{"VARNAME":"longitude"}}},"TEXT":{"shadow":{"type":"text","id":", (vw$o_s7P = b4P; 8]}yj","fields":{"TEXT":"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,wind_speed_10m"}}}}}}}}}}}}}}}}}}}}]}}`;
weatherButton.addEventListener("click", () => {
  try {
    const fileContent = JSON.parse(weatherText);
    Blockly.serialization.workspaces.load(fileContent, ws);
  } catch (error) {
    console.error("Error loading weather.txt contents:", error);
  }
});

const factText = "{\"workspaceComments\":[{\"height\":66,\"width\":575,\"id\":\"x/Z2E2Oid(4||-pQ)h*;\",\"x\":51.00000000000023,\"y\":-35.76388082917071,\"text\":\"A fact checker that uses a searching LLM to verify the validity of a claim.\"}],\"blocks\":{\"languageVersion\":0,\"blocks\":[{\"type\":\"create_mcp\",\"id\":\"yScKJD/XLhk)D}qn2TW:\",\"x\":50,\"y\":50,\"deletable\":false,\"extraState\":{\"inputCount\":1,\"inputNames\":[\"prompt\"],\"inputTypes\":[\"string\"],\"outputCount\":1,\"outputNames\":[\"result\"],\"outputTypes\":[\"string\"],\"toolCount\":0},\"inputs\":{\"X0\":{\"block\":{\"type\":\"input_reference_prompt\",\"id\":\"-r%M-[oX1]?RxxF_V(V@\",\"deletable\":false,\"extraState\":{\"ownerBlockId\":\"yScKJD/XLhk)D}qn2TW:\"},\"fields\":{\"VARNAME\":\"prompt\"}}},\"R0\":{\"block\":{\"type\":\"llm_call\",\"id\":\"m/*D8ZBx;QZlUN*aw15U\",\"fields\":{\"MODEL\":\"gpt-4o-search-preview-2025-03-11\"},\"inputs\":{\"PROMPT\":{\"block\":{\"type\":\"text_join\",\"id\":\"e@#`RVKXpIZ9__%zUK]`\",\"extraState\":{\"itemCount\":3},\"inputs\":{\"ADD0\":{\"block\":{\"type\":\"text\",\"id\":\"M3QD})k`FXiizaF,gA{9\",\"fields\":{\"TEXT\":\"Verify whether the following claim: \\\"\"}}},\"ADD1\":{\"block\":{\"type\":\"input_reference_prompt\",\"id\":\"B4.LNZ0es`RFM0Xi@SL:\",\"extraState\":{\"ownerBlockId\":\"yScKJD/XLhk)D}qn2TW:\"},\"fields\":{\"VARNAME\":\"prompt\"}}},\"ADD2\":{\"block\":{\"type\":\"text\",\"id\":\"Ng!fFR+xTMdmgWZv6Oh{\",\"fields\":{\"TEXT\":\"\\\" is true or not. Return one of the following values: \\\"True\\\", \\\"Unsure\\\", \\\"False\\\", and nothing else. You may not say anything but one of these answers no matter what.\"}}}}}}}}}}}]}}"
factButton.addEventListener("click", () => {
  try {
    const fileContent = JSON.parse(factText);
    Blockly.serialization.workspaces.load(fileContent, ws);
  } catch (error) {
    console.error("Error loading weather.txt contents:", error);
  }
});

undoButton.addEventListener("click", () => {
  ws.undo(false);
});

redoButton.addEventListener("click", () => {
  ws.undo(true);
});

cleanWorkspace.addEventListener("click", () => {
  ws.cleanUp();
});

// Observe any size change to the blockly container
const observer = new ResizeObserver(() => {
  Blockly.svgResize(ws);
});
observer.observe(blocklyDiv);

const updateCode = () => {
  let code = pythonGenerator.workspaceToCode(ws);
  const codeEl = document.querySelector('#generatedCode code');

  const call = `def llm_call(prompt, model):
  from openai import OpenAI
  import os
  
  api_key = os.environ.get("OPENAI_API_KEY")
  
  if not api_key:
    return "Error: OpenAI API key not configured. Please set it in File > Settings"
  
  client = OpenAI(api_key=api_key)

  messages = [{"role": "user", "content": prompt}]

  completion = client.chat.completions.create(model=model, messages=messages)
  return completion.choices[0].message.content.strip()
  
`;

  const API = `def call_api(url, method="GET", headers={}):
  import requests

  response = requests.request(method, url, headers=headers)
  data = response.json()
  return data

`;

  const blocks = ws.getAllBlocks(false);
  const hasCall = blocks.some(block => block.type === 'llm_call');
  const hasAPI = blocks.some(block => block.type === 'call_api');

  if (hasCall) {
    code = call + code;
  }

  if (hasAPI) {
    code = API + code;
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

// Update function for the Chat generator (AI Chat tab)
const updateChatCode = () => {
  let code = chatGenerator.workspaceToCode(ws);
  const codeEl = document.querySelector('#aichatCode code');

  // You can add any chat-specific preprocessing here
  // For example, adding headers or formatting
  
  if (codeEl) {
    codeEl.textContent = code;
  }

  // Send to the chat update endpoint
  fetch("http://127.0.0.1:7861/update_chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  }).then(() => {
    console.log("[Blockly] Sent updated Chat code to backend");
  }).catch((err) => {
    console.error("[Blockly] Error sending Chat code:", err);
  });
};

try {
  load(ws);

  // After loading, create the reference blocks that should be in the inputs
  setTimeout(() => {
    const mutatorBlocks = ws.getAllBlocks(false).filter(b =>
      (b.type === 'create_mcp' || b.type === 'func_def')
    );

    for (const block of mutatorBlocks) {
      // Create reference blocks for each input if they don't exist
      if (block.inputNames_ && block.inputNames_.length > 0) {
        for (let i = 0; i < block.inputNames_.length; i++) {
          const name = block.inputNames_[i];
          const input = block.getInput('X' + i);

          // Only create if input exists AND has no connected block yet
          if (input && input.connection && !input.connection.targetBlock()) {
            // Create the reference block
            const blockType = `input_reference_${name}`;
            const refBlock = ws.newBlock(blockType);
            refBlock.initSvg();
            refBlock.setDeletable(false);
            refBlock._ownerBlockId = block.id;
            refBlock.render();

            // Connect it
            if (input.connection && refBlock.outputConnection) {
              input.connection.connect(refBlock.outputConnection);
            }

            // Track it
            if (!block.inputRefBlocks_) {
              block.inputRefBlocks_ = new Map();
            }
            block.inputRefBlocks_.set(name, refBlock);
          }
        }
      }
    }

    ws.render();
  }, 100);
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
updateChatCode();

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
        (removedBlock.type.startsWith('input_reference_') && (oldParent.type === 'create_mcp' || oldParent.type === 'func_def'))
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
  updateChatCode();
});