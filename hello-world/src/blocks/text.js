/**
 * @license
 * Copyright 2023 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

import * as Blockly from 'blockly/core';

const whenUserSends = {
  type: 'when_user_sends',
  message0: 'When user sends msg do %1 %2',
  args0: [
    {
      "type": "input_dummy"
    },
    {
      "type": "input_statement",
      "name": "code"
    }
  ],
  inputsInline: true,
  colour: 230,
  tooltip: 'Triggered when the user sends a chat message.',
  helpUrl: '',
};

const assistantReply = {
  type: 'assistant_reply',
  message0: 'Reply with %1',
  args0: [
    {
      type: 'input_value',
      name: 'INPUT',
      check: 'String',
    },
  ],
  previousStatement: null,
  nextStatement: null,
  colour: 65,
  tooltip: 'Send a message as the assistant.',
  helpUrl: '',
};

export const blocks = Blockly.common.createBlockDefinitionsFromJsonArray([
  whenUserSends,
  assistantReply,
]);
