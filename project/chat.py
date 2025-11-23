import os
import re
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
import gradio as gr
import asyncio
import queue
import json
import uuid
import time
from colorama import Fore, Style
from huggingface_hub import HfApi

# Initialize OpenAI client (will be updated when API key is set)
client = None

# Store API keys in memory for this process
stored_api_key = ""
stored_hf_key = ""

# Global variable to store the latest chat context
latest_blockly_chat_code = ""

# Global variable to store the workspace's variables
latest_blockly_vars = ""

# Queue for deletion requests and results storage
deletion_queue = queue.Queue()
deletion_results = {}

# Queue for creation requests and results storage
creation_queue = queue.Queue()
creation_results = {}

# Queue for variable creation requests and results storage
variable_queue = queue.Queue()
variable_results = {}

# Queue for edit MCP requests and results storage
edit_mcp_queue = queue.Queue()
edit_mcp_results = {}

# Global variable to store the deployed HF MCP server URL
current_mcp_server_url = None

# Global variable to track if a deployment just happened
deployment_just_happened = False
deployment_message = ""

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
    global latest_blockly_chat_code, latest_blockly_vars
    data = await request.json()
    latest_blockly_chat_code = data.get("code", "")
    latest_blockly_vars = data.get("varString", "")
    print("\n[FASTAPI] Updated Blockly chat code:\n", latest_blockly_chat_code)
    print("\n[FASTAPI] Updated Blockly variables:\n", latest_blockly_vars)
    return {"code": latest_blockly_chat_code}

@app.post("/set_api_key_chat")
async def set_api_key_chat(request: Request):
    """Receive API keys from frontend and store them"""
    global stored_api_key, stored_hf_key
    data = await request.json()
    api_key = data.get("api_key", "").strip()
    hf_key = data.get("hf_key", "").strip()
    
    # Store in memory and set environment variables for this process
    if api_key:
        stored_api_key = api_key
        os.environ["OPENAI_API_KEY"] = api_key
        print(f"[CHAT API KEY] Set OPENAI_API_KEY in chat.py environment")
    
    if hf_key:
        stored_hf_key = hf_key
        os.environ["HUGGINGFACE_API_KEY"] = hf_key
        print(f"[CHAT HF KEY] Set HUGGINGFACE_API_KEY in chat.py environment")
    
    return {"success": True}

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

def create_block(block_spec, under_block_id=None):
    """Create a block in the Blockly workspace"""
    try:
        print(f"[CREATE REQUEST] Attempting to create block: {block_spec}")
        if under_block_id:
            print(f"[CREATE REQUEST] Under block ID: {under_block_id}")
        
        # Generate a unique request ID
        import uuid
        request_id = str(uuid.uuid4())
        
        # Clear any old results for this request ID first
        if request_id in creation_results:
            creation_results.pop(request_id)
        
        # Add to creation queue with optional under_block_id
        queue_data = {"request_id": request_id, "block_spec": block_spec}
        if under_block_id:
            queue_data["under_block_id"] = under_block_id
        creation_queue.put(queue_data)
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

def create_variable(var_name):
    """Create a variable in the Blockly workspace"""
    try:
        print(f"[VARIABLE REQUEST] Attempting to create variable: {var_name}")
        
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        
        # Clear any old results for this request ID first
        if request_id in variable_results:
            variable_results.pop(request_id)
        
        # Add to variable creation queue
        queue_data = {"request_id": request_id, "variable_name": var_name}
        variable_queue.put(queue_data)
        print(f"[VARIABLE REQUEST] Added to queue with ID: {request_id}")
        
        # Wait for result with timeout
        timeout = 8  # 8 seconds timeout
        start_time = time.time()
        check_interval = 0.05  # Check more frequently
        
        while time.time() - start_time < timeout:
            if request_id in variable_results:
                result = variable_results.pop(request_id)
                print(f"[VARIABLE RESULT] Received result for {request_id}: success={result.get('success')}, error={result.get('error')}")
                if result["success"]:
                    return f"[TOOL] Successfully created variable: {result.get('variable_id', var_name)}"
                else:
                    return f"[TOOL] Failed to create variable: {result.get('error', 'Unknown error')}"
            time.sleep(check_interval)
        
        print(f"[VARIABLE TIMEOUT] No response received for request {request_id} after {timeout} seconds")
        return f"Timeout waiting for variable creation confirmation"
            
    except Exception as e:
        print(f"[VARIABLE ERROR] {e}")
        import traceback
        traceback.print_exc()
        return f"Error creating variable: {str(e)}"

