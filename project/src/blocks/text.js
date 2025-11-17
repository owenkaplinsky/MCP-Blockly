import * as Blockly from 'blockly/core';
import { pythonGenerator } from 'blockly/python';

// Utility to create a unique input reference block type
function createInputRefBlockType(inputName) {
  const blockType = `input_reference_${inputName}`;
  if (!Blockly.Blocks[blockType]) {
    Blockly.Blocks[blockType] = {
      init: function () {
        this.jsonInit({
          type: blockType,
          message0: "%1",
          args0: [
            {
              type: "field_label_serializable",
              name: "VARNAME",
              text: inputName
            }
          ],
          output: null,
          colour: 210,
          outputShape: 2
        });
      }
    };
    pythonGenerator.forBlock[blockType] = function () {
      return [inputName, pythonGenerator.ORDER_ATOMIC];
    };
  }
  return blockType;
}

// Global input reference tracking map
const inputRefs = new Map();

// Core mutator registration for dynamic tool and input creation
Blockly.Extensions.registerMutator(
  'test_mutator',
  {
    initialize: function () {
      if (!this.initialized_) {
        this.inputCount_ = 0;
        this.inputNames_ = [];
        this.inputTypes_ = [];
        this.inputRefBlocks_ = new Map();
        this.outputCount_ = 0;
        this.outputNames_ = [];
        this.outputTypes_ = [];
        this.initialized_ = true;
        // Mark all reference blocks with their owner for later identification
        this._ownerBlockId = this.id;
      }
    },

    decompose: function (workspace) {
      const containerBlock = workspace.newBlock('container');
      containerBlock.initSvg();
      let connection = containerBlock.getInput('STACK').connection;

      this.inputCount_ = this.inputCount_ || 0;
      this.inputNames_ = this.inputNames_ || [];
      this.inputTypes_ = this.inputTypes_ || [];
      this.outputCount_ = this.outputCount_ || 0;
      this.outputNames_ = this.outputNames_ || [];
      this.outputTypes_ = this.outputTypes_ || [];

      // Restore dynamically added input items
      for (let i = 0; i < this.inputCount_; i++) {
        const itemBlock = workspace.newBlock('container_input');
        itemBlock.initSvg();
        const typeVal = this.inputTypes_[i] || 'string';
        const nameVal = this.inputNames_[i] || typeVal;
        itemBlock.setFieldValue(typeVal, 'TYPE');
        itemBlock.setFieldValue(nameVal, 'NAME');

        const input = this.getInput('X' + i);
        if (input && input.connection && input.connection.targetConnection) {
          itemBlock.valueConnection_ = input.connection.targetConnection;
        }

        connection.connect(itemBlock.previousConnection);
        connection = itemBlock.nextConnection;
      }

      // Restore dynamically added output items
      let connection2 = containerBlock.getInput('STACK2').connection;
      for (let i = 0; i < this.outputCount_; i++) {
        const itemBlock = workspace.newBlock('container_output');
        itemBlock.initSvg();
        const typeVal = this.outputTypes_[i] || 'string';
        const nameVal = this.outputNames_[i] || typeVal;
        itemBlock.setFieldValue(typeVal, 'TYPE');
        itemBlock.setFieldValue(nameVal, 'NAME');

        connection2.connect(itemBlock.previousConnection);
        connection2 = itemBlock.nextConnection;
      }

      return containerBlock;
    },

    compose: function (containerBlock) {
      Blockly.Events.disable();
      try {
        if (!this.initialized_) this.initialize();

        const oldNames = [...(this.inputNames_ || [])];
        const oldOutputNames = [...(this.outputNames_ || [])];
        const connections = [];
        const returnConnections = [];
        let itemBlock = containerBlock.getInputTargetBlock('STACK');

        // Collect all child connections from mutator stack
        while (itemBlock) {
          connections.push(itemBlock.valueConnection_);
          itemBlock = itemBlock.nextConnection && itemBlock.nextConnection.targetBlock();
        }

        // Save existing return connections before removing them
        let rIdx = 0;
        while (this.getInput('R' + rIdx)) {
          const returnInput = this.getInput('R' + rIdx);
          if (returnInput && returnInput.connection && returnInput.connection.targetConnection) {
            returnConnections.push(returnInput.connection.targetConnection);
          } else {
            returnConnections.push(null);
          }
          rIdx++;
        }

        // Collect output specifications from STACK2
        const outputSpecs = [];
        let outputBlock = containerBlock.getInputTargetBlock('STACK2');
        while (outputBlock) {
          outputSpecs.push(outputBlock);
          outputBlock = outputBlock.nextConnection && outputBlock.nextConnection.targetBlock();
        }

        const newCount = connections.length;
        const newOutputCount = outputSpecs.length;
        this.inputCount_ = newCount;
        this.outputCount_ = newOutputCount;
        this.inputNames_ = this.inputNames_ || [];
        this.inputTypes_ = this.inputTypes_ || [];
        this.outputNames_ = this.outputNames_ || [];
        this.outputTypes_ = this.outputTypes_ || [];

        // Rebuild the new list of input names and types
        let idx = 0;
        let it = containerBlock.getInputTargetBlock('STACK');
        const newNames = [];
        while (it) {
          this.inputTypes_[idx] = it.getFieldValue('TYPE') || 'string';
          this.inputNames_[idx] = it.getFieldValue('NAME') || 'arg' + idx;
          newNames.push(this.inputNames_[idx]);
          it = it.nextConnection && it.nextConnection.targetBlock();
          idx++;
        }

        // Rebuild the new list of output names and types
        let oidx = 0;
        const newOutputNames = [];
        for (const outBlock of outputSpecs) {
          this.outputTypes_[oidx] = outBlock.getFieldValue('TYPE') || 'string';
          this.outputNames_[oidx] = outBlock.getFieldValue('NAME') || 'output' + oidx;
          newOutputNames.push(this.outputNames_[oidx]);
          oidx++;
        }

        // Dispose of removed input reference blocks when inputs shrink
        if (newCount < oldNames.length) {
          for (let i = newCount; i < oldNames.length; i++) {
            const oldName = oldNames[i];
            const block = this.inputRefBlocks_.get(oldName);
            if (block && !block.disposed) block.dispose(true);
            this.inputRefBlocks_.delete(oldName);
          }
        }

        // Rename reference blocks when variable names change
        // Only update reference blocks that belong to THIS block
        for (let i = 0; i < Math.min(oldNames.length, newNames.length); i++) {
          const oldName = oldNames[i];
          const newName = newNames[i];
          if (oldName !== newName) {
            const oldBlockType = `input_reference_${oldName}`;
            const newBlockType = `input_reference_${newName}`;

            if (this.inputRefBlocks_.has(oldName)) {
              const refBlock = this.inputRefBlocks_.get(oldName);
              if (refBlock && !refBlock.disposed) {
                this.inputRefBlocks_.delete(oldName);
                this.inputRefBlocks_.set(newName, refBlock);
                refBlock.setFieldValue(newName, 'VARNAME');
                // Properly update the block type in workspace tracking
                if (refBlock.workspace && refBlock.workspace.removeTypedBlock) {
                  refBlock.workspace.removeTypedBlock(refBlock);
                  refBlock.type = newBlockType;
                  refBlock.workspace.addTypedBlock(refBlock);
                } else {
                  refBlock.type = newBlockType;
                }
              }
            }

            // Update all clones of this reference block that share the same owner
            // (i.e., all clones that were created from the same parent block)
            const refBlock = this.inputRefBlocks_.get(newName);
            const ownerBlockId = this.id;

            if (refBlock && !refBlock.disposed) {
              const allBlocks = this.workspace.getAllBlocks(false);
              for (const block of allBlocks) {
                if (block.type === oldBlockType) {
                  // Update if this block has the same owner as our reference block
                  // This includes both connected and cloned blocks
                  if (block._ownerBlockId === ownerBlockId) {
                    // Properly update the block type in workspace tracking
                    if (block.workspace && block.workspace.removeTypedBlock) {
                      block.workspace.removeTypedBlock(block);
                      block.type = newBlockType;
                      block.workspace.addTypedBlock(block);
                    } else {
                      block.type = newBlockType;
                    }
                    block.setFieldValue(newName, 'VARNAME');
                  }
                }
              }
            }

            pythonGenerator.forBlock[newBlockType] = function () {
              return [newName, pythonGenerator.ORDER_ATOMIC];
            };
          }
        }

        // Remove all dynamic and temporary inputs before reconstruction
        let i = 0;
        while (this.getInput('X' + i)) this.removeInput('X' + i++);
        let r = 0;
        while (this.getInput('R' + r)) this.removeInput('R' + r++);
        let t = 0;
        while (this.getInput('T' + t)) this.removeInput('T' + t++);
        ['INPUTS_TEXT', 'RETURNS_TEXT', 'TOOLS_TEXT'].forEach(name => {
          if (this.getInput(name)) this.removeInput(name);
        });

        if (newCount > 0) {
          const inputsText = this.appendDummyInput('INPUTS_TEXT');
          inputsText.appendField('with inputs:');
          this.moveInputBefore('INPUTS_TEXT', 'BODY');
        }

        // Add each dynamic input, reconnecting to reference blocks
        for (let j = 0; j < newCount; j++) {
          const type = this.inputTypes_[j] || 'string';
          const name = this.inputNames_[j] || type;
          let check = null;
          if (type === 'integer') check = 'Number';
          if (type === 'string') check = 'String';

          const existingRefBlock = this.inputRefBlocks_.get(name);
          const input = this.appendValueInput('X' + j);
          if (check) input.setCheck(check);
          input.appendField(type);
          this.moveInputBefore('X' + j, 'BODY');

          const blockType = createInputRefBlockType(name);
          if (!existingRefBlock) {
            const refBlock = this.workspace.newBlock(blockType);
            refBlock.initSvg();
            refBlock.setDeletable(false);
            refBlock.render();
            // Mark the reference block with its owner
            refBlock._ownerBlockId = this.id;
            this.inputRefBlocks_.set(name, refBlock);
            if (input.connection && refBlock.outputConnection) {
              input.connection.connect(refBlock.outputConnection);
            }
          } else if (input.connection && existingRefBlock.outputConnection) {
            input.connection.connect(existingRefBlock.outputConnection);
          }

          pythonGenerator.forBlock[blockType] = function () {
            return [name, pythonGenerator.ORDER_ATOMIC];
          };
        }

        // Reconnect preserved connections to new structure
        for (let k = 0; k < newCount; k++) {
          const conn = connections[k];
          if (conn) {
            try {
              conn.connect(this.getInput('X' + k).connection);
            } catch { }
          }
        }

        // Handle return inputs based on outputs
        if (newOutputCount > 0) {
          // Remove the default RETURN input if it exists
          if (this.getInput('RETURN')) {
            this.removeInput('RETURN');
          }

          // Add the "and return" label
          const returnsText = this.appendDummyInput('RETURNS_TEXT');
          returnsText.appendField('and return');

          // Add each return value input slot
          for (let j = 0; j < newOutputCount; j++) {
            const type = this.outputTypes_[j] || 'string';
            const name = this.outputNames_[j] || ('output' + j);
            let check = null;
            if (type === 'integer') check = 'Number';
            if (type === 'string') check = 'String';

            const returnInput = this.appendValueInput('R' + j);
            if (check) returnInput.setCheck(check);
            returnInput.appendField(type);
            returnInput.appendField('"' + name + '":');

            // Reconnect previous connection if it exists
            if (returnConnections[j]) {
              try {
                returnInput.connection.connect(returnConnections[j]);
              } catch { }
            }
          }
        }

        this.workspace.render();
      } finally {
        Blockly.Events.enable();
      }
    },

    saveExtraState: function () {
      return {
        inputCount: this.inputCount_,
        inputNames: this.inputNames_,
        inputTypes: this.inputTypes_,
        outputCount: this.outputCount_,
        outputNames: this.outputNames_,
        outputTypes: this.outputTypes_,
        toolCount: this.toolCount_ || 0
      };
    },

    loadExtraState: function (state) {
      this.inputCount_ = state.inputCount;
      this.inputNames_ = state.inputNames || [];
      this.inputTypes_ = state.inputTypes || [];
      this.outputCount_ = state.outputCount || 0;
      this.outputNames_ = state.outputNames || [];
      this.outputTypes_ = state.outputTypes || [];
      this.toolCount_ = state.toolCount || 0;
    }
  },
  null,
  ['container_input']
);

