import * as Blockly from 'blockly/core';

const whenUserSends = {
  type: 'when_user_sends',
  message0: 'when user sends %1 do %2 %3',
  args0: [
    {
      "type": "input_value",
      "name": "DUPLICATE"
    },
    {
      "type": "input_dummy"
    },
    {
      "type": "input_statement",
      "name": "CODE"
    }
  ],
  inputsInline: true,
  colour: 230,
  tooltip: 'Triggered when the user sends a chat message.',
  helpUrl: '',
};

const assistantReply = {
  type: 'assistant_reply',
  message0: 'reply with %1',
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

const getAssistantResponse = {
  type: 'get_assistant_response',
  message0: 'call model %1 with prompt %2 %3 history',
  args0: [
    {
      type: 'field_dropdown',
      name: 'MODEL',
      options: [
        ['gpt-3.5-turbo', 'gpt-3.5-turbo-0125'],
        ['gpt-5-mini', 'gpt-5-mini-2025-08-07'],
      ],
    },
    {
      type: 'input_value',
      name: 'PROMPT',
      check: 'String',
    },
    {
      type: 'field_dropdown',
      name: 'HISTORY',
      options: [
        ["with", "True"],
        ["without", "False"]
      ]
    },
  ],
  inputsInline: true,
  output: 'String',
  colour: 230,
  tooltip: 'Call the selected OpenAI model to get a response.',
  helpUrl: '',
};

const user_message = {
  type: "user_message",
  message0: "user message",
  output: "String",
  colour: "#47A8D1",
  tooltip: "",
  helpUrl: "",
};

export const blocks = Blockly.common.createBlockDefinitionsFromJsonArray([
  whenUserSends,
  assistantReply,
  getAssistantResponse,
  user_message
]);