def edit_mcp(inputs=None, outputs=None):
    """Edit the inputs and outputs of the create_mcp block"""
    try:
        print(f"[EDIT MCP REQUEST] Attempting to edit MCP block: inputs={inputs}, outputs={outputs}")
        
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        
        # Clear any old results for this request ID first
        if request_id in edit_mcp_results:
            edit_mcp_results.pop(request_id)
        
        # Build the edit data
        edit_data = {"request_id": request_id}
        if inputs is not None:
            edit_data["inputs"] = inputs
        if outputs is not None:
            edit_data["outputs"] = outputs
        
        # Add to edit MCP queue
        edit_mcp_queue.put(edit_data)
        print(f"[EDIT MCP REQUEST] Added to queue with ID: {request_id}")
        
        # Wait for result with timeout
        timeout = 8  # 8 seconds timeout
        start_time = time.time()
        check_interval = 0.05  # Check more frequently
        
        while time.time() - start_time < timeout:
            if request_id in edit_mcp_results:
                result = edit_mcp_results.pop(request_id)
                print(f"[EDIT MCP RESULT] Received result for {request_id}: success={result.get('success')}, error={result.get('error')}")
                if result["success"]:
                    return f"[TOOL] Successfully edited MCP block inputs/outputs"
                else:
                    return f"[TOOL] Failed to edit MCP block: {result.get('error', 'Unknown error')}"
            time.sleep(check_interval)
        
        print(f"[EDIT MCP TIMEOUT] No response received for request {request_id} after {timeout} seconds")
        return f"Timeout waiting for MCP edit confirmation"
            
    except Exception as e:
        print(f"[EDIT MCP ERROR] {e}")
        import traceback
        traceback.print_exc()
        return f"Error editing MCP block: {str(e)}"

# Unified Server-Sent Events endpoint for all workspace operations
@app.get("/unified_stream")
async def unified_stream():
    """Unified SSE endpoint for delete, create, and variable operations"""
    
    async def clear_sent_request(sent_requests, request_key, delay):
        """Clear request_key from sent_requests after delay seconds"""
        await asyncio.sleep(delay)
        if request_key in sent_requests:
            sent_requests.discard(request_key)
    
    async def event_generator():
        sent_requests = set()  # Track sent requests to avoid duplicates
        heartbeat_counter = 0
        
        while True:
            try:
                # Check deletion queue
                if not deletion_queue.empty():
                    deletion_request = deletion_queue.get_nowait()
                    block_id = deletion_request.get("block_id")
                    request_key = f"delete_{block_id}"
                    
                    # Avoid sending duplicate requests too quickly
                    if request_key not in sent_requests:
                        sent_requests.add(request_key)
                        deletion_request["type"] = "delete"  # Add type identifier
                        print(f"[SSE SEND] Sending deletion request for block: {block_id}")
                        yield f"data: {json.dumps(deletion_request)}\n\n"
                        
                        # Clear from sent_requests after 10 seconds
                        asyncio.create_task(clear_sent_request(sent_requests, request_key, 10))
                    else:
                        print(f"[SSE SKIP] Skipping duplicate request for block: {block_id}")
                
                # Check creation queue
                elif not creation_queue.empty():
                    creation_request = creation_queue.get_nowait()
                    request_id = creation_request.get("request_id")
                    request_key = f"create_{request_id}"
                    
                    # Avoid sending duplicate requests too quickly
                    if request_key not in sent_requests:
                        sent_requests.add(request_key)
                        creation_request["type"] = "create"  # Add type identifier
                        print(f"[SSE SEND] Sending creation request with ID: {request_id}")
                        yield f"data: {json.dumps(creation_request)}\n\n"
                        
                        # Clear from sent_requests after 10 seconds
                        asyncio.create_task(clear_sent_request(sent_requests, request_key, 10))
                    else:
                        print(f"[SSE SKIP] Skipping duplicate request for ID: {request_id}")
                
                # Check variable queue
                elif not variable_queue.empty():
                    variable_request = variable_queue.get_nowait()
                    request_id = variable_request.get("request_id")
                    request_key = f"variable_{request_id}"
                    
                    # Avoid sending duplicate requests too quickly
                    if request_key not in sent_requests:
                        sent_requests.add(request_key)
                        variable_request["type"] = "variable"  # Add type identifier
                        print(f"[SSE SEND] Sending variable creation request with ID: {request_id}")
                        yield f"data: {json.dumps(variable_request)}\n\n"
                        
                        # Clear from sent_requests after 10 seconds
                        asyncio.create_task(clear_sent_request(sent_requests, request_key, 10))
                    else:
                        print(f"[SSE SKIP] Skipping duplicate request for ID: {request_id}")
                
                # Check edit MCP queue
                elif not edit_mcp_queue.empty():
                    edit_request = edit_mcp_queue.get_nowait()
                    request_id = edit_request.get("request_id")
                    request_key = f"edit_mcp_{request_id}"
                    
                    # Avoid sending duplicate requests too quickly
                    if request_key not in sent_requests:
                        sent_requests.add(request_key)
                        edit_request["type"] = "edit_mcp"  # Add type identifier
                        print(f"[SSE SEND] Sending edit MCP request with ID: {request_id}")
                        yield f"data: {json.dumps(edit_request)}\n\n"
                        
                        # Clear from sent_requests after 10 seconds
                        asyncio.create_task(clear_sent_request(sent_requests, request_key, 10))
                    else:
                        print(f"[SSE SKIP] Skipping duplicate request for ID: {request_id}")
                
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

