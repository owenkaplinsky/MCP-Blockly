import os
import re
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
import uvicorn
import gradio as gr
import asyncio
import queue
import json

# Initialize OpenAI client (will be updated when API key is set)
client = None

# Store API key in memory for this process
stored_api_key = ""

# Global variable to store the latest chat context
latest_blockly_chat_code = ""

# Queue for deletion requests and results storage
deletion_queue = queue.Queue()
deletion_results = {}

# Queue for creation requests and results storage
creation_queue = queue.Queue()
creation_results = {}

blocks_context = ""
try:
    file_path = os.path.join(os.path.dirname(__file__), "blocks.txt")
    with open(file_path, "r", encoding="utf-8") as f:
        blocks_context = f.read().strip()
except Exception as e:
    print(f"[WARN] Could not read blocks.txt: {e}")
    blocks_context = "(No external block data available.)"

# FastAPI App
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/update_chat")
async def update_chat(request: Request):
    global latest_blockly_chat_code
    data = await request.json()
    latest_blockly_chat_code = data.get("code", "")
    print("\n[FASTAPI] Updated Blockly chat code:\n", latest_blockly_chat_code)
    return {"code": latest_blockly_chat_code}

@app.post("/set_api_key_chat")
async def set_api_key_chat(request: Request):
    """Receive API key from frontend and store it"""
    global stored_api_key
    data = await request.json()
    api_key = data.get("api_key", "").strip()
    
    # Store in memory and set environment variable for this process
    stored_api_key = api_key
    os.environ["OPENAI_API_KEY"] = api_key
    
    print(f"[CHAT API KEY] Set OPENAI_API_KEY in chat.py environment")
    return {"success": True}

def execute_mcp(mcp_call):
    """Execute MCP call using the actual Python function from test.py"""
    global stored_api_key, latest_blockly_chat_code

    if stored_api_key:
        os.environ["OPENAI_API_KEY"] = stored_api_key

    try:
        # Now, retrieve the real generated Python code from test.py
        blockly_code = ""
        try:
            resp = requests.get("http://localhost:7860/get_latest_code")
            if resp.ok:
                blockly_code = resp.json().get("code", "")
        except Exception as e:
            print(f"[WARN] Could not fetch real Python code: {e}")

        if not blockly_code.strip():
            return "No Python code available from test.py"

        # Parse the MCP call arguments
        match = re.match(r'create_mcp\((.*)\)', mcp_call.strip())
        if not match:
            return "Invalid MCP call format"

        params_str = match.group(1)
        user_inputs = []

        if params_str:
            import ast
            try:
                dict_str = "{" + params_str.replace("=", ":") + "}"
                param_dict = ast.literal_eval(dict_str)
                user_inputs = [str(v) for v in param_dict.values()]
            except Exception:
                for pair in params_str.split(','):
                    if '=' in pair:
                        _, value = pair.split('=', 1)
                        user_inputs.append(value.strip().strip('"').strip("'"))

        # Prepare to execute
        result = ""
        lines = blockly_code.split('\n')
        filtered_lines = []
        skip_mode = False
        in_demo_block = False

        for line in lines:
            if 'import gradio' in line:
                continue
            if 'demo = gr.Interface' in line:
                in_demo_block = True
                skip_mode = True
                continue
            elif 'demo.launch' in line:
                skip_mode = False
                in_demo_block = False
                continue
            elif in_demo_block:
                continue
            if 'gr.' in line:
                continue
            if not skip_mode:
                filtered_lines.append(line)

        code_to_run = '\n'.join(filtered_lines)

        def capture_result(msg):
            nonlocal result
            result = msg

        env = {
            "reply": capture_result,
            "__builtins__": __builtins__,
        }

        exec("import os", env)
        exec("import requests", env)
        exec("import json", env)

        exec(code_to_run, env)

        if "create_mcp" in env:
            import inspect
            sig = inspect.signature(env["create_mcp"])
            params = list(sig.parameters.values())

            typed_args = []
            for i, arg in enumerate(user_inputs):
                if i >= len(params):
                    break
                if arg is None or arg == "":
                    typed_args.append(None)
                    continue
                anno = params[i].annotation
                try:
                    if anno == int:
                        typed_args.append(int(float(arg)))
                    elif anno == float:
                        typed_args.append(float(arg))
                    elif anno == bool:
                        typed_args.append(str(arg).lower() in ("true", "1"))
                    elif anno == str or anno == inspect._empty:
                        typed_args.append(str(arg))
                    else:
                        typed_args.append(arg)
                except Exception:
                    typed_args.append(arg)

            result = env["create_mcp"](*typed_args)

        return result if result else "No output generated"

    except Exception as e:
        print(f"[MCP EXECUTION ERROR] {e}")
        import traceback
        traceback.print_exc()
        return f"Error executing MCP: {str(e)}"

