import * as Blockly from 'blockly/core';
import { pythonGenerator } from 'blockly/python';

// Function to create a unique block type for an input
function createInputRefBlockType(inputName) {
  const blockType = `input_reference_${inputName}`;

  // Only create if not already defined
  if (!Blockly.Blocks[blockType]) {
    // Define block
    Blockly.Blocks[blockType] = {
      init: function () {
        this.jsonInit({
          "type": blockType,
          "message0": "%1",
          "args0": [
            {
              "type": "field_label_serializable",
              "name": "VARNAME",
              "text": inputName
            }
          ],
          "output": null,
          "colour": 210,
          "outputShape": 1  // Oval shape (1 = round)
        });
      }
    };

    // Define Python generator for this block type
    pythonGenerator.forBlock[blockType] = function (block) {
      // Just return the input name as a variable reference
      return [inputName, pythonGenerator.ORDER_ATOMIC];
    };
  }
  return blockType;
}

// Keep track of input reference blocks
const inputRefs = new Map();  // Maps input name to block ID

Blockly.Extensions.registerMutator(
  'test_mutator',
  {
    // Initialize tracking of input reference blocks
    initialize: function () {
      if (!this.initialized_) {
        this.inputCount_ = 0;
        this.inputNames_ = [];
        this.inputTypes_ = [];
        this.inputRefBlocks_ = new Map();  // Maps input name to block reference
        this.initialized_ = true;
      }
    },

    decompose: function (workspace) {
      var containerBlock = workspace.newBlock('container');
      containerBlock.initSvg();
      var connection = containerBlock.getInput('STACK').connection;

      // Ensure inputCount_ is defined
      this.inputCount_ = this.inputCount_ || 0;
      this.inputNames_ = this.inputNames_ || [];
      this.inputTypes_ = this.inputTypes_ || [];

      // Dynamically add input blocks based on inputCount_
      for (var i = 0; i < this.inputCount_; i++) {
        var itemBlock = workspace.newBlock('container_input');
        itemBlock.initSvg();

        var typeVal = this.inputTypes_[i] || 'string';
        var nameVal = this.inputNames_[i] || typeVal;
        itemBlock.setFieldValue(typeVal, 'TYPE');  // Set data type
        itemBlock.setFieldValue(nameVal, 'NAME');  // Set name from stored name

        // Preserve any existing connection from this block's input
        var input = this.getInput('X' + i);
        if (input && input.connection && input.connection.targetConnection) {
          itemBlock.valueConnection_ = input.connection.targetConnection;
        }

        connection.connect(itemBlock.previousConnection);
        connection = itemBlock.nextConnection;
      }

      return containerBlock;
    },

    compose: function (containerBlock) {
      // Disable events during mutator updates to prevent duplication
      Blockly.Events.disable();

      try {
        // Ensure initialization
        if (!this.initialized_) {
          this.initialize();
        }

        var itemBlock = containerBlock.getInputTargetBlock('STACK');
        var connections = [];
        var oldNames = this.inputNames_ ? [...this.inputNames_] : [];  // Copy old names for cleanup

        // Collect input connections
        while (itemBlock) {
          connections.push(itemBlock.valueConnection_);
          itemBlock = itemBlock.nextConnection && itemBlock.nextConnection.targetBlock();
        }

        var newCount = connections.length;
        this.inputCount_ = newCount;
        this.inputNames_ = this.inputNames_ || [];
        this.inputTypes_ = this.inputTypes_ || [];

        var idx = 0;
        var it = containerBlock.getInputTargetBlock('STACK');
        var newNames = [];
        while (it) {
          this.inputTypes_[idx] = it.getFieldValue('TYPE') || 'string';
          this.inputNames_[idx] = it.getFieldValue('NAME') || ('arg' + idx);
          newNames.push(this.inputNames_[idx]);
          it = it.nextConnection && it.nextConnection.targetBlock();
          idx++;
        }

        // Clean up removed input reference blocks only if count decreased
        if (newCount < oldNames.length) {
          // Only remove blocks for inputs that were deleted (beyond new count)
          for (let i = newCount; i < oldNames.length; i++) {
            const oldName = oldNames[i];
            const block = this.inputRefBlocks_.get(oldName);
            if (block && !block.disposed) {
              block.dispose(true);  // true = skip gap
            }
            this.inputRefBlocks_.delete(oldName);
          }
        }

        // Handle renamed variables - update ALL instances (main block + clones)
        for (let i = 0; i < Math.min(oldNames.length, newNames.length); i++) {
          const oldName = oldNames[i];
          const newName = newNames[i];
          if (oldName !== newName) {
            const oldBlockType = `input_reference_${oldName}`;
            const newBlockType = `input_reference_${newName}`;

            // Update the reference block in the MCP block
            if (this.inputRefBlocks_.has(oldName)) {
              const refBlock = this.inputRefBlocks_.get(oldName);
              if (refBlock && !refBlock.disposed) {
                this.inputRefBlocks_.delete(oldName);
                this.inputRefBlocks_.set(newName, refBlock);
                refBlock.setFieldValue(newName, 'VARNAME');
                refBlock.type = newBlockType;  // Update the block type
              }
            }

            // Find and update ALL clones of this reference block in the workspace
            const workspace = this.workspace;
            const allBlocks = workspace.getAllBlocks(false);
            for (const block of allBlocks) {
              if (block.type === oldBlockType && block !== this.inputRefBlocks_.get(newName)) {
                // This is a clone - update it too
                block.type = newBlockType;
                block.setFieldValue(newName, 'VARNAME');
              }
            }

            // Update the Python generator for the new block type
            pythonGenerator.forBlock[newBlockType] = function (block) {
              return [newName, pythonGenerator.ORDER_ATOMIC];
            };
          }
        }

        // Remove only the dynamic inputs (X0, X1, etc.)
        var i = 0;
        while (this.getInput('X' + i)) {
          this.removeInput('X' + i);
          i++;
        }

        // Now add dynamic inputs at the correct position
        for (var j = 0; j < newCount; j++) {
          var type = this.inputTypes_[j] || 'string';
          var name = this.inputNames_[j] || type;
          var check = null;
          if (type === 'integer') check = 'Number';
          if (type === 'string') check = 'String';
          // For list, leave check as null (no restriction)

          // Get existing reference block if any
          const existingRefBlock = this.inputRefBlocks_.get(name);

          // Insert inputs at the beginning (after the static text)
          var input = this.appendValueInput('X' + j);
          if (check) input.setCheck(check);
          input.appendField(type);  // Display the type instead of the name

          // Move the input to the correct position (after dummy inputs, before BODY)
          this.moveInputBefore('X' + j, 'BODY');

          // Create or reuse reference block
          const blockType = createInputRefBlockType(name);
          if (!existingRefBlock) {
            // Create new reference block
            const workspace = this.workspace;
            const refBlock = workspace.newBlock(blockType);
            refBlock.initSvg();
            refBlock.setDeletable(false);  // Can't be deleted directly
            refBlock.render();
            this.inputRefBlocks_.set(name, refBlock);

            // Connect new block
            if (input && input.connection && refBlock.outputConnection) {
              input.connection.connect(refBlock.outputConnection);
            }
          } else {
            // Reuse existing block - connect it to new input
            if (input && input.connection && existingRefBlock.outputConnection) {
              input.connection.connect(existingRefBlock.outputConnection);
            }

            // Update the Python generator for renamed variables
            pythonGenerator.forBlock[blockType] = function (block) {
              return [name, pythonGenerator.ORDER_ATOMIC];
            };
          }
        }

        // Reconnect preserved connections
        for (var k = 0; k < newCount; k++) {
          var conn = connections[k];
          if (conn) {
            try {
              conn.connect(this.getInput('X' + k).connection);
            } catch (e) {
              // ignore failed reconnects
            }
          }
        }

        // Force workspace to update
        this.workspace.render();

      } finally {
        // Re-enable events
        Blockly.Events.enable();
      }
    },

    saveExtraState: function () {
      const state = {
        inputCount: this.inputCount_,
        inputNames: this.inputNames_,
        inputTypes: this.inputTypes_
      };
      return state;
    },

    loadExtraState: function (state) {
      this.inputCount_ = state['inputCount'];
      this.inputNames_ = state['inputNames'] || [];
      this.inputTypes_ = state['inputTypes'] || [];
    }
  },
  null,  // No helper function needed
  ['container_input']
);

