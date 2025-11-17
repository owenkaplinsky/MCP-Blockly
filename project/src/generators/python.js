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

  // Main function body and return value(s)
  let body = generator.statementToCode(block, 'BODY');
  let returnStatement = '';

  const returnValues = [];

  // Check if we have outputs defined and the R inputs exist
  if (block.outputCount_ && block.outputCount_ > 0 && block.getInput('R0')) {
    for (let r = 0; r < block.outputCount_; r++) {
      let returnValue = generator.valueToCode(block, 'R' + r, Order.ATOMIC);

      // Replace placeholder args with actual names
      if (returnValue && block.inputNames_) {
        for (let j = 0; j < block.inputNames_.length; j++) {
          const paramName = block.inputNames_[j];
          returnValue = returnValue.replace(new RegExp(`arg${j}\\b`, 'g'), paramName);
        }
      }

      // Type-cast numeric returns to ensure proper Gradio compatibility
      const outputType = block.outputTypes_[r] || 'string';
      if (outputType === 'integer' && returnValue) {
        returnValue = `int(${returnValue})`;
      }

      returnValues.push(returnValue || 'None');
    }

    if (returnValues.length === 1) {
      returnStatement = `  return ${returnValues[0]}\n`;
    } else {
      returnStatement = `  return (${returnValues.join(', ')})\n`;
    }
  } else {
    // No outputs defined, return empty dict for MCP
    returnStatement = '  return {}\n';
  }
  let code = '';

  // Create the main function definition
  if (typedInputs.length > 0) {
    code += `def create_mcp(${typedInputs.join(', ')}):\n  out_amt = ${returnValues.length}\n\n${body}${returnStatement}\n`;
  } else {
    code += `def create_mcp():\n  out_amt = ${returnValues.length}\n\n${body || ''}${returnStatement}`;
  }

  // Map Python types to Gradio components for inputs
  const gradioInputs = [];
  if (block.inputTypes_) {
    for (let k = 0; k < block.inputTypes_.length; k++) {
      const type = block.inputTypes_[k];
      switch (type) {
        case 'integer':
          gradioInputs.push('gr.Number()');
          break;
        case 'string':
          gradioInputs.push('gr.Textbox()');
          break;
        case 'list':
          gradioInputs.push('gr.Dataframe()');
          break;
        default:
          gradioInputs.push('gr.Textbox()');
      }
    }
  }

  // Map Python types to Gradio components for outputs
  const gradioOutputs = [];
  // Only add outputs if they actually exist in the block (R0, R1, etc.)
  if (block.outputTypes_ && block.outputCount_ > 0 && block.getInput('R0')) {
    // Use outputCount_ to ensure we only process actual outputs
    for (let k = 0; k < block.outputCount_; k++) {
      const type = block.outputTypes_[k];
      switch (type) {
        case 'integer':
          gradioOutputs.push('gr.Number()');
          break;
        case 'string':
          gradioOutputs.push('gr.Textbox()');
          break;
        case 'list':
          gradioOutputs.push('gr.Dataframe()');
          break;
        default:
          gradioOutputs.push('gr.Textbox()');
      }
    }
  }

  // Create Gradio Interface with dynamic I/O
  // Always include outputs parameter, use empty list if no outputs
  code += `\ndemo = gr.Interface(
  fn=create_mcp,
  inputs=[${gradioInputs.join(', ')}],
  outputs=[${gradioOutputs.join(', ')}],
  )

demo.launch(mcp_server=True)
`;

  return code;
};

forBlock['func_def'] = function (block, generator) {
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
  let returnStatement = '';

  // Check if we have outputs defined and the R inputs exist
  if (block.outputCount_ && block.outputCount_ > 0 && block.getInput('R0')) {
    const returnValues = [];
    for (let r = 0; r < block.outputCount_; r++) {
      let returnValue = generator.valueToCode(block, 'R' + r, Order.ATOMIC);

      // Replace placeholder args with actual names
      if (returnValue && block.inputNames_) {
        for (let j = 0; j < block.inputNames_.length; j++) {
          const paramName = block.inputNames_[j];
          returnValue = returnValue.replace(new RegExp(`arg${j}\\b`, 'g'), paramName);
        }
      }

      // Type-cast numeric returns to ensure proper Gradio compatibility
      const outputType = block.outputTypes_[r] || 'string';
      if (outputType === 'integer' && returnValue) {
        returnValue = `int(${returnValue})`;
      }

      returnValues.push(returnValue || 'None');
    }

    if (returnValues.length === 1) {
      returnStatement = `  return ${returnValues[0]}\n`;
    } else {
      returnStatement = `  return (${returnValues.join(', ')})\n`;
    }
  } else {
    // No outputs defined, add pass only if body is empty
    if (!body || body.trim() === '') {
      returnStatement = '  pass\n';
    } else {
      returnStatement = '';
    }
  }

  // Construct the function definition
  let code;
  if (typedInputs.length > 0) {
    code = `def ${name}(${typedInputs.join(', ')}):\n${body}${returnStatement}`;
  } else {
    code = `def ${name}():\n${body || '  pass\n'}${returnStatement}`;
  }

  // Add output type hints as comments if outputs are defined
  if (block.outputTypes_ && block.outputTypes_.length > 0) {
    let outputTypes = [];
    for (let k = 0; k < block.outputTypes_.length; k++) {
      const type = block.outputTypes_[k];
      const outName = block.outputNames_[k] || ('output' + k);
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
      outputTypes.push(`${outName}: ${pyType}`);
    }
    code = code.slice(0, -1) + `  # Returns: ${outputTypes.join(', ')}\n`;
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
