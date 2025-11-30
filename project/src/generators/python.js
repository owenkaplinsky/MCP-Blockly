import { Order } from 'blockly/python';
import * as Blockly from 'blockly';

export const forBlock = Object.create(null);

forBlock['create_mcp'] = function (block, generator) {
  // Ensure the generator is properly initialized for nested blocks like loops
  if (!generator.nameDB_) {
    generator.nameDB_ = new Blockly.Names(generator.RESERVED_WORDS_ || []);
  }

  // Ensure getDistinctName is available for control flow blocks
  if (!generator.getDistinctName) {
    generator.getDistinctName = function (name, type) {
      return this.nameDB_.getDistinctName(name, type);
    };
  }

  const typedInputs = [];
  const listParams = [];
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
        case 'float':
          pyType = 'float';
          break;
        case 'string':
          pyType = 'str';
          break;
        case 'list':
          pyType = 'str';
          listParams.push(paramName);
          break;
        case 'boolean':
          pyType = 'bool';
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
  
  // Add list conversion code at the beginning of the body
  let listConversionCode = '';
  if (listParams.length > 0) {
    for (const param of listParams) {
      listConversionCode += `  try:\n    ${param} = ast.literal_eval(${param})\n  except:\n    ${param} = [${param}]\n`;
    }
  }
  
  body = listConversionCode + body;
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

      // Type-cast returns to ensure proper Gradio compatibility
      const outputType = block.outputTypes_[r] || 'string';
      if (outputType === 'integer' && returnValue) {
        returnValue = `int(${returnValue})`;
      } else if (outputType === 'float' && returnValue) {
        returnValue = `float(${returnValue})`;
      } else if (outputType === 'boolean' && returnValue) {
        returnValue = `bool(${returnValue})`;
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
    code += `def create_mcp(${typedInputs.join(', ')}):\n  in_types = ${JSON.stringify(block.inputTypes_ || [])}\n  out_amt = ${returnValues.length}\n  out_names = ${JSON.stringify(block.outputNames_ || [])}\n  out_types = ${JSON.stringify(block.outputTypes_ || [])}\n\n${body}${returnStatement}\n`;
  } else {
    code += `def create_mcp():\n  in_types = ${JSON.stringify(block.inputTypes_ || [])}\n  out_amt = ${returnValues.length}\n  out_names = ${JSON.stringify(block.outputNames_ || [])}\n  out_types = ${JSON.stringify(block.outputTypes_ || [])}\n\n${body || ''}${returnStatement}`;
  }

  // Map Python types to Gradio components for inputs
  // Only add inputs if they actually exist in the block (X0, X1, etc.)
  const gradioInputs = [];
  if (block.inputCount_ && block.inputCount_ > 0 && block.getInput('X0')) {
    for (let k = 0; k < block.inputCount_; k++) {
      const type = block.inputTypes_[k];
      switch (type) {
        case 'integer':
          gradioInputs.push('gr.Number()');
          break;
        case 'float':
          gradioInputs.push('gr.Number()');
          break;
        case 'string':
          gradioInputs.push('gr.Textbox()');
          break;
        case 'list':
          gradioInputs.push('gr.Textbox()');
          break;
        case 'boolean':
          gradioInputs.push('gr.Checkbox()');
          break;
        case 'any':
          gradioInputs.push('gr.JSON()');
          break;
        default:
          gradioInputs.push('gr.Textbox()');
      }
    }
  }

  // Map Python types to Gradio components for outputs
  const gradioOutputs = [];
  // Only add outputs if they actually exist in the block (R0, R1, etc.)
  if (block.outputCount_ && block.outputCount_ > 0 && block.getInput('R0')) {
    // Use outputCount_ to ensure we only process actual outputs
    for (let k = 0; k < block.outputCount_; k++) {
      const type = block.outputTypes_[k];
      switch (type) {
        case 'integer':
          gradioOutputs.push('gr.Number()');
          break;
        case 'float':
          gradioOutputs.push('gr.Number()');
          break;
        case 'string':
          gradioOutputs.push('gr.Textbox()');
          break;
        case 'list':
          gradioOutputs.push('gr.Dataframe()');
          break;
        case 'boolean':
          gradioOutputs.push('gr.Checkbox()');
          break;
        case 'any':
          gradioOutputs.push('gr.JSON()');
          break;
        default:
          gradioOutputs.push('gr.Textbox()');
      }
    }
  }

  return code;
};

