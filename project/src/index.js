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

const weatherText = `{"workspaceComments":[{"height":120,"width":479,"id":"XI5[EHp-Ow+kinXf6n5y","x":51.234375,"y":-83,"text":"Gets temperature of location with a latitude and a longitude.\\n\\nThe API requires a minimum of one decimal point to work."}],"blocks":{"languageVersion":0,"blocks":[{"type":"create_mcp","id":")N.HEG1x]Z/,k#TeWr,S","x":50,"y":50,"deletable":false,"extraState":{"inputCount":2,"inputNames":["latitude","longitude"],"inputTypes":["string","string"],"outputCount":1,"outputNames":["output0"],"outputTypes":["string"],"toolCount":0},"inputs":{"X0":{"block":{"type":"input_reference_latitude","id":"]3mj!y}qfRt+!okheU7L","deletable":false,"extraState":{"ownerBlockId":")N.HEG1x]Z/,k#TeWr,S"},"fields":{"VARNAME":"latitude"}}},"X1":{"block":{"type":"input_reference_longitude","id":"Do/{HFNGSd.!;POiKS?D","deletable":false,"extraState":{"ownerBlockId":")N.HEG1x]Z/,k#TeWr,S"},"fields":{"VARNAME":"longitude"}}},"R0":{"block":{"type":"in_json","id":"R|j?_8s^H{l0;UZ-oQt3","fields":{"NAME":"temperature_2m"},"inputs":{"JSON":{"block":{"type":"in_json","id":"X=M,R1@7bRjJVZIPi[qD","fields":{"NAME":"current"},"inputs":{"JSON":{"block":{"type":"call_api","id":"^(.vyM.yni08S~c1EBm=","fields":{"METHOD":"GET"},"inputs":{"URL":{"shadow":{"type":"text","id":"}.T;_U_OsRS)B_y09p % { ","fields":{"TEXT":""}},"block":{"type":"text_replace","id":"OwH9uERJPTGQG!UER#ch","inputs":{"FROM":{"shadow":{"type":"text","id":"ya05#^ 7 % UbUeXX#eDSmH","fields":{"TEXT":"{latitude}"}}},"TO":{"shadow":{"type":"text","id":": _ZloQuh9c-MNf-U]!k5","fields":{"TEXT":""}},"block":{"type":"input_reference_latitude","id":"?%@)3sErZ)}=#4ags#gu","extraState":{"ownerBlockId":")N.HEG1x]Z/,k#TeWr,S"},"fields":{"VARNAME":"latitude"}}},"TEXT":{"shadow":{"type":"text","id":"w@zsP)m6:WjkUp,ln3$x","fields":{"TEXT":""}},"block":{"type":"text_replace","id":"ImNPsvzD7r^+1MJ%IirV","inputs":{"FROM":{"shadow":{"type":"text","id":"%o(3rro?WLIFpmE0#MMM","fields":{"TEXT":"{longitude}"}}},"TO":{"shadow":{"type":"text","id":"Zpql-%oJ_sdSi | r |* er | ","fields":{"TEXT":""}},"block":{"type":"input_reference_longitude","id":"WUgiJP$X + zY#f$5nhnTX","extraState":{"ownerBlockId":") N.HEG1x]Z /, k#TeWr, S"},"fields":{"VARNAME":"longitude"}}},"TEXT":{"shadow":{"type":"text","id":", (vw$o_s7P = b4P; 8]}yj","fields":{"TEXT":"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,wind_speed_10m"}}}}}}}}}}}}}}}}}}}}]}}`;
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