# Endpoint to receive variable creation results from frontend
@app.post("/variable_result")
async def variable_result(request: Request):
    """Receive variable creation results from the frontend"""
    data = await request.json()
    request_id = data.get("request_id")
    success = data.get("success")
    error = data.get("error")
    variable_id = data.get("variable_id")
    
    print(f"[VARIABLE RESULT RECEIVED] request_id={request_id}, success={success}, error={error}, variable_id={variable_id}")
    
    if request_id:
        # Store the result for the create_variable function to retrieve
        variable_results[request_id] = data
        print(f"[VARIABLE RESULT STORED] Results dict now has {len(variable_results)} items")
    
    return {"received": True}

# Endpoint to receive edit MCP results from frontend
@app.post("/edit_mcp_result")
async def edit_mcp_result(request: Request):
    """Receive edit MCP results from the frontend"""
    data = await request.json()
    request_id = data.get("request_id")
    success = data.get("success")
    error = data.get("error")
    
    print(f"[EDIT MCP RESULT RECEIVED] request_id={request_id}, success={success}, error={error}")
    
    if request_id:
        # Store the result for the edit_mcp function to retrieve
        edit_mcp_results[request_id] = data
        print(f"[EDIT MCP RESULT STORED] Results dict now has {len(edit_mcp_results)} items")
    
    return {"received": True}

