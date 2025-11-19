# Agent-Blockly

Agent-Blockly is a visual programming environment for building AI tools. Instead of writing Python code, you arrange blocks in a visual editor and the system generates code for you. You can test your tool immediately and download it when you're ready.

## What This Does

Agent-Blockly lets you build Model Context Protocol (MCP) servers using a block-based interface. You define what inputs your tool needs, add blocks that perform operations (calling APIs, parsing data, executing language models), and specify what your tool outputs. The system generates Python code from your block arrangement and provides a testing interface to verify your work.

The interface has three main areas. The canvas on the left is where you build by dragging and connecting blocks. On the right are two tabs for working with your project: the Development tab for testing, and an AI Chat tab.

In the Development tab, you see your generated Python code alongside a test interface. The interface automatically creates input fields matching your tool's parameters. After you arrange your blocks, click Refresh to update the test interface, enter values, and click Submit to run your code. Results appear in the output fields.

The AI Chat tab lets you build and refine your project through conversation. It understands your workspace and can turn natural instructions into real changes inside the editor.

The assistant can:
- Create new blocks from plain language. Describe what you want to add, and it builds the correct structure automatically.  
- Delete or replace existing blocks without disrupting the rest of your layout.  
- Create and name variables that become immediately usable in your workspace.  
- Run your MCP tool with real inputs and show the actual outputs for testing.  
- Build nested block structures, such as inserting expressions or operations inside other blocks.  
- Perform multi-step changes and executions, refining your setup one step at a time.  

It works live and responds quickly, keeping your workspace synchronized with every instruction. Larger changes are best made in smaller steps, allowing for smooth and accurate updates.

While it can handle a wide range of tasks, multi-step or highly complex changes work best when broken into smaller requests. Taking things one step at a time leads to more accurate and reliable results.

The File menu handles creating new projects, opening existing ones, and downloading your work. You can download just the generated Python code or the entire project as a JSON file. The Edit menu provides standard undo, redo, and a cleanup button to reorganize blocks. The Examples menu includes pre-built projects you can load to understand how to structure your own. You need to set your OpenAI API key through Settings before the system can execute language model calls or power the chat.

The toolbox contains blocks for common operations: calling language models, making HTTP requests, extracting data from JSON, manipulating text, performing math, and working with lists. You connect these blocks to build your workflow.

## Installation

Clone the repository and install dependencies.

```bash
git clone https://github.com/owenkaplinsky/agent-blockly.git
cd agent-blockly/project
pip install -r ../requirements.txt
npm install
```

## Running Locally

Start the application with:

```bash
npm start
```

Open your browser and navigate to http://127.0.0.1:8080 to begin building.

## How It Works

The system has three main components: the frontend Blockly editor, the backend Python services, and the AI Chat engine.

When you arrange blocks in the editor, change listeners trigger code generation. The JavaScript generator traverses your block tree and outputs Python code that represents your workflow. Each block type has a corresponding generator function that knows how to output Python for that block. These functions compose recursively, building the complete function definition from your block arrangement. The generated code is sent to the backend via HTTP POST and stored in memory.

Blocks dynamically manage their input and output ports through Blockly's mutator system. When you modify a block to add or remove parameters, the mutator updates both the visual shape and the internal state that tracks how many inputs and outputs exist. Each input and output has metadata about its name and type. When a user defines inputs on their main function block, the system creates invisible reference blocks for each input parameter. These reference blocks appear as connectable outputs that other blocks can use. During code generation, these references translate to variable names in the Python function signature and body.

Code execution happens in a sandboxed Python environment. User code is executed with restricted builtins and a clean state for each run. The system captures return values and displays them in the test interface.

The AI Chat component is the sophisticated heart of the system. It continuously monitors the current workspace state and code. When you send a message, the system formats your entire block structure into a readable representation and includes it in the context sent to OpenAI. The model receives not just your question but a complete understanding of what you've built. The system includes a detailed system prompt that explains MCP concepts, the block syntax, and what actions the model can perform.

Based on the model's response, the system recognizes three special commands: run to execute your MCP with sample inputs, delete to remove a block by ID, and create to add new blocks to your workspace. When the model issues these commands, they're executed immediately. For block modifications, the system uses Server-Sent Events to stream commands back to the frontend, which creates or deletes blocks in real time while you watch. This maintains real-time synchronization between the chat interface and the visual editor.

The AI Chat can execute multiple actions per conversation turn. If the model decides it needs to run your code to see the result before suggesting improvements, it does that automatically. If it needs to delete a broken block and create a replacement, it performs both operations and then reports back with what happened. This looping continues for up to five consecutive iterations per user message, allowing the AI to progressively refine your blocks without requiring you to send multiple messages.

API keys are managed through environment variables set at runtime. The system uses Gradio to automatically generate user interfaces based on the function signatures in your generated code, creating input and output fields that match your tool's parameters.