// Base block definitions
const container = {
  type: "container",
  message0: "inputs %1 %2 outputs %3 %4",
  args0: [
    { type: "input_dummy", name: "title" },
    { type: "input_statement", name: "STACK" },
    { type: "input_dummy", name: "title2" },
    { type: "input_statement", name: "STACK2" },
  ],
  colour: 160,
  inputsInline: false
};

const container_input = {
  type: "container_input",
  message0: "%1 %2",
  args0: [
    {
      type: "field_dropdown",
      name: "TYPE",
      options: [
        ["String", "string"],
        ["Integer", "integer"],
        ["List", "list"],
      ]
    },
    { type: "field_input", name: "NAME" },
  ],
  previousStatement: null,
  nextStatement: null,
  colour: 210,
};

const container_output = {
  type: "container_output",
  message0: "%1 %2",
  args0: [
    {
      type: "field_dropdown",
      name: "TYPE",
      options: [
        ["String", "string"],
        ["Integer", "integer"],
        ["List", "list"],
      ]
    },
    { type: "field_input", name: "NAME" },
  ],
  previousStatement: null,
  nextStatement: null,
  colour: 210,
};

const llm_call = {
  type: "llm_call",
  message0: "call model %1 with prompt %2",
  args0: [
    {
      type: "field_dropdown",
      name: "MODEL",
      options: [
        ["gpt-3.5-turbo", "gpt-3.5-turbo-0125"],
        ["gpt-5-mini", "gpt-5-mini-2025-08-07"],
      ]
    },
    { type: "input_value", name: "PROMPT", check: "String" },
  ],
  inputsInline: true,
  output: "String",
  colour: 230,
  tooltip: "Call the selected OpenAI model to get a response.",
  helpUrl: "",
};

