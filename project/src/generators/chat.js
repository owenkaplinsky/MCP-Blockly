import * as Blockly from 'blockly';

// Create a custom generator for the chat/AI language
class ChatGenerator extends Blockly.Generator {
  constructor(name) {
    super(name);
    // Custom order definitions for the chat language if needed
    this.ORDER_ATOMIC = 0;
  }

  // Override scrub_ to handle how blocks are joined
  scrub_(block, code, thisOnly) {
    const nextBlock = block.nextConnection && block.nextConnection.targetBlock();
    let nextCode = '';
    if (nextBlock) {
      nextCode = this.blockToCode(nextBlock);
    }
    return code + nextCode;
  }
}

// Create an instance of the chat generator
export const chatGenerator = new ChatGenerator('Chat');

// Export forBlock for custom block definitions
export const forBlock = Object.create(null);

/*

This file is for the secondary code generator.
It is not meant to be shown to the user, but rather to communicate the state of the workspace to an AI Assistant assistant in a simplistic text format.

*/

forBlock['create_mcp'] = function (block, generator) {
  const inputParams = [];
  const outputParams = [];
  let i = 0;

  // Build list of input parameters with types
  while (block.getInput('X' + i)) {
    const input = block.getInput('X' + i);
    if (input && input.connection && input.connection.targetBlock()) {
      const paramName = (block.inputNames_ && block.inputNames_[i]) || ('arg' + i);
      const type = (block.inputTypes_ && block.inputTypes_[i]) || 'string';
      inputParams.push(`${paramName}: ${type}`);
    }
    i++;
  }

  // Build list of output parameters with values (not types)
  if (block.outputCount_ && block.outputCount_ > 0 && block.getInput('R0')) {
    for (let r = 0; r < block.outputCount_; r++) {
      const outputName = (block.outputNames_ && block.outputNames_[r]) || `result${r}`;
      let returnValue = generator.valueToCode(block, 'R' + r, chatGenerator.ORDER_ATOMIC) || 'None';
      
      // Replace placeholder args with actual names
      if (returnValue && block.inputNames_) {
        for (let j = 0; j < block.inputNames_.length; j++) {
          const paramName = block.inputNames_[j];
          returnValue = returnValue.replace(new RegExp(`arg${j}\\b`, 'g'), paramName);
        }
      }
      
      outputParams.push(`${outputName}: ${returnValue}`);
    }
  }

  // Main function body
  let body = generator.statementToCode(block, 'BODY');

  // Construct the create_mcp call with inputs and outputs
  // Include block ID for deletion tracking with pipe separator
  let code = `${block.id} | create_mcp(inputs(${inputParams.join(', ')}), outputs(${outputParams.join(', ')}))`

  // Add the function body
  if (body) {
    code += body;
  }

  return code;
};

forBlock['func_def'] = function (block, generator) {
  const name = block.getFieldValue('NAME');
  const inputParams = [];
  const outputParams = [];
  let i = 0;

  // Build list of input parameters with types
  while (block.getInput('X' + i)) {
    const input = block.getInput('X' + i);
    if (input && input.connection && input.connection.targetBlock()) {
      const paramName = (block.inputNames_ && block.inputNames_[i]) || ('arg' + i);
      const type = (block.inputTypes_ && block.inputTypes_[i]) || 'string';
      inputParams.push(`${paramName}: ${type}`);
    }
    i++;
  }

  // Build list of output parameters with values (not types)
  if (block.outputCount_ && block.outputCount_ > 0 && block.getInput('R0')) {
    for (let r = 0; r < block.outputCount_; r++) {
      const outputName = (block.outputNames_ && block.outputNames_[r]) || `output${r}`;
      let returnValue = generator.valueToCode(block, 'R' + r, chatGenerator.ORDER_ATOMIC) || 'None';
      
      // Replace placeholder args with actual names
      if (returnValue && block.inputNames_) {
        for (let j = 0; j < block.inputNames_.length; j++) {
          const paramName = block.inputNames_[j];
          returnValue = returnValue.replace(new RegExp(`arg${j}\\b`, 'g'), paramName);
        }
      }
      
      outputParams.push(`${outputName}: ${returnValue}`);
    }
  }

  // Main function body
  let body = generator.statementToCode(block, 'BODY');

  // Construct the func_def call with inputs and outputs
  // Include block ID for deletion tracking with pipe separator
  let code = `${block.id} | ${name}(inputs(${inputParams.join(', ')}), outputs(${outputParams.join(', ')}))`

  // Add the function body
  if (body) {
    code += body;
  }

  return code;
};

// Handler for input reference blocks
forBlock['input_reference'] = function(block, generator) {
  const varName = block.getFieldValue('VARNAME') || 
                  block.type.replace('input_reference_', '') || 
                  'unnamed_arg';
  // Value blocks must return a tuple: [code, order]
  return [varName, chatGenerator.ORDER_ATOMIC];
};

// Register the forBlock definitions with the chat generator
Object.assign(chatGenerator.forBlock, forBlock);