def delete_block(block_id):
    """Delete a block from the Blockly workspace"""
    try:
        print(f"[DELETE REQUEST] Attempting to delete block: {block_id}")
        
        # Clear any old results for this block ID first
        if block_id in deletion_results:
            deletion_results.pop(block_id)
        
        # Add to deletion queue
        deletion_queue.put({"block_id": block_id})
        print(f"[DELETE REQUEST] Added to queue: {block_id}")
        
        # Wait for result with timeout
        import time
        timeout = 8  # Increased timeout to 8 seconds
        start_time = time.time()
        check_interval = 0.05  # Check more frequently
        
        while time.time() - start_time < timeout:
            if block_id in deletion_results:
                result = deletion_results.pop(block_id)
                print(f"[DELETE RESULT] Received result for {block_id}: success={result.get('success')}, error={result.get('error')}")
                if result["success"]:
                    return f"[TOOL] Successfully deleted block {block_id}"
                else:
                    return f"[TOOL] Failed to delete block {block_id}: {result.get('error', 'Unknown error')}"
            time.sleep(check_interval)
        
        print(f"[DELETE TIMEOUT] No response received for block {block_id} after {timeout} seconds")
        return f"Timeout waiting for deletion confirmation for block {block_id}"
            
    except Exception as e:
        print(f"[DELETE ERROR] {e}")
        import traceback
        traceback.print_exc()
        return f"Error deleting block: {str(e)}"

def create_block(block_spec):
    """Create a block in the Blockly workspace"""
    try:
        print(f"[CREATE REQUEST] Attempting to create block: {block_spec}")
        
        # Generate a unique request ID
        import uuid
        request_id = str(uuid.uuid4())
        
        # Clear any old results for this request ID first
        if request_id in creation_results:
            creation_results.pop(request_id)
        
        # Add to creation queue
        creation_queue.put({"request_id": request_id, "block_spec": block_spec})
        print(f"[CREATE REQUEST] Added to queue with ID: {request_id}")
        
        # Wait for result with timeout
        import time
        timeout = 8  # 8 seconds timeout
        start_time = time.time()
        check_interval = 0.05  # Check more frequently
        
        while time.time() - start_time < timeout:
            if request_id in creation_results:
                result = creation_results.pop(request_id)
                print(f"[CREATE RESULT] Received result for {request_id}: success={result.get('success')}, error={result.get('error')}")
                if result["success"]:
                    return f"[TOOL] Successfully created block: {result.get('block_id', 'unknown')}"
                else:
                    return f"[TOOL] Failed to create block: {result.get('error', 'Unknown error')}"
            time.sleep(check_interval)
        
        print(f"[CREATE TIMEOUT] No response received for request {request_id} after {timeout} seconds")
        return f"Timeout waiting for block creation confirmation"
            
    except Exception as e:
        print(f"[CREATE ERROR] {e}")
        import traceback
        traceback.print_exc()
        return f"Error creating block: {str(e)}"

