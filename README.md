# MCP Blockly

MCP Blockly is a visual programming environment for building real MCP servers without dealing with Python syntax or configuration. It brings the clarity of block-based logic into AI development, allowing newcomers and experienced builders alike to design, test, and refine MCP tools through a clean drag-and-connect workflow. Every block you place generates runnable Python code instantly, so you can focus on structure and behavior while the system manages the boilerplate.

## What This Does

MCP Blockly lets you build Model Context Protocol (MCP) servers using a block-based interface, perfect for students and newcomers stepping into AI development. The core building happens on the visual canvas. You define your MCP inputs, arrange your logic with blocks, and choose what your server will return. Every change you make is reflected in live Python code on the side. The generator handles function signatures and MCP boilerplate automatically, so you never have to worry about syntax or configuration. Everything stays valid and synchronized.

The interface has three main areas. The canvas on the left is where you build by dragging and connecting blocks. On the right are two tabs for working with your project: the Testing tab, and an AI Assistant tab.

Once your blocks are in place, the Development panel makes testing simple. It automatically generates input fields based on your parameters, so you can run the MCP server logic instantly. You enter values, submit, and see the outputs appear. This kind of immediate feedback helps learners understand how data flows through their tool and builds intuition about how AI tools work.

The AI Assistant tab lets you build and refine your project through conversation. It understands your workspace and becomes a natural part of how you learn and explore the MCP ecosystem.

The assistant can:
- Create new blocks from plain language. Describe what you want to accomplish, and it builds the correct structure automatically.  
- Delete or replace existing blocks without disrupting the rest of your layout.  
- Create and name variables that become immediately usable in your workspace.  
- Run your MCP tool with real inputs and show the actual outputs for testing.  
- Build nested block structures, such as inserting expressions or operations inside other blocks.  
- Explain concepts and guide you step by step through the creation process.  
- Perform multi-step changes and executions, refining your setup one step at a time.  

It works live and responds quickly, keeping your workspace synchronized with every instruction. This combination of hands-on building with conversational guidance bridges the gap between visual coding and real AI workflows. Taking things one step at a time leads to more accurate and reliable results as you learn.

The File menu handles creating new projects, opening existing ones, and downloading your work. You can download just the generated Python code or the entire project as a JSON file. The Edit menu provides standard undo, redo, and a cleanup button to reorganize blocks. The Examples menu includes pre-built projects you can load to understand how to structure your own.

### API Keys

The system has two optional but recommended API keys:

**OpenAI API Key**: Enables the AI Assistant: your guide through the learning process. The assistant helps you build blocks, fix mistakes, explain concepts, and explore MCP development interactively. Without it, you can still create and test blocks manually.

**Hugging Face API Key**: Allows you to deploy your MCP as a real, live server on Hugging Face Spaces. This is a practical way to learn how AI tools work in production. The system creates a new Space and uploads your tool automatically. The Space becomes a real MCP server that other AI systems can connect to and call natively. Without it, you can build and test locally but won't be able to deploy unless you manually create a space and upload the generated `app.py` file.

Set these keys through Settings before using features that depend on them. Both are optional: you can build and test tools without either key, but certain features won't be available.

The toolbox contains blocks for common operations: calling language models, making HTTP requests, extracting data from JSON, manipulating text, performing math, and working with lists. You connect these blocks to build your workflow.

## Installation

Clone the repository and install dependencies.

```bash
git clone https://github.com/owenkaplinsky/mcp-blockly.git
cd mcp-blockly/project
pip install -r ../requirements.txt
npm install
```

## Running Locally

Start the application with:

```bash
npm start
```

After that, it will open a tab in your browser and you can start building!

## How It Works

The system has three main components: the frontend Blockly editor, the backend Python services, and the AI Assistant engine.

When you arrange blocks in the editor, change listeners trigger code generation. The JavaScript generator traverses your block tree and outputs Python code that represents your workflow. Each block type has a corresponding generator function that knows how to output Python for that block. These functions compose recursively, building the complete function definition from your block arrangement. The generated code is sent to the backend via HTTP POST and stored in memory.

Blocks dynamically manage their input and output ports through Blockly's mutator system. When you modify a block to add or remove parameters, the mutator updates both the visual shape and the internal state that tracks how many inputs and outputs exist. Each input and output has metadata about its name and type. When a user defines inputs on their main function block, the system creates invisible reference blocks for each input parameter. These reference blocks appear as connectable outputs that other blocks can use. During code generation, these references translate to variable names in the Python function signature and body.

The AI Assistant component is the sophisticated heart of the system. It continuously monitors the current workspace state and code. When you send a message, the system formats your entire block structure into a readable representation and includes it in the context sent to OpenAI. The model receives not just your question but a complete understanding of what you've built. The system includes a detailed system prompt that explains MCP concepts, the block syntax, and what actions the model can perform.

Based on the model's response, the system recognizes four special commands: run to execute your MCP with sample inputs, delete to remove a block by ID, create to add new blocks to your workspace, and deploy_to_huggingface to publish your tool as a live server. When the model issues these commands, they're executed immediately. For block modifications, the system uses Server-Sent Events to stream commands back to the frontend, which creates or deletes blocks in real time while you watch. This maintains real-time synchronization between the chat interface and the visual editor.

The AI Assistant can execute multiple actions per conversation turn. If the model decides it needs to run your code to see the result before suggesting improvements, it does that automatically. If it needs to delete a broken block and create a replacement, it performs both operations and then reports back with what happened. This looping continues for up to ten consecutive iterations per user message, allowing the AI to progressively refine your blocks without requiring you to send multiple messages.

When you're ready to share your MCP tool, you can deploy it directly to Hugging Face Spaces. Once deployed, the tool becomes a real MCP server that can be called by any AI system supporting the MCP protocol. The AI Assistant in MCP Blockly can immediately use your deployed tool—just ask it to call your MCP and it will invoke the actual live server.

The agent also monitors your Space's build status. Build typically takes 1-2 minutes. Once the Space reaches RUNNING status, all the tools you defined in your blocks become available for the AI to call natively. If you send a message while the Space is still building, the AI will let you know to wait a moment before your MCP tools become available.

API keys are managed through environment variables set at runtime. The system uses Gradio to automatically generate user interfaces based on the function signatures in your generated code, creating input and output fields that match your tool's parameters.
