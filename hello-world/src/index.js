/**
 * @license
 * Copyright 2023 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import * as Blockly from 'blockly';
import { blocks } from './blocks/text';
import { forBlock } from './generators/python';
import { pythonGenerator } from 'blockly/python';
import { save, load } from './serialization';
import { toolbox } from './toolbox';
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
  renderer: 'zelos',
  theme: myTheme,
});

if (!ws.getVariable('user_message')) {
  ws.createVariable('user_message');
}

ws.updateUserMessage = (message) => {
  let variable = ws.getVariable('user_message');
  if (!variable) ws.createVariable('user_message');
  ws.variableValues = ws.variableValues || {};
  ws.variableValues['user_message'] = message;
};

const updateCode = () => {
  let code = pythonGenerator.workspaceToCode(ws);
  const codeEl = document.querySelector('#generatedCode code');

  const response = `def get_assistant_response(prompt, model, use_history=True):
  global history
  from openai import OpenAI
  import os

  client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

  if use_history:
      messages = history + [{"role": "user", "content": prompt}]
  else:
      messages = [{"role": "user", "content": prompt}]

  completion = client.chat.completions.create(model=model, messages=messages)
  return completion.choices[0].message.content.strip()
  
`;

  const blocks = ws.getAllBlocks(false);
  const hasResponse = blocks.some(block => block.type === 'assistant_reply');

  if (hasResponse) {
    code = response + code;
  }

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
updateCode();

ws.addChangeListener((e) => {
  if (e.isUiEvent) return;

  if (!ws.getVariable('user_message')) {
    ws.createVariable('user_message');
  }

  save(ws);
});

ws.addChangeListener((e) => {
  if (e.isUiEvent || e.type == Blockly.Events.FINISHED_LOADING || ws.isDragging()) {
    return;
  }
  updateCode();
});

window.addEventListener("message", (event) => {
  if (event.data?.type === "user_message") {
    handleUserMessage(event.data.text);
  }
});

function handleUserMessage(message) {
  if (window.Blockly && window.ws) {
    let v = ws.getVariable('user_message') || ws.createVariable('user_message');
    ws.variableValues = ws.variableValues || {};
    ws.variableValues['user_message'] = message;
  }

  if (typeof window.userSendHandler === "function") {
    console.log("[PARENT] userSendHandler exists, invoking it");
    window.userSendHandler(message);
  } else {
    console.warn("[PARENT] userSendHandler is undefined!");
  }
}