# Server-Sent Events endpoint for creation requests
@app.get("/create_stream")
async def create_stream():
    """Stream creation requests to the frontend using Server-Sent Events"""
    
    async def clear_sent_request(sent_requests, request_id, delay):
        """Clear request_id from sent_requests after delay seconds"""
        await asyncio.sleep(delay)
        if request_id in sent_requests:
            sent_requests.discard(request_id)
    
    async def event_generator():
        sent_requests = set()  # Track sent requests to avoid duplicates
        heartbeat_counter = 0
        
        while True:
            try:
                # Check for creation requests (non-blocking)
                if not creation_queue.empty():
                    creation_request = creation_queue.get_nowait()
                    request_id = creation_request.get("request_id")
                    
                    # Avoid sending duplicate requests too quickly
                    if request_id not in sent_requests:
                        sent_requests.add(request_id)
                        print(f"[SSE CREATE SEND] Sending creation request with ID: {request_id}")
                        yield f"data: {json.dumps(creation_request)}\n\n"
                        
                        # Clear from sent_requests after 10 seconds
                        asyncio.create_task(clear_sent_request(sent_requests, request_id, 10))
                    else:
                        print(f"[SSE CREATE SKIP] Skipping duplicate request for ID: {request_id}")
                    
                    await asyncio.sleep(0.1)  # Small delay between messages
                else:
                    # Send a heartbeat every 30 seconds to keep connection alive
                    heartbeat_counter += 1
                    if heartbeat_counter >= 300:  # 300 * 0.1 = 30 seconds
                        yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                        heartbeat_counter = 0
                    await asyncio.sleep(0.1)
            except queue.Empty:
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"[SSE CREATE ERROR] {e}")
                await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

# Endpoint to receive creation results from frontend
@app.post("/creation_result")
async def creation_result(request: Request):
    """Receive creation results from the frontend"""
    data = await request.json()
    request_id = data.get("request_id")
    success = data.get("success")
    error = data.get("error")
    block_id = data.get("block_id")
    
    print(f"[CREATION RESULT RECEIVED] request_id={request_id}, success={success}, error={error}, block_id={block_id}")
    
    if request_id:
        # Store the result for the create_block function to retrieve
        creation_results[request_id] = data
        print(f"[CREATION RESULT STORED] Results dict now has {len(creation_results)} items")
    
    return {"received": True}

# Server-Sent Events endpoint for deletion requests
@app.get("/delete_stream")
async def delete_stream():
    """Stream deletion requests to the frontend using Server-Sent Events"""
    
    async def clear_sent_request(sent_requests, block_id, delay):
        """Clear block_id from sent_requests after delay seconds"""
        await asyncio.sleep(delay)
        if block_id in sent_requests:
            sent_requests.discard(block_id)
    
    async def event_generator():
        sent_requests = set()  # Track sent requests to avoid duplicates
        heartbeat_counter = 0
        
        while True:
            try:
                # Check for deletion requests (non-blocking)
                if not deletion_queue.empty():
                    deletion_request = deletion_queue.get_nowait()
                    block_id = deletion_request.get("block_id")
                    
                    # Avoid sending duplicate requests too quickly
                    if block_id not in sent_requests:
                        sent_requests.add(block_id)
                        print(f"[SSE SEND] Sending deletion request for block: {block_id}")
                        yield f"data: {json.dumps(deletion_request)}\n\n"
                        
                        # Clear from sent_requests after 10 seconds
                        asyncio.create_task(clear_sent_request(sent_requests, block_id, 10))
                    else:
                        print(f"[SSE SKIP] Skipping duplicate request for block: {block_id}")
                    
                    await asyncio.sleep(0.1)  # Small delay between messages
                else:
                    # Send a heartbeat every 30 seconds to keep connection alive
                    heartbeat_counter += 1
                    if heartbeat_counter >= 300:  # 300 * 0.1 = 30 seconds
                        yield f"data: {json.dumps({'heartbeat': True})}\n\n"
                        heartbeat_counter = 0
                    await asyncio.sleep(0.1)
            except queue.Empty:
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"[SSE ERROR] {e}")
                await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