// Override workspaceToCode to include standalone value blocks
chatGenerator.workspaceToCode = function(workspace) {
  if (!workspace) {
    // Backwards compatibility from before there could be multiple workspaces.
    console.warn('No workspace specified in workspaceToCode call.  Guessing.');
    workspace = Blockly.getMainWorkspace();
  }
  let code = [];
  const blocks = workspace.getTopBlocks(true);
  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i];
    // Process ALL top-level blocks, including value blocks
    if (block.outputConnection) {
      // This is a value block - check if it's connected
      if (!block.outputConnection.isConnected()) {
        // Standalone value block - get its code
        const line = this.blockToCode(block, true);
        if (Array.isArray(line)) {
          // Value blocks return [code, order], extract just the code
          const blockCode = line[0];
          if (blockCode) {
            code.push(blockCode);
          }
        } else if (line) {
          code.push(line);
        }
      }
    } else {
      // Regular statement block
      const line = this.blockToCode(block);
      if (Array.isArray(line)) {
        // Shouldn't happen for statement blocks, but handle it anyway
        code.push(line[0]);
      } else if (line) {
        code.push(line);
      }
    }
  }
  code = code.join('\n');  // Blank line between each section.
  // Strip trailing whitespace
  code = code.replace(/\n\s*$/g, '\n');
  return code;
};

// Override blockToCode to provide a catch-all handler
const originalBlockToCode = chatGenerator.blockToCode.bind(chatGenerator);
chatGenerator.blockToCode = function(block, opt_thisOnly) {
  // Null check
  if (!block) {
    return '';
  }
  
  // Check if it's an input reference block type
  if (block.type.startsWith('input_reference_')) {
    const varName = block.getFieldValue('VARNAME') || 
                    block.type.replace('input_reference_', '') || 
                    'unnamed_arg';
    // Value blocks must return a tuple: [code, order]
    return [varName, this.ORDER_ATOMIC];
  }
  
  // Try the normal generation first
  try {
    return originalBlockToCode(block, opt_thisOnly);
  } catch (e) {
    // Catch-all handler for blocks without specific generators
    const blockType = block.type;
    const inputs = [];
    
    // Special handling for common blocks with field values
    if (blockType === 'text') {
      const text = block.getFieldValue('TEXT');
      if (text !== null && text !== undefined) {
        inputs.push(`TEXT: "${text}"`);
      }
    } else if (blockType === 'math_number') {
      const num = block.getFieldValue('NUM');
      if (num !== null && num !== undefined) {
        inputs.push(`NUM: ${num}`);
      }
    } else {
      // Generic field value extraction for other blocks
      // Get all inputs to check for fields
      const inputList = block.inputList || [];
      for (const input of inputList) {
        // Check fields in each input
        if (input.fieldRow) {
          for (const field of input.fieldRow) {
            if (field && field.name && field.getValue) {
              const value = field.getValue();
              if (value !== null && value !== undefined && value !== '') {
                // Format the value appropriately
                const formattedValue = typeof value === 'string' ? `"${value}"` : value;
                inputs.push(`${field.name}: ${formattedValue}`);
              }
            }
          }
        }
      }
    }
    
    // Then get all value inputs (connected blocks)
    const inputList = block.inputList || [];
    for (const input of inputList) {
      if (input.type === Blockly.INPUT_VALUE && input.connection) {
        const inputName = input.name;
        const inputValue = this.valueToCode(block, inputName, this.ORDER_ATOMIC);
        
        if (inputValue) {
          inputs.push(`${inputName}: ${inputValue}`);
        }
      }
    }
    
    // Generate the standard format: name(inputs(...)) with block ID and pipe separator
    const code = `${block.id} | ${blockType}(inputs(${inputs.join(', ')}))`;
    
    // Handle statement inputs (for blocks that have a body)
    let statements = '';
    for (const input of inputList) {
      if (input.type === Blockly.NEXT_STATEMENT && input.connection) {
        const statementCode = this.statementToCode(block, input.name);
        if (statementCode) {
          statements += statementCode;
        }
      }
    }
    
    // Return appropriate format based on whether it's a value or statement block
    if (block.outputConnection) {
      // This is a value block (can be plugged into inputs)
      // Check if this block is connected to another block's input
      const isConnectedToInput = block.outputConnection && block.outputConnection.isConnected();
      
      if (isConnectedToInput) {
        // When used as input to another block, don't include the ID
        const valueCode = `${blockType}(inputs(${inputs.join(', ')}))`;
        return [valueCode, this.ORDER_ATOMIC];
      } else {
        // When standalone (not connected), include the ID
        const standaloneCode = `${block.id} | ${blockType}(inputs(${inputs.join(', ')}))`;
        // For standalone value blocks, we need to return them as statement-like
        // but still maintain the value block return format for Blockly
        return [standaloneCode, this.ORDER_ATOMIC];
      }
    } else {
      // This is a statement block (has prev/next connections)
      const fullCode = code + (statements ? '\n' + statements : '');
      
      // Handle the next block in the sequence if not opt_thisOnly
      if (!opt_thisOnly) {
        const nextCode = this.scrub_(block, fullCode, opt_thisOnly);
        return nextCode;
      }
      
      return fullCode + '\n';
    }
  }
};