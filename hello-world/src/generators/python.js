import { Order } from 'blockly/python';

export const forBlock = Object.create(null);

// Generates a Python function that runs when the user sends a message
forBlock['when_user_sends'] = function (block, generator) {
  const body = generator.statementToCode(block, 'code') || "";
  const code = `def on_user_send(user_message):\n${body}\n`;
  return code;
};

// Generates a Python 'return' statement for the assistant's reply
forBlock['assistant_reply'] = function (block, generator) {
  const reply = generator.valueToCode(block, 'INPUT', Order.NONE) || "''";
  const code = `return ${reply}\n`;
  return code;
};