# Endpoint to receive deletion results from frontend
@app.post("/deletion_result")
async def deletion_result(request: Request):
    """Receive deletion results from the frontend"""
    data = await request.json()
    block_id = data.get("block_id")
    success = data.get("success")
    error = data.get("error")
    
    print(f"[DELETION RESULT RECEIVED] block_id={block_id}, success={success}, error={error}")
    
    if block_id:
        # Store the result for the delete_block function to retrieve
        deletion_results[block_id] = data
        print(f"[DELETION RESULT STORED] Results dict now has {len(deletion_results)} items")
    
    return {"received": True}

def create_gradio_interface():
    # Hardcoded system prompt
    SYSTEM_PROMPT = f"""You are an AI assistant that helps users build **MCP servers** using Blockly blocks.
MCP lets AI systems define tools with specific inputs and outputs that any LLM can call.

You’ll receive the workspace state in this format:
`blockId | block_name(inputs(input_name: value))`

**Special cases:**
- `create_mcp` and `func_def` use
  `blockId | block_name(inputs(input_name: type), outputs(output_name: value))`
- Indentation or nesting shows logic hierarchy (like loops or conditionals).
- The `blockId` before the pipe `|` is each block’s unique identifier.

---

### Your job
- Help users understand or fix their MCP logic in natural, human language.
- Never mention the internal block syntax or say “multi-context-protocol.” Just call it **MCP**.
- Focus on what the code *does* and what the user is trying to achieve, not on the raw block format.

---

### Using Tools
Before using any tool, **explicitly plan** what you will do.
You can only use **one tool per message** - NEVER EVER combine multiple tool calls in one message.
If you need two actions, use two messages.
```

---

### Running MCP
You can execute the MCP directly and get the result back.

---

### Deleting Blocks
Each block starts with its ID, like `blockId | block_name(...)`.
To delete one, end your message with:
You can delete any block except the main `create_mcp` block.
You can see the ID to the left of each block it will be a jarble of characters
looking something like:

`blockId | code`

Each block has its own ID, and you need to use the ID specifically from
the correct block.

---

### Creating Blocks
You can create new blocks in the workspace.
To create a block, specify its type and parameters (if any).

If you want to create a block inside of a block, do it like this:

block_name(inputs(value_name: block_name2(inputs(value_name2: value))))

Where you specify inputs() per block, even if it's inside of another block.

List of blocks:

{blocks_context}

YOU CANNOT CREATE A MCP BLOCK OR EDIT ITS INPUTS. YOU MUST TELL THE USER TO DO SO.
"""
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "delete_block",
                "description": "Delete a single block using its ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "The ID of the block you're trying to delete.",
                        },
                    },
                    "required": ["id"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_block",
                "description": "Creates a single block that allows recursive nested blocks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "The create block command using the custom DSL format.",
                        },
                    },
                    "required": ["command"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "run_mcp",
                "description": "Runs the MCP with the given inputs. Create one parameter for each input that the user-created MCP allows.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": True
                },
            }
        },
    ]
    
    def chat_with_context(message, history):
        # Check if API key is set and create/update client
        global client, stored_api_key
        
        # Use stored key or check environment
        api_key = stored_api_key or os.environ.get("OPENAI_API_KEY")
        
        if api_key and (not client or (hasattr(client, 'api_key') and client.api_key != api_key)):
            try:
                client = OpenAI(api_key=api_key)
            except Exception as e:
                yield f"Error initializing OpenAI client: {str(e)}"
                return
        
        if not client or not api_key:
            yield "OpenAI API key not configured. Please set it in File > Settings in the Blockly interface."
            return
        
        # Get the chat context from the global variable
        global latest_blockly_chat_code
        context = latest_blockly_chat_code
        
        # Convert history to OpenAI format
        full_history = []
        for human, ai in history:
            full_history.append({"role": "user", "content": human})
            full_history.append({"role": "assistant", "content": ai})

        # Debug: Print context to see what we're getting
        print(f"[DEBUG] Context received: {context if context else 'No context available'}")

        # Combine system prompt with context
        full_system_prompt = SYSTEM_PROMPT
        if context:
            full_system_prompt += f"\n\nCurrent Blockly workspace state:\n{context}"
        else:
            full_system_prompt += "\n\nNote: No Blockly workspace context is currently available."

        # Allow up to 10 consecutive messages from the agent
        accumulated_response = ""
        max_iterations = 10
        current_iteration = 0
        
        # Start with the user's original message
        current_prompt = message
        temp_history = full_history.copy()
        
        while current_iteration < max_iterations:
            current_iteration += 1
            
            try:
                # Create the completion request with tools
                response = client.chat.completions.create(
                    model="gpt-4o-2024-08-06",
                    messages=[
                        {"role": "system", "content": full_system_prompt},
                        *temp_history,
                        {"role": "user", "content": current_prompt}
                    ],
                    tools=tools,
                    tool_choice="auto"  # Let the model decide whether to use tools
                )
                
                response_message = response.choices[0].message
                ai_response = response_message.content or ""
                
                # Check if the model wants to use tools
                if response_message.tool_calls:
                    # Display the AI's message before executing tools (if any)
                    if ai_response:
                        if accumulated_response:
                            accumulated_response += "\n\n"
                        accumulated_response += ai_response
                        yield accumulated_response
                    
                    # Process each tool call
                    for tool_call in response_message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        
                        print(f"[TOOL CALL] {function_name} with args: {function_args}")
                        
                        # Execute the appropriate function
                        tool_result = None
                        result_label = ""
                        
                        if function_name == "delete_block":
                            block_id = function_args.get("id", "")
                            tool_result = delete_block(block_id)
                            result_label = "Delete Operation"
                            
                        elif function_name == "create_block":
                            command = function_args.get("command", "")
                            tool_result = create_block(command)
                            result_label = "Create Operation"
                            
                        elif function_name == "run_mcp":
                            # Build the MCP call string from the arguments
                            # run_mcp receives dynamic arguments based on the MCP's inputs
                            params = []
                            for key, value in function_args.items():
                                # Format as key=value for execute_mcp
                                params.append(f"{key}=\"{value}\"")
                            mcp_call = f"create_mcp({', '.join(params)})"
                            print(f"[MCP CALL] Executing: {mcp_call}")
                            tool_result = execute_mcp(mcp_call)
                            result_label = "MCP Execution Result"
                        
                        if tool_result:
                            print(f"[TOOL RESULT] {tool_result}")
                            
                            # Yield the tool result
                            if accumulated_response:
                                accumulated_response += "\n\n"
                            accumulated_response += f"**{result_label}:** {tool_result}"
                            yield accumulated_response
                            
                            # Update history with the tool call and result
                            temp_history.append({"role": "user", "content": current_prompt})
                            temp_history.append({"role": "assistant", "content": ai_response, "tool_calls": response_message.tool_calls})
                            temp_history.append({"role": "tool", "tool_call_id": tool_call.id, "content": tool_result})
                            
                            # Set up next prompt to have the model respond to the tool result
                            current_prompt = f"The tool has been executed with the result shown above. Please respond appropriately to the user based on this result."
                    
                    # Continue to next iteration if tools were used
                    continue
                    
                else:
                    # No tool calls, this is a regular response
                    if accumulated_response:
                        accumulated_response += "\n\n"
                    accumulated_response += ai_response
                    yield accumulated_response
                    break
                    
            except Exception as e:
                if accumulated_response:
                    yield f"{accumulated_response}\n\nError in iteration {current_iteration}: {str(e)}"
                else:
                    yield f"Error: {str(e)}"
                return
        
        # If we hit max iterations, add a note
        if current_iteration >= max_iterations:
            accumulated_response += f"\n\n*(Reached maximum of {max_iterations} consecutive responses)*"
            yield accumulated_response
    
    # Create the standard ChatInterface
    demo = gr.ChatInterface(
        fn=chat_with_context,
        title="Blockly MCP Chat",
    )

    return demo

# Mount Gradio with FastAPI
demo = create_gradio_interface()
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    print("[BOOT] Running Gradio+FastAPI Chat on http://127.0.0.1:7861")
    uvicorn.run(app, host="0.0.0.0", port=7861)