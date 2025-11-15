import { Order } from 'blockly/python';

export const forBlock = Object.create(null);

// Generates a Python function that runs when the user sends a message
forBlock['when_user_sends'] = function (block, generator) {
  const body = generator.statementToCode(block, 'CODE') || "";
  const code = `def on_user_send(user_message):\n${body}  return\n`;
  return code;
};

// Generates a Python 'return' statement for the assistant's reply
forBlock['assistant_reply'] = function (block, generator) {
  const reply = generator.valueToCode(block, 'INPUT', Order.NONE) || "''";
  const code = `reply(${reply})\n`;
  return code;
};

forBlock['get_assistant_response'] = function (block, generator) {
  const model = block.getFieldValue('MODEL');
  const prompt = generator.valueToCode(block, 'PROMPT', Order.NONE) || "''";
  const history = block.getFieldValue('HISTORY');

  const code = `get_assistant_response(${prompt}, model="${model}", use_history=${history})`;
  return [code, Order.NONE];
};

forBlock['user_message'] = function (block, generator) {
  const code = `user_message`;
  return [code, generator.ORDER_NONE];
};