def deploy_to_huggingface(space_name):
    """Deploy the generated MCP code to a Hugging Face Space"""
    global stored_hf_key
    
    if not stored_hf_key:
        return "[DEPLOY ERROR] No Hugging Face API key configured. Please set it in File > Keys."
    
    try:
        from huggingface_hub import HfApi
    except ImportError:
        return "[DEPLOY ERROR] huggingface_hub not installed. Run: pip install huggingface_hub"
    
    try:
        api = HfApi(token=stored_hf_key)
        
        # Get username from token
        user_info = api.whoami()
        username = user_info["name"]
        repo_id = f"{username}/{space_name}"
        
        print(f"[DEPLOY] Creating HF Space: {repo_id}")
        
        # Create the Space
        api.create_repo(
            repo_id=repo_id,
            repo_type="space",
            space_sdk="gradio",
            private=False,
        )
        
        print(f"[DEPLOY] Space created. Uploading files...")
        
        # Get the actual generated Python code from test.py (not the Blockly DSL)
        python_code = ""
        try:
            resp = requests.get(f"http://127.0.0.1:{os.getenv('PORT', 8080)}/get_latest_code")
            if resp.ok:
                python_code = resp.json().get("code", "")
        except Exception as e:
            print(f"[DEPLOY WARN] Could not fetch Python code from test.py: {e}")
        
        if not python_code.strip():
            return "[DEPLOY ERROR] No generated Python code available. Create and test your tool first."
        
        # Upload app.py with actual Python code
        api.upload_file(
            path_or_fileobj=python_code.encode(),
            path_in_repo="app.py",
            repo_id=repo_id,
            repo_type="space",
        )
        
        # Create requirements.txt
        requirements_content = """gradio
openai
requests
huggingface_hub
"""
        
        api.upload_file(
            path_or_fileobj=requirements_content.encode(),
            path_in_repo="requirements.txt",
            repo_id=repo_id,
            repo_type="space",
        )
        
        # Create README.md with proper YAML front matter
        readme_content = f"""---
title: {space_name.replace('-', ' ').title()}
emoji: 🚀
colorFrom: purple
colorTo: blue
sdk: gradio
app_file: app.py
pinned: false
---

# {space_name}

This is a MCP server created with [MCP Blockly](https://github.com/owenkaplinsky/mcp-blockly): a visual programming environment for building AI tools.

The tool has been automatically deployed to Hugging Face Spaces and is ready to use!
"""
        
        api.upload_file(
            path_or_fileobj=readme_content.encode("utf-8"),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="space",
        )
        
        space_url = f"https://huggingface.co/spaces/{repo_id}"
        print(f"[DEPLOY SUCCESS] Space deployed: {space_url}")
        
        # Store the MCP server URL globally for native MCP support
        global current_mcp_server_url, deployment_just_happened, deployment_message
        current_mcp_server_url = space_url
        deployment_just_happened = True
        deployment_message = f"Your MCP tool is being built on Hugging Face Spaces. This usually takes 1-2 minutes. Once it's ready, you'll be able to use the MCP tools defined in your blocks."
        print(f"[MCP] Registered MCP server: {current_mcp_server_url}")
        
        return f"[TOOL] Successfully deployed to Hugging Face Space!\n\n**Space URL:** {space_url}"
        
    except Exception as e:
        print(f"[DEPLOY ERROR] {e}")
        import traceback
        traceback.print_exc()
        return f"[DEPLOY ERROR] Failed to deploy: {str(e)}"

