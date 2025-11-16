import { Order } from 'blockly/python';

export const forBlock = Object.create(null);

forBlock['create_mcp'] = function (block, generator) {
  // Get all inputs with their types
  const typedInputs = [];
  let i = 0;
  while (block.getInput('X' + i)) {
    const input = block.getInput('X' + i);
    if (input && input.connection && input.connection.targetBlock()) {
      // Get the actual parameter name from inputNames_ array
      const paramName = (block.inputNames_ && block.inputNames_[i]) || ('arg' + i);
      // Get the type from inputTypes_ array
      const type = (block.inputTypes_ && block.inputTypes_[i]) || 'string';
      // Convert type to Python type annotation
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

  // Get the code for blocks inside the BODY statement input
  let body = generator.statementToCode(block, 'BODY');

  // Get the return value if any
  let returnValue = generator.valueToCode(block, 'RETURN', Order.ATOMIC);

  // Replace arg references with actual parameter names
  if (returnValue && block.inputNames_) {
    for (let j = 0; j < block.inputNames_.length; j++) {
      const paramName = block.inputNames_[j];
      returnValue = returnValue.replace(new RegExp(`arg${j}\\b`, 'g'), paramName);
    }
  }

  let returnStatement = returnValue ? `  return ${returnValue}\n` : '  return\n';

  // Create the function with all typed inputs
  if (typedInputs.length > 0) {
    const code = `def create_mcp(${typedInputs.join(', ')}):\n${body}${returnStatement}\n`;
    return code;
  } else {
    return `def create_mcp():\n${body}${returnStatement}`;
  }
};