// Set up SSE connection for deletion requests
const setupDeletionStream = () => {
  const eventSource = new EventSource('http://127.0.0.1:7861/delete_stream');
  const processedRequests = new Set(); // Track processed deletion requests
  
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      
      // Skip heartbeat messages
      if (data.heartbeat) return;
      
      // Skip if we've already processed this exact request
      const requestKey = `${data.block_id}_${Date.now()}`;
      if (data.block_id && processedRequests.has(data.block_id)) {
        console.log('[SSE] Skipping duplicate deletion request for:', data.block_id);
        return;
      }
      if (data.block_id) {
        processedRequests.add(data.block_id);
        // Clear after 10 seconds to allow retries if needed
        setTimeout(() => processedRequests.delete(data.block_id), 10000);
      }
      
      if (data.block_id) {
        console.log('[SSE] Received deletion request for block:', data.block_id);
        
        // Try to delete the block
        const block = ws.getBlockById(data.block_id);
        let success = false;
        let error = null;
        
        if (block) {
          console.log('[SSE] Found block to delete:', block.type, block.id);
          // Check if it's the main create_mcp block (which shouldn't be deleted)
          if (block.type === 'create_mcp' && !block.isDeletable()) {
            error = 'Cannot delete the main create_mcp block';
            console.log('[SSE] Block is protected create_mcp');
          } else {
            try {
              block.dispose(true);
              success = true;
              console.log('[SSE] Successfully deleted block:', data.block_id);
            } catch (e) {
              error = e.toString();
              console.error('[SSE] Error deleting block:', e);
            }
          }
        } else {
          error = 'Block not found';
          console.log('[SSE] Block not found:', data.block_id);
        }
        
        // Send result back to backend immediately
        console.log('[SSE] Sending deletion result:', { block_id: data.block_id, success, error });
        fetch('http://127.0.0.1:7861/deletion_result', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            block_id: data.block_id,
            success: success,
            error: error
          })
        }).then(response => {
          console.log('[SSE] Deletion result sent successfully');
        }).catch(err => {
          console.error('[SSE] Error sending deletion result:', err);
        });
      }
    } catch (err) {
      console.error('[SSE] Error processing message:', err);
    }
  };
  
  eventSource.onerror = (error) => {
    console.error('[SSE] Connection error:', error);
    // Reconnect after 5 seconds
    setTimeout(() => {
      console.log('[SSE] Attempting to reconnect...');
      setupDeletionStream();
    }, 5000);
  };
  
  eventSource.onopen = () => {
    console.log('[SSE] Connected to deletion stream');
  };
};

// Start the SSE connection
setupDeletionStream();

