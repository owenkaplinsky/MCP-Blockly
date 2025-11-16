import { Order } from 'blockly/python';

export const forBlock = Object.create(null);

forBlock['create_mcp'] = function (block, generator) {
  const typedInputs = [];
  let i = 0;

  // Build list of typed input parameters with inferred Python types
  while (block.getInput('X' + i)) {
    const input = block.getInput('X' + i);
    if (input && input.connection && input.connection.targetBlock()) {
      const paramName = (block.inputNames_ && block.inputNames_[i]) || ('arg' + i);
      const type = (block.inputTypes_ && block.inputTypes_[i]) || 'string';

      let pyType;
      switch (type) {
        case 'integer':
          pyType = 'int';
          break;
        case 'string':
          pyType = 'str';
          break;
        case 'list':
          pyType = 'list';
          break;
        default:
          pyType = 'Any';
      }
      typedInputs.push(`${paramName}: ${pyType}`);
    }
    i++;
  }

  // Gather any tool definitions connected to this block
  let toolDefs = [];
  let t = 0;
  while (block.getInput('T' + t)) {
    const toolCode = generator.valueToCode(block, 'T' + t, Order.NONE);
    if (toolCode) {
      toolDefs.push(toolCode);
    }
    t++;
  }

  // Main function body and return value
  let body = generator.statementToCode(block, 'BODY');
  let returnValue = generator.valueToCode(block, 'RETURN', Order.ATOMIC);

  // Replace placeholder args (arg0, arg1...) with actual names in return statement
  if (returnValue && block.inputNames_) {
    for (let j = 0; j < block.inputNames_.length; j++) {
      const paramName = block.inputNames_[j];
      returnValue = returnValue.replace(new RegExp(`arg${j}\\b`, 'g'), paramName);
    }
  }

  let returnStatement = returnValue ? `  return ${returnValue}\n` : '  return\n';
  let code = '';

  // Tool definitions come before main function
  if (toolDefs.length > 0) {
    code += toolDefs.join('\n') + '\n\n';
  }

  // Create the main function definition
  if (typedInputs.length > 0) {
    code += `def create_mcp(${typedInputs.join(', ')}):\n${body}${returnStatement}\n`;
  } else {
    code += `def create_mcp():\n${body}${returnStatement}`;
  }

  return code;
};

forBlock['tool_def'] = function (block, generator) {
  const name = block.getFieldValue('NAME');
  const typedInputs = [];
  let i = 0;

  // Build function signature with typed arguments
  while (block.getInput('X' + i)) {
    const input = block.getInput('X' + i);
    if (input && input.connection && input.connection.targetBlock()) {
      const paramName = (block.inputNames_ && block.inputNames_[i]) || ('arg' + i);
      const type = (block.inputTypes_ && block.inputTypes_[i]) || 'string';

      let pyType;
      switch (type) {
        case 'integer':
          pyType = 'int';
          break;
        case 'string':
          pyType = 'str';
          break;
        case 'list':
          pyType = 'list';
          break;
        default:
          pyType = 'Any';
      }
      typedInputs.push(`${paramName}: ${pyType}`);
    }
    i++;
  }

  let body = generator.statementToCode(block, 'BODY');
  let returnValue = generator.valueToCode(block, 'RETURN', Order.ATOMIC);

  // Ensure return expression uses correct parameter names
  if (returnValue && block.inputNames_) {
    for (let j = 0; j < block.inputNames_.length; j++) {
      const paramName = block.inputNames_[j];
      returnValue = returnValue.replace(new RegExp(`arg${j}\\b`, 'g'), paramName);
    }
  }

  let returnStatement = returnValue ? `  return ${returnValue}\n` : '  return\n';

  // Construct the function definition
  let code;
  if (typedInputs.length > 0) {
    code = `def ${name}(${typedInputs.join(', ')}):\n${body}${returnStatement}`;
  } else {
    code = `def ${name}():\n${body}${returnStatement}`;
  }

  // Return function definition as a string value (not executed immediately)
  return code;
};

forBlock['llm_call'] = function (block, generator) {
  const model = block.getFieldValue('MODEL');
  const prompt = generator.valueToCode(block, 'PROMPT', Order.NONE) || "''";

  // Generate code to call an LLM model with a prompt
  const code = `llm_call(${prompt}, model="${model}")`;
  return [code, Order.NONE];
};