const create_mcp = {
  type: "create_mcp",
  message0: "create MCP %1 %2",
  args0: [
    { type: "input_dummy" },
    { type: "input_statement", name: "BODY" },
  ],
  colour: 160,
  inputsInline: true,
  mutator: "test_mutator",
  inputCount_: 0,
  deletable: false,
  extensions: ["test_cleanup_extension"]
};

const tool_def = {
  type: "tool_def",
  message0: "function %1 %2 %3",
  args0: [
    { type: "field_input", name: "NAME", text: "newFunction" },
    { type: "input_dummy" },
    { type: "input_statement", name: "BODY" },
  ],
  colour: 160,
  inputsInline: true,
  mutator: "test_mutator",
  inputCount_: 0,
  deletable: true,
  extensions: ["test_cleanup_extension"]
};

// Cleanup extension ensures that dynamic reference blocks are deleted when parent is
Blockly.Extensions.register('test_cleanup_extension', function () {
  const oldDispose = this.dispose;
  this.dispose = function (healStack, recursive) {
    if (this.inputRefBlocks_) {
      for (const [, refBlock] of this.inputRefBlocks_) {
        if (refBlock && !refBlock.disposed) refBlock.dispose(false);
      }
      this.inputRefBlocks_.clear();
    }
    if (oldDispose) oldDispose.call(this, healStack, recursive);
  };
});