// Set up SSE connection for creation requests
const setupCreationStream = () => {
  const eventSource = new EventSource('http://127.0.0.1:7861/create_stream');
  const processedRequests = new Set(); // Track processed creation requests
  
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      
      // Skip heartbeat messages
      if (data.heartbeat) return;
      
      // Skip if we've already processed this request
      if (data.request_id && processedRequests.has(data.request_id)) {
        console.log('[SSE CREATE] Skipping duplicate creation request:', data.request_id);
        return;
      }
      if (data.request_id) {
        processedRequests.add(data.request_id);
        // Clear after 10 seconds to allow retries if needed
        setTimeout(() => processedRequests.delete(data.request_id), 10000);
      }
      
      if (data.block_spec && data.request_id) {
        console.log('[SSE CREATE] Received creation request:', data.request_id, data.block_spec);
        
        let success = false;
        let error = null;
        let blockId = null;
        
        try {
          // Parse and create blocks recursively
          function parseAndCreateBlock(spec, shouldPosition = false) {
            // Match block_name(inputs(...))
            const blockMatch = spec.match(/^(\w+)\s*\((.+)\)$/s);
            
            if (!blockMatch) {
              throw new Error(`Invalid block specification format: ${spec}`);
            }
            
            const blockType = blockMatch[1];
            const content = blockMatch[2].trim();
            
            console.log('[SSE CREATE] Parsing block:', blockType, 'with content:', content);
            
            // Check if this has inputs() wrapper
            let inputsContent = content;
            if (content.startsWith('inputs(') && content.endsWith(')')) {
              inputsContent = content.slice(7, -1); // Remove 'inputs(' and ')'
            }
            
            // Create the block
            const newBlock = ws.newBlock(blockType);
            
            if (inputsContent) {
              // Parse the inputs content
              const inputs = parseInputs(inputsContent);
              console.log('[SSE CREATE] Parsed inputs:', inputs);
              
              // Set field values and connect child blocks
              for (const [key, value] of Object.entries(inputs)) {
                if (typeof value === 'string') {
                  // Check if this is a nested block specification
                  if (value.match(/^\w+\s*\(inputs\(/)) {
                    // This is a nested block, create it recursively
                    const childBlock = parseAndCreateBlock(value);
                    
                    // Connect the child block to the appropriate input
                    const input = newBlock.getInput(key);
                    if (input && input.connection) {
                      childBlock.outputConnection.connect(input.connection);
                    }
                  } else {
                    // This is a simple value, set it as a field
                    // Remove quotes if present
                    const cleanValue = value.replace(/^["']|["']$/g, '');
                    
                    // Try to set as a field value
                    try {
                      newBlock.setFieldValue(cleanValue, key);
                    } catch (e) {
                      console.log(`[SSE CREATE] Could not set field ${key} to ${cleanValue}:`, e);
                    }
                  }
                } else if (typeof value === 'number') {
                  // Set numeric field value
                  try {
                    newBlock.setFieldValue(value, key);
                  } catch (e) {
                    console.log(`[SSE CREATE] Could not set field ${key} to ${value}:`, e);
                  }
                } else if (typeof value === 'boolean') {
                  // Set boolean field value
                  try {
                    newBlock.setFieldValue(value ? 'TRUE' : 'FALSE', key);
                  } catch (e) {
                    console.log(`[SSE CREATE] Could not set field ${key} to ${value}:`, e);
                  }
                }
              }
            }
            
            // Initialize the block (renders it)
            newBlock.initSvg();
            
            // Only position the top-level block
            if (shouldPosition) {
              // Find a good position that doesn't overlap existing blocks
              const existingBlocks = ws.getAllBlocks();
              let x = 50;
              let y = 50;
              
              // Simple positioning: stack new blocks vertically
              if (existingBlocks.length > 0) {
                const lastBlock = existingBlocks[existingBlocks.length - 1];
                const lastPos = lastBlock.getRelativeToSurfaceXY();
                y = lastPos.y + lastBlock.height + 20;
              }
              
              newBlock.moveBy(x, y);
            }
            
            // Render the block
            newBlock.render();
            
            return newBlock;
          }
          
          // Helper function to parse inputs(key: value, key2: value2, ...)
          function parseInputs(inputStr) {
            const result = {};
            let currentKey = '';
            let currentValue = '';
            let depth = 0;
            let inQuotes = false;
            let quoteChar = '';
            let readingKey = true;
            
            for (let i = 0; i < inputStr.length; i++) {
              const char = inputStr[i];
              
              // Handle quotes
              if ((char === '"' || char === "'") && (i === 0 || inputStr[i-1] !== '\\')) {
                if (!inQuotes) {
                  inQuotes = true;
                  quoteChar = char;
                } else if (char === quoteChar) {
                  inQuotes = false;
                  quoteChar = '';
                }
              }
              
              // Handle parentheses depth (for nested blocks)
              if (!inQuotes) {
                if (char === '(') depth++;
                else if (char === ')') depth--;
              }
              
              // Handle key-value separation
              if (char === ':' && depth === 0 && !inQuotes && readingKey) {
                readingKey = false;
                currentKey = currentKey.trim();
                continue;
              }
              
              // Handle comma separation
              if (char === ',' && depth === 0 && !inQuotes && !readingKey) {
                // Store the key-value pair
                currentValue = currentValue.trim();
                
                // Parse the value
                if (currentValue.match(/^\w+\s*\(inputs\(/)) {
                  // This is a nested block
                  result[currentKey] = currentValue;
                } else if (currentValue.match(/^-?\d+(\.\d+)?$/)) {
                  // This is a number
                  result[currentKey] = parseFloat(currentValue);
                } else if (currentValue === 'true' || currentValue === 'false') {
                  // This is a boolean
                  result[currentKey] = currentValue === 'true';
                } else {
                  // This is a string (remove quotes if present)
                  result[currentKey] = currentValue.replace(/^["']|["']$/g, '');
                }
                
                // Reset for next key-value pair
                currentKey = '';
                currentValue = '';
                readingKey = true;
                continue;
              }
              
              // Accumulate characters
              if (readingKey) {
                currentKey += char;
              } else {
                currentValue += char;
              }
            }
            
            // Handle the last key-value pair
            if (currentKey && currentValue) {
              currentKey = currentKey.trim();
              currentValue = currentValue.trim();
              
              // Parse the value
              if (currentValue.match(/^\w+\s*\(inputs\(/)) {
                // This is a nested block
                result[currentKey] = currentValue;
              } else if (currentValue.match(/^-?\d+(\.\d+)?$/)) {
                // This is a number
                result[currentKey] = parseFloat(currentValue);
              } else if (currentValue === 'true' || currentValue === 'false') {
                // This is a boolean
                result[currentKey] = currentValue === 'true';
              } else {
                // This is a string (remove quotes if present)
                result[currentKey] = currentValue.replace(/^["']|["']$/g, '');
              }
            }
            
            return result;
          }
          
          // Create the block and all its nested children
          const newBlock = parseAndCreateBlock(data.block_spec, true);
          
          if (newBlock) {
            blockId = newBlock.id;
            success = true;
            console.log('[SSE CREATE] Successfully created block with children:', blockId, newBlock.type);
          } else {
            throw new Error(`Failed to create block from specification`);
          }
          
        } catch (e) {
          error = e.toString();
          console.error('[SSE CREATE] Error creating block:', e);
        }
        
        // Send result back to backend immediately
        console.log('[SSE CREATE] Sending creation result:', { 
          request_id: data.request_id, 
          success, 
          error,
          block_id: blockId 
        });
        
        fetch('http://127.0.0.1:7861/creation_result', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            request_id: data.request_id,
            success: success,
            error: error,
            block_id: blockId
          })
        }).then(response => {
          console.log('[SSE CREATE] Creation result sent successfully');
        }).catch(err => {
          console.error('[SSE CREATE] Error sending creation result:', err);
        });
      }
    } catch (err) {
      console.error('[SSE CREATE] Error processing message:', err);
    }
  };
  
  eventSource.onerror = (error) => {
    console.error('[SSE CREATE] Connection error:', error);
    // Reconnect after 5 seconds
    setTimeout(() => {
      console.log('[SSE CREATE] Attempting to reconnect...');
      setupCreationStream();
    }, 5000);
  };
  
  eventSource.onopen = () => {
    console.log('[SSE CREATE] Connected to creation stream');
  };
};

// Start the creation SSE connection
setupCreationStream();

// Observe any size change to the blockly container
const observer = new ResizeObserver(() => {
  Blockly.svgResize(ws);
});
observer.observe(blocklyDiv);

const updateCode = () => {
  // Instead of using workspaceToCode which processes ALL blocks,
  // manually process only blocks connected to create_mcp or func_def
  let code = '';
  
  // Get all top-level blocks (not connected to other blocks)
  const topBlocks = ws.getTopBlocks(false);
  
  // Process only create_mcp and func_def blocks
  for (const block of topBlocks) {
    if (block.type === 'create_mcp' || block.type === 'func_def') {
      // Generate code for this block and its connected blocks
      const blockCode = pythonGenerator.blockToCode(block);
      if (blockCode) {
        if (Array.isArray(blockCode)) {
          code += blockCode[0] + '\n';
        } else {
          code += blockCode + '\n';
        }
      }
    }
    // Ignore any other top-level blocks (stray blocks)
  }
  
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

// Track if chat backend is available
let chatBackendAvailable = false;
let chatUpdateQueue = [];
let chatRetryTimeout = null;

// Function to check if chat backend is available
const checkChatBackend = async () => {
  try {
    const response = await fetch("http://127.0.0.1:7861/update_chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: "" }),
    });
    if (response.ok) {
      chatBackendAvailable = true;
      console.log("[Blockly] Chat backend is available");
      // Process any queued updates
      processChatUpdateQueue();
      return true;
    }
  } catch (err) {
    chatBackendAvailable = false;
  }
  return false;
};

// Process queued chat updates
const processChatUpdateQueue = () => {
  if (chatBackendAvailable && chatUpdateQueue.length > 0) {
    const code = chatUpdateQueue.pop(); // Get the latest update
    chatUpdateQueue = []; // Clear the queue
    sendChatUpdate(code);
  }
};

// Send chat update with retry logic
const sendChatUpdate = async (code, retryCount = 0) => {
  try {
    const response = await fetch("http://127.0.0.1:7861/update_chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    
    if (response.ok) {
      chatBackendAvailable = true;
      console.log("[Blockly] Sent updated Chat code to backend");
    } else {
      throw new Error(`Server responded with status ${response.status}`);
    }
  } catch (err) {
    console.warn(`[Blockly] Chat backend not ready (attempt ${retryCount + 1}):`, err.message);
    chatBackendAvailable = false;
    
    // Queue this update for retry
    if (retryCount < 5) {
      const delay = Math.min(1000 * Math.pow(2, retryCount), 10000); // Exponential backoff, max 10s
      setTimeout(() => {
        if (!chatBackendAvailable) {
          checkChatBackend().then(available => {
            if (available) {
              sendChatUpdate(code, retryCount + 1);
            } else if (retryCount < 4) {
              sendChatUpdate(code, retryCount + 1);
            }
          });
        }
      }, delay);
    }
  }
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

  // If backend is available, send immediately
  if (chatBackendAvailable) {
    sendChatUpdate(code);
  } else {
    // Queue the update and try to establish connection
    chatUpdateQueue.push(code);
    
    // Clear any existing retry timeout
    if (chatRetryTimeout) {
      clearTimeout(chatRetryTimeout);
    }
    
    // Try to connect to backend
    checkChatBackend();
    
    // Set up periodic retry
    chatRetryTimeout = setTimeout(() => {
      checkChatBackend();
    }, 2000);
  }
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

// Check if chat backend is available before first update
checkChatBackend().then(() => {
  updateChatCode();
});

// Also set up periodic health checks for the chat backend
setInterval(() => {
  if (!chatBackendAvailable) {
    checkChatBackend();
  }
}, 5000); // Check every 5 seconds if not connected

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