// Define the test block with mutator
const create_mcp = {
  "type": "create_mcp",
  "message0": "create MCP with inputs: %1 %2 and return %3",
  "args0": [
    {
      "type": "input_dummy"
    },
    {
      "type": "input_statement",
      "name": "BODY"
    },
    {
      "type": "input_value",
      "name": "RETURN",
    },
  ],
  "colour": 160,
  "inputsInline": true,
  "mutator": "test_mutator",
  "inputCount_": 0,  // Start with no inputs
  "deletable": false,  // Make the block non-deletable

  // Override the dispose function to clean up reference blocks
  "extensions": ["test_cleanup_extension"]
};

// Define the container block for the mutator
const container = {
  "type": "container",
  "message0": "inputs %1 %2",
  "args0": [
    {
      "type": "input_dummy",
      "name": "title"
    },
    {
      "type": "input_statement",
      "name": "STACK"
    }
  ],
  "colour": 160,
  "inputsInline": false
}


// Define the input block for the mutator
const container_input = {
  type: 'container_input',
  message0: '%1 %2',
  args0: [
    {
      type: 'field_dropdown',
      name: 'TYPE',
      options: [
        ["String", "string"],
        ["Integer", "integer"],
        ["List", "list"],
      ]
    },
    {
      type: 'field_input',
      name: 'NAME',
    },
  ],
  previousStatement: null,
  nextStatement: null,
  colour: 210,
};

// Register an extension to handle cleanup when the block is deleted
Blockly.Extensions.register('test_cleanup_extension', function () {
  // Store the original dispose function
  const oldDispose = this.dispose;

  // Override the dispose function
  this.dispose = function (healStack, recursive) {
    // Clean up all reference blocks first
    if (this.inputRefBlocks_) {
      for (const [name, refBlock] of this.inputRefBlocks_) {
        if (refBlock && !refBlock.disposed) {
          refBlock.dispose(false);  // Don't heal stack for reference blocks
        }
      }
      this.inputRefBlocks_.clear();
    }

    // Call the original dispose function
    if (oldDispose) {
      oldDispose.call(this, healStack, recursive);
    }
  };
});

// Create block definitions from the JSON
export const blocks = Blockly.common.createBlockDefinitionsFromJsonArray([
  create_mcp,
  container,
  container_input,
]);