def create_gradio_interface():
    # Hardcoded system prompt
    SYSTEM_PROMPT = f"""You are an AI assistant that helps users build **MCP servers** using Blockly blocks.
MCP lets AI systems define tools with specific inputs and outputs that any LLM can call.

You’ll receive the workspace state in this format:
`blockId | block_name(inputs(input_name: value))`

**Special cases:**
- `create_mcp` and `func_def` use `blockId | block_name(inputs(input_name: type), outputs(output_name: value))`
- Indentation or nesting shows logic hierarchy (like loops or conditionals).
- The `blockId` before the pipe `|` is each block’s unique identifier.

---

### Your job
- Help users understand or fix their MCP logic in natural, human language.
- You may reference the internal block syntax for your own understanding, but never show or explain it to the
user unless they explicitly ask.
- Focus on what the code *does* and what the user is trying to achieve, not on the raw block format.
- In your first message, you may either respond normally or call a tool. If you call a tool, you must first
explain your intended plan and the steps you will take, then perform the tool call in the same message.

---

### Using Your MCP
Once you deploy your MCP to a Hugging Face Space, the model will automatically have access to all the tools you defined. Simply ask the model to use your MCP tools, and it will call them natively without manual intervention.

**Deployment workflow:**
1. Create and test your MCP using Blockly blocks
2. Deploy to a Hugging Face Space using the `deploy_to_huggingface` tool
3. After deployment, the MCP tool becomes immediately available in this chat
4. You may call this tool afterwards as needed. Do not immediately run the MCP
server after deploying it. The user must ask (you can ask if they want it)

---

### Deleting Blocks
- Each block starts with its ID, like `blockId | block_name(...)`.
- To delete a block, specify its block ID. Each block ID is a unique random alphanumeric string shown to the left of the block.
- You can delete any block except the main `create_mcp` block.

`blockId | code`

Each block has its own ID, and you need to use the ID specifically from
the correct block.

---

### Creating Blocks
List of blocks:

{blocks_context}

---

You can create new blocks in the workspace by specifying the block type and its input parameters, if it has any.
You cannot create a MCP block or edit its inputs or outputs.
There are two kinds of nesting in Blockly:
1. **Statement-level nesting (main-level blocks)**  
    These are blocks that represent actions or structures, such as loops or conditionals, which can contain other blocks *under* them.  
    To create this kind of nesting, use **two separate `create_block` commands**:  
    - First, create the outer block (for example, a `repeat` or `if` block).  
    - Then, create the inner block *under* it using the `under` parameter.  
    Example: putting an `if` block inside a `repeat` block.
2. **Value-level nesting (output blocks)**  
    These are blocks that produce a value (like a number, text, or expression). They can’t exist alone in the workspace - they must
    be nested inside another block’s input. To create these, you can nest them directly in a single command, for example:
    math_arithmetic(inputs(A: math_number(inputs(NUM: 1)), B: math_number(inputs(NUM: 1))))
    Here, the two `math_number` blocks are nested inside the `math_arithmetic` block in one call.

When creating blocks, you are never allowed to insert raw text or numbers directly into a block's inputs.  
Every value must be enclosed inside the correct block type that represents that value.  
Failing to do this will cause the block to be invalid and unusable.

Example of what you must NOT do:

`text_isEmpty(inputs(VALUE: "text"))`

This is invalid because "text" is a raw string and not a block.

The correct and required form wraps the string inside a text block:

`text_isEmpty(inputs(VALUE: text(inputs(TEXT: "text"))))`

This is valid because it uses a text block as the value.

This rule is absolute and applies to all value types:
- Strings must always use a text block.
- Numbers must always use a math_number block.
- Booleans, lists, colors, and every other type must always use their correct block type.

If a block has a value input, that input must always contain another block.  
You are not permitted to use raw values under any circumstance.

For blocks that allow infinite things (like ...N) you do not need to provide any inputs
if you want it to be blank.

When creating blocks, you are unable to put an outputting block inside of another block
which already exists. If you are trying to nest input blocks, you must create them all
in one call.

But, for blocks that you want to stack that connect above or below to other blocks, you cannot
create both blocks in the same response. You must create one, wait, then create the other. You
need to wait and not do both in the same response because you need the ID of the first block.

### Variables

You will be given the current variables that are in the workspace. Like the blocks, you will see:

`varId | varName`

---

### Deploying to Hugging Face Spaces

Once the user has tested and is happy with their MCP tool, you can deploy it to a live Hugging Face Space using the `deploy_to_huggingface` tool.

**To deploy:**
1. Ask the user for a name for their Space (e.g., "my-tool")
2. Call the `deploy_to_huggingface` tool with that name
3. The tool will create a new Space, upload the code, and return a live URL

The deployed Space will be public and shareable with others.

You NEVER need to deploy it more than once. If you deployed it, you can run it as many times as you want WITHOUT deploying again.

---

Note: Users can see tool response outputs verbatim. You don't have to repeat the tool response unless you want to.
"""
    
    tools = [
        {
            "type": "function",
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
            }
        },
        {
            "type": "function",
            "name": "create_block",
            "description": "Creates a single block that allows recursive nested blocks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The create block command using the custom DSL format.",
                    },
                    "under": {
                        "type": "string",
                        "description": "The ID of the block that you want to place this under.",
                    },
                },
                "required": ["command"],
            }
        },
        {
            "type": "function",
            "name": "create_variable",
            "description": "Creates a variable.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the variable you want to create.",
                    },
                },
                "required": ["name"],
            }
        },
        {
            "type": "function",
            "name": "edit_mcp",
            "description": "Edit the inputs and outputs of the create_mcp block.",
            "parameters": {
                "type": "object",
                "properties": {
                    "inputs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": { "type": "string" },
                                "type": { "type": "string", "enum": ["string", "integer", "list"] }
                            },
                            "required": ["name", "type"]
                        }
                    },
                    "outputs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": { "type": "string" },
                                "type": { "type": "string", "enum": ["string", "integer", "list"] }
                            },
                            "required": ["name", "type"]
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "name": "deploy_to_huggingface",
            "description": "Deploy the generated MCP tool to a Hugging Face Space. Requires a Hugging Face API key to be set.",
            "parameters": {
                "type": "object",
                "properties": {
                    "space_name": {
                        "type": "string",
                        "description": "The name of the Hugging Face Space to create (e.g., 'my-tool')",
                    },
                },
                "required": ["space_name"],
            }
        },
    ]
    
    def chat_with_context(message, history):
        # Check if API key is set and create/update client
        global client, stored_api_key
        
        # Use stored key or environment key
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
        
        # Get chat context
        global latest_blockly_chat_code
        context = latest_blockly_chat_code
        global latest_blockly_vars
        vars = latest_blockly_vars
        
        # Convert history to OpenAI format
        input_items = []
        for human, ai in history:
            input_items.append({"role": "user", "content": human})
            input_items.append({"role": "assistant", "content": ai})
        
        # Debug
        print(f"[DEBUG] Context received: {context if context else 'No context available'}")
        
        # Build instructions
        instructions = SYSTEM_PROMPT
        if context:
            instructions += f"\n\nCurrent Blockly workspace state:\n{context}"
        else:
            instructions += "\n\nNote: No Blockly workspace context is currently available."
        
        if vars != "":
            instructions += f"\n\nCurrent Blockly variables:\n{vars}"
        else:
            instructions += "\n\nNote: No Blockly variables are currently available."
        
        # Iteration control
        accumulated_response = ""
        max_iterations = 10
        current_iteration = 0
        
        # Start with original user message
        current_prompt = message
        temp_input_items = input_items.copy()
        
        # MAIN LOOP
        while current_iteration < max_iterations:
            current_iteration += 1
            
            try:
                # Build dynamic tools list with MCP support
                dynamic_tools = tools.copy() if tools else []
                
                # Inject MCP tool if a server is registered
                global current_mcp_server_url, deployment_just_happened, deployment_message
                space_building_status = None  # Track if space is building
                if current_mcp_server_url:
                    mcp_injection_successful = False
                    try:
                        # Try to verify the MCP server is available before injecting
                        space_is_running = False
                        try:
                            # Extract username and space name from URL
                            # URL format: https://huggingface.co/spaces/username/space_name
                            url_parts = current_mcp_server_url.split("/spaces/")
                            if len(url_parts) == 2:
                                space_id = url_parts[1]
                                api = HfApi()
                                runtime_info = api.get_space_runtime(space_id)
                                print(f"[MCP] Space runtime status: {runtime_info}")
                                # Check if space is running
                                if runtime_info and runtime_info.stage == "RUNNING":
                                    space_is_running = True
                                    # Space is running - deployment is complete
                                    deployment_just_happened = False
                                    print(f"[MCP] Space is RUNNING")
                                else:
                                    # Space is not running - it's likely building
                                    space_building_status = runtime_info.stage if runtime_info else "unknown"
                                    print(f"[MCP] Space is not running yet (stage: {space_building_status})")
                        except Exception as check_error:
                            print(f"[MCP] Could not verify space runtime: {check_error}")
                        
                        # Only inject the MCP tool if the space is verified running
                        if space_is_running:
                            def convert_repo_to_live_mcp(url):
                                # input:  https://huggingface.co/spaces/user/space
                                # output: https://user-space.hf.space/gradio_api/mcp

                                parts = url.split("/spaces/")
                                user, space = parts[1].split("/")
                                return f"https://{user}-{space}.hf.space/gradio_api/mcp"

                            live_mcp_url = convert_repo_to_live_mcp(current_mcp_server_url)

                            mcp_tool = {
                                "type": "mcp",
                                "server_url": live_mcp_url,
                                "server_label": "user_mcp_server",
                                "require_approval": "never"
                            }
                            dynamic_tools.append(mcp_tool)
                            print(f"[MCP] Injected MCP tool for server: {current_mcp_server_url}")
                        else:
                            print(f"[MCP] Skipping MCP tool injection - space not running yet")
                    except Exception as mcp_error:
                        print(f"[MCP ERROR] Failed during MCP injection: {mcp_error}")
                        print(f"[MCP] Continuing without MCP tools...")
                        # Continue without MCP - don't crash
                
                # Add deployment status message to instructions if deployment just happened and space is not running
                deployment_instructions = instructions
                if deployment_just_happened and space_building_status and space_building_status != "RUNNING":
                    deployment_instructions = instructions + f"\n\n**MCP DEPLOYMENT STATUS:** {deployment_message}"
                
                # Create Responses API call
                response = client.responses.create(
                    model="gpt-4o",
                    instructions=deployment_instructions,
                    input=temp_input_items + [{"role": "user", "content": current_prompt}],
                    tools=dynamic_tools,
                    tool_choice="auto"
                )
                
                # print(response)
                
                # Extract outputs
                ai_response = ""
                tool_calls = []
                
                for item in response.output:
                    
                    if item.type == "message":
                        # Extract assistant text
                        for content in item.content:
                            if content.type == "output_text":
                                ai_response = content.text
                    
                    elif item.type == "function_call":
                        # Collect tool calls
                        tool_calls.append(item)
                
                # PROCESSING TOOL CALLS
                if tool_calls:

                    # Show assistant text FIRST if it exists
                    if ai_response:
                        if accumulated_response:
                            accumulated_response += "\n\n"
                        accumulated_response += ai_response
                        yield accumulated_response

                    # Now process each tool call, one by one
                    for tool_call in tool_calls:
                        function_name = tool_call.name
                        function_args = json.loads(tool_call.arguments)
                        call_id = tool_call.call_id
                        
                        temp_input_items.append({"role": "user", "content": current_prompt})
                        temp_input_items.append({"role": "assistant", "content": ai_response})

                        temp_input_items.append({
                            "type": "function_call",
                            "call_id": call_id,
                            "name": function_name,
                            "arguments": tool_call.arguments
                        })
                        
                        # Execute the tool
                        tool_result = None
                        result_label = ""
                        
                        if function_name == "delete_block":
                            block_id = function_args.get("id", "")
                            print(Fore.YELLOW + f"Agent deleted block with ID `{block_id}`." + Style.RESET_ALL)
                            tool_result = delete_block(block_id)
                            result_label = "Delete Operation"
                        
                        elif function_name == "create_block":
                            command = function_args.get("command", "")
                            under_block_id = function_args.get("under", None)
                            if under_block_id is None:
                                print(Fore.YELLOW + f"Agent created block with command `{command}`." + Style.RESET_ALL)
                            else:
                                print(Fore.YELLOW + f"Agent created block with command `{command}`, under block ID `{under_block_id}`." + Style.RESET_ALL)
                            tool_result = create_block(command, under_block_id)
                            result_label = "Create Operation"
                        
                        elif function_name == "create_variable":
                            name = function_args.get("name", "")
                            print(Fore.YELLOW + f"Agent created variable with name `{name}`." + Style.RESET_ALL)
                            tool_result = create_variable(name)
                            result_label = "Create Var Operation"
                        
                        elif function_name == "edit_mcp":
                            inputs = function_args.get("inputs", None)
                            outputs = function_args.get("outputs", None)
                            print(Fore.YELLOW + f"Agent editing MCP block: inputs={inputs}, outputs={outputs}." + Style.RESET_ALL)
                            tool_result = edit_mcp(inputs, outputs)
                            result_label = "Edit MCP Operation"
                        
                        elif function_name == "deploy_to_huggingface":
                            space_name = function_args.get("space_name", "")
                            print(Fore.YELLOW + f"Agent deploying to Hugging Face Space `{space_name}`." + Style.RESET_ALL)
                            tool_result = deploy_to_huggingface(space_name)
                            result_label = "Deployment Result"
                        
                        # SHOW TOOL RESULT IMMEDIATELY
                        if tool_result is not None:
                            print(Fore.YELLOW + f"[TOOL RESULT] {tool_result}" + Style.RESET_ALL)
                            
                            if accumulated_response:
                                accumulated_response += "\n\n"
                            accumulated_response += f"**{result_label}:** {tool_result}"
                            yield accumulated_response
                        
                        # Append the tool result into the conversation for the model
                        temp_input_items.append({
                            "type": "function_call_output",
                            "call_id": tool_call.call_id,
                            "output": str(tool_result)
                        })
                    
                    # Tell model to respond to tool result
                    current_prompt = "The tool has been executed with the result shown above. Please respond appropriately."
                    
                    continue  # Continue the main loop
                
                else:
                    if ai_response:
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
        
        # Max iterations reached
        if current_iteration >= max_iterations:
            accumulated_response += f"\n\n*(Reached maximum of {max_iterations} consecutive responses)*"
            yield accumulated_response


    # Attach to Gradio ChatInterface
    demo = gr.ChatInterface(
        fn=chat_with_context,
        title="AI Assistant",
    )

    return demo


def get_chat_gradio_interface():
    return create_gradio_interface()


if __name__ == "__main__":
    demo = create_gradio_interface()
    app = gr.mount_gradio_app(app, demo, path="/")