// Function to generate a unique tool name
function generateUniqueToolName(workspace, excludeBlock) {
  const existingNames = new Set();
  const allBlocks = workspace.getAllBlocks(false);

  // Collect all existing tool names, excluding the block being created
  for (const block of allBlocks) {
    if (block.type === 'tool_def' && block !== excludeBlock && block.getFieldValue('NAME')) {
      existingNames.add(block.getFieldValue('NAME'));
    }
  }

  // Generate a unique name
  let baseName = 'newTool';
  let name = baseName;
  let counter = 1;

  while (existingNames.has(name)) {
    counter++;
    name = `${baseName}${counter}`;
  }

  return name;
}

// Register create_mcp block separately to include custom init logic  
Blockly.Blocks['create_mcp'] = {
  init: function () {
    this.jsonInit(create_mcp);
    // Apply extensions
    Blockly.Extensions.apply('test_cleanup_extension', this, false);
    // Initialize mutator state
    if (this.initialize) {
      this.initialize();
    }
  }
};

// Register tool_def block separately to include custom init logic
Blockly.Blocks['tool_def'] = {
  init: function () {
    this.jsonInit(tool_def);
    // Apply extensions
    Blockly.Extensions.apply('test_cleanup_extension', this, false);
    // Initialize mutator state
    if (this.initialize) {
      this.initialize();
    }
  }
};

export const blocks = Blockly.common.createBlockDefinitionsFromJsonArray([
  container,
  container_input,
  container_output,
  llm_call,
]);