forBlock['func_def'] = function (block, generator) {
  // Ensure the generator is properly initialized for nested blocks like loops
  if (!generator.nameDB_) {
    generator.nameDB_ = new Blockly.Names(generator.RESERVED_WORDS_ || []);
  }

  // Ensure getDistinctName is available for control flow blocks
  if (!generator.getDistinctName) {
    generator.getDistinctName = function (name, type) {
      return this.nameDB_.getDistinctName(name, type);
    };
  }

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
        case 'float':
          pyType = 'float';
          break;
        case 'string':
          pyType = 'str';
          break;
        case 'list':
          pyType = 'list';
          break;
        case 'boolean':
          pyType = 'bool';
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

      // Type-cast returns to ensure proper Gradio compatibility
      const outputType = block.outputTypes_[r] || 'string';
      if (outputType === 'integer' && returnValue) {
        returnValue = `int(${returnValue})`;
      } else if (outputType === 'float' && returnValue) {
        returnValue = `float(${returnValue})`;
      } else if (outputType === 'boolean' && returnValue) {
        returnValue = `bool(${returnValue})`;
      }

      returnValues.push(returnValue || 'None');
    }

    if (returnValues.length === 1) {
      returnStatement = `  return ${returnValues[0]}\n`;
    } else {
      returnStatement = `  return (${returnValues.join(', ')})\n`;
    }
  } else {
    // No outputs defined, return None
    returnStatement = '  return None\n';
  }

  // Construct the function definition
  let code;
  if (typedInputs.length > 0) {
    code = `def ${name}(${typedInputs.join(', ')}):\n${body}${returnStatement}`;
  } else {
    code = `def ${name}():\n${body}${returnStatement}`;
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
        case 'float':
          pyType = 'float';
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
    };
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

forBlock['func_call'] = function (block, generator) {
  // Prefer the serialized function name, fall back to the field if needed
  const funcName = block.currentFunction_ || block.getFieldValue('FUNC_NAME');

  if (!funcName || funcName === 'NONE') {
    return ['None', Order.ATOMIC];
  }

  // Find the function definition to get parameter info
  const workspace = block.workspace;
  const funcBlock = workspace.getAllBlocks(false).find(b =>
    b.type === 'func_def' && b.getFieldValue('NAME') === funcName
  );

  if (!funcBlock) {
    return ['None', Order.ATOMIC];
  }

  // Build the argument list based on actual inputs on the block
  const args = [];
  let i = 0;

  while (block.getInput('ARG' + i)) {
    const argValue = generator.valueToCode(block, 'ARG' + i, Order.NONE);
    args.push(argValue || 'None');
    i++;
  }

  const code = `${funcName}(${args.join(', ')})`;
  return [code, Order.FUNCTION_CALL];
};

forBlock['call_api'] = function (block, generator) {
  const url = generator.valueToCode(block, 'URL', Order.NONE) || "''";
  const method = block.getFieldValue('METHOD');
  const headers = generator.valueToCode(block, 'HEADERS', Order.NONE) || "''";

  // Generate code to call an LLM model with a prompt
  const code = `call_api(url=${url}, method="${method}", headers=${headers})`;
  return [code, Order.NONE];
};

forBlock['in_json'] = function (block, generator) {
  const name = generator.valueToCode(block, 'NAME', Order.NONE);
  const json = generator.valueToCode(block, 'JSON', Order.NONE);

  // Generate code to call an LLM model with a prompt
  const code = `${json}[${name}]`;
  return [code, Order.NONE];
};

forBlock['make_json'] = function (block, generator) {
  const pairs = [];
  let i = 0;

  // Collect all key-value pairs
  while (block.getInput('FIELD' + i)) {
    // Get the key from the text field on the block
    const keyField = block.getField('KEY' + i);
    const key = keyField ? keyField.getValue() : (block.fieldKeys_[i] || ('key' + i));
    const value = generator.valueToCode(block, 'FIELD' + i, Order.NONE) || "''";
    pairs.push(`"${key}": ${value}`);
    i++;
  }

  // Generate valid Python dict syntax
  const code = pairs.length > 0 ? `{${pairs.join(', ')}}` : '{}';
  return [code, Order.ATOMIC];
};

forBlock['lists_contains'] = function (block, generator) {
  const item = generator.valueToCode(block, 'ITEM', Order.NONE) || "''";
  const list = generator.valueToCode(block, 'LIST', Order.NONE) || "[]";

  // Generate code to check if item is in list
  const code = `${item} in ${list}`;
  return [code, Order.ATOMIC];
};

forBlock['cast_as'] = function (block, generator) {
  const value = generator.valueToCode(block, 'VALUE', Order.NONE) || "''";
  const type = block.getFieldValue('TYPE');

  // Generate code to cast value to the specified type
  const code = `${type}(${value})`;
  return [code, Order.FUNCTION_CALL];
};
