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
When you invoke a tool, it must be the **last thing in your message**.  

To call a tool, use this exact format (no newline after the opening backticks):

```name
(arguments_here)
```

---

### Running MCPs
You can execute MCPs directly.  
End your message (and say nothing after) with:

```run
create_mcp(input_name=value)
```

Use plain Python-style arguments (no `inputs()` wrapper).  
That’s how you actually run the MCP.

---

### Deleting Blocks
Each block starts with its ID, like `blockId | block_name(...)`.  
To delete one, end your message with:

```delete
blockId
```

You can delete any block except the main `create_mcp` block.

---

### Creating Blocks
You can create new blocks in the workspace.  
To create a block, specify its type and parameters (if any).  
End your message (and say nothing after) with:

```create
block_type(parameters)
```

Examples:
- `print_text("Hello World")` - creates a print block with text
- `text("some text")` - creates a text block
- `math_number(42)` - creates a number block
- `logic_boolean(true)` - creates a boolean block
- `mcp_tool("tool_name")` - creates an MCP tool block
- `controls_if()` - creates an if block
- `lists_create_empty()` - creates an empty list block

List of blocks:

{blocks_context}

---

Additionally, if you ever send a message without a tool call, your response will end. So, if you want to
call more tools after something you have to keep calling them. Any pause in tool callings ends the loop.

REMEMBER, AS YOU SEE BELOW, THE NAME MUST BE DIRECTLY AFTER THE ``` AND CANNOT HAVE A NEW LINE IN BETWEEN
THIS IS A REQUIREMENT. NAME MUST BE ON THE EXACT SAME LINE AS THE BACKTICKS.

```name
(arguments_here)
```
"""
    
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

        # Allow up to 5 consecutive messages from the agent
        accumulated_response = ""
        max_iterations = 5
        current_iteration = 0
        
        # Start with the user's original message
        current_prompt = message
        temp_history = full_history.copy()
        
        while current_iteration < max_iterations:
            current_iteration += 1
            
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": full_system_prompt},
                        *temp_history,
                        {"role": "user", "content": current_prompt}
                    ]
                )
                
                ai_response = response.choices[0].message.content
                
                # Define action patterns and their handlers
                action_patterns = {
                    'run': {
                        'pattern': r'```run\n(.+?)\n```',
                        'label': 'MCP',
                        'result_label': 'MCP Execution Result',
                        'handler': lambda content: execute_mcp(content),
                        'next_prompt': "Please respond to the MCP execution result above and provide any relevant information to the user. If you need to run another MCP, delete, or create blocks, you can do so."
                    },
                    'delete': {
                        'pattern': r'```delete\n(.+?)\n```',
                        'label': 'DELETE',
                        'result_label': 'Delete Operation',
                        'handler': lambda content: delete_block(content.strip()),
                        'next_prompt': "Please respond to the delete operation result above. If you need to run an MCP, delete more code, or create blocks, you can do so."
                    },
                    'create': {
                        'pattern': r'```create\n(.+?)\n```',
                        'label': 'CREATE',
                        'result_label': 'Create Operation',
                        'handler': lambda content: create_block(content.strip()),
                        'next_prompt': "Please respond to the create operation result above. If you need to run an MCP, delete code, or create more blocks, you can do so."
                    }
                }
                
                # Check for action blocks
                action_found = False
                for action_type, config in action_patterns.items():
                    match = re.search(config['pattern'], ai_response, re.DOTALL)
                    if match:
                        action_found = True
                        
                        # Extract content and filter the action block from displayed message
                        action_content = match.group(1)
                        displayed_response = ai_response[:match.start()].rstrip()
                        
                        print(f"[{config['label']} DETECTED] Processing: {action_content}")
                        
                        # Yield the displayed response first if it exists
                        if displayed_response:
                            if accumulated_response:
                                accumulated_response += "\n\n"
                            accumulated_response += displayed_response
                            yield accumulated_response
                        
                        # Execute the action
                        action_result = config['handler'](action_content)
                        
                        print(f"[{config['label']} RESULT] {action_result}")
                        
                        # Yield the action result
                        if accumulated_response:
                            accumulated_response += "\n\n"
                        accumulated_response += f"**{config['result_label']}:** {action_result}"
                        yield accumulated_response
                        
                        # Update history for next iteration
                        temp_history.append({"role": "user", "content": current_prompt})
                        temp_history.append({"role": "assistant", "content": ai_response})
                        temp_history.append({"role": "system", "content": f"{config['result_label']}: {action_result}"})
                        
                        # Set up next prompt
                        current_prompt = config['next_prompt']
                        break
                
                if action_found:
                    continue
                else:
                    # No action blocks found, this is the final response
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