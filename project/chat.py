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

# Track if first MCP output block creation attempt has happened in this conversation
first_output_block_attempted = False

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
    return {"code": latest_blockly_chat_code}

@app.post("/set_api_key_chat")
async def set_api_key_chat(request: Request):
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

def create_block(block_spec, blockID=None, placement_type=None, input_name=None):
    try:
        # Generate a unique request ID
        import uuid
        request_id = str(uuid.uuid4())
        
        # Clear any old results for this request ID first
        if request_id in creation_results:
            creation_results.pop(request_id)
        
        # Add to creation queue with optional blockID, placement_type, and input_name
        queue_data = {"request_id": request_id, "block_spec": block_spec}
        if blockID:
            queue_data["blockID"] = blockID
        if placement_type:
            queue_data["placement_type"] = placement_type
        if input_name:
            queue_data["input_name"] = input_name
        creation_queue.put(queue_data)
        
        # Wait for result with timeout
        import time
        timeout = 8  # 8 seconds timeout
        start_time = time.time()
        check_interval = 0.05  # Check more frequently
        
        while time.time() - start_time < timeout:
            if request_id in creation_results:
                result = creation_results.pop(request_id)
                if result["success"]:
                    return f"[TOOL] Successfully created block: {result.get('block_id', 'unknown')}"
                else:
                    error_msg = result.get('error') or 'Unknown error'
                    return f"[TOOL] Failed to create block: {error_msg}"
            time.sleep(check_interval)
        
        print(f"[CREATE TIMEOUT] No response received for request {request_id} after {timeout} seconds")
        return f"Timeout waiting for block creation confirmation"
            
    except Exception as e:
        print(f"[CREATE ERROR] {e}")
        import traceback
        traceback.print_exc()
        return f"Error creating block: {str(e)}"

def create_variable(var_name):
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
    data = await request.json()
    request_id = data.get("request_id")
 
    if request_id:
        # Store the result for the create_block function to retrieve
        creation_results[request_id] = data
    
    return {"received": True}

# Endpoint to receive deletion results from frontend
@app.post("/deletion_result")
async def deletion_result(request: Request):
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
    data = await request.json()
    request_id = data.get("request_id")
    success = data.get("success")
    error = data.get("error")
    
    if request_id:
        # Store the result for the edit_mcp function to retrieve
        edit_mcp_results[request_id] = data
    
    return {"received": True}

def deploy_to_huggingface(space_name):
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

    You'll receive the workspace state in this format:
    `blockId → block_name(inputs(input_name: value))`

    Block ID parsing: Block IDs are everything before ` → ` (space-arrow-space). IDs are always complex/long strings.
    Example: `?fHZRh^|us|9bECO![$= → text(inputs(TEXT: "hello"))`, ID is `?fHZRh^|us|9bECO![$=`
    
    Special cases:
    - `create_mcp` and `func_def` use `blockId → block_name(inputs(input_name: type), outputs(output_name: value))`
    - Indentation or nesting shows logic hierarchy (like loops or conditionals).

    ---

    ### Your job
    - Help users understand or fix their MCP logic in natural, human language.
    - You may reference the internal block syntax for your own understanding, but never show or explain it unless explicitly asked.
    - Focus on what the code *does* and what the user is trying to achieve, not on the raw block format.
    - When calling a tool, first state your plan and the steps, then perform the tool call in the same message.

    ---

    ### Using the MCP
    After deployment to a Hugging Face Space, all defined tools become available in the chat environment and can be invoked directly.

    **Deployment workflow:**
    1. Create and test the MCP using Blockly blocks  
    2. Deploy to a Hugging Face Space with `deploy_to_huggingface`  
    3. After deployment, the MCP tools are available immediately  
    4. The MCP server should only be run if the user requests it

    ---

    ### Deleting Blocks
    - Each block starts with its ID, like `blockId → block_name(...)`.
    - To delete a block, specify its block ID.
    - Any block except the main `create_mcp` block can be deleted.

    `blockId → code`

    Use the exact ID from the workspace.

    ---

    ### Creating Blocks
    List of blocks:

    {blocks_context}

    You cannot create a `create_mcp` block, but you may edit its inputs using the `edit_mcp` tool.

    ### Block Types: Statement vs Value
    **Statement blocks** (loops, conditionals, any container) hold other blocks inside them and require sequential creation to get the container's ID first.
    
    **Value blocks** (math, text, logic, comparison) produce values that plug into inputs and must be built entirely in one nested create_block call.

    ### How to Place Blocks
    
    **CRITICAL: Understand the difference between placing blocks INSIDE the MCP vs. placing blocks in MCP OUTPUTS**
    - The MCP block is a statement container (like a loop or conditional)
    - Blocks placed `type: "under"` with the MCP's blockID go INSIDE the MCP's code body
    - Blocks placed `type: "input"` with `input_name: "name"` only work if the MCP has explicit outputs defined
    - By default, the MCP does NOT have output slots - you must create/edit outputs first

    **IF/ELSE Blocks:**

    The entire IF/ELSE structure must be created in one `create_block` call.

    **Structure:**
    `controls_if(inputs(IF0: cond, IF1: cond2, IF2: cond3, ELSE))`

    - `IF0:` first/main condition (required)
    - `IF1:`, `IF2:`, `IF3:`, etc. - else-if conditions (optional)
    - `ELSE` keyword (optional, no value)

    **Do NOT:**
    - Add ELSE or ELSE-IF later using `input_name`
    - Give ELSE a value
    - Use `IF:` alone without a number (must be `IF0`)

    **Correct placement after creation:**
    - `input_name: "DO0"`: Main IF branch
    - `input_name: "DO1"`: First ELSE-IF branch
    - `input_name: "DO2"`: Second ELSE-IF branch
    - `input_name: "ELSE"`: ELSE branch

    YOU CANNOT EDIT THE IF BLOCK LATER. IF YOU WILL NEED TO HAVE AN ELSE OR IFELSE LATER, YOU MUST CREATE IT WITH ALL BRANCHES FROM THE START.

    **Placement types** - use `blockID` and `type` parameters:
    
    - `type: "under"` - For statement blocks inside containers. Create the container first, then create statement blocks using the container's ID.
      Example: Create a loop first, then use `blockID: loopID, type: "under"` to place code inside it.
      Optional: use `input_name` for statement input names only (e.g., "DO0", "DO1", "ELSE" for IF blocks).
      Example: `create_block(text_append(...), blockID: ifBlockID, type: "under", input_name: "DO0")` places the block in the IF branch.
    
    - `type: "input"` - ONLY for value blocks placed in MCP output slots.
      Example: `text(inputs(TEXT: "hello"))` with `type: "input", input_name: "name"` places the text block in the MCP's first output slot.
      Requirement: The create_mcp block must have explicit outputs defined (you will see `outputs(...)` in the workspace state). Do not use this if outputs are not visible.
    
    Key rule: Statement input names (DO0, DO1, ELSE) are for `type: "under"`. Output slot names are for `type: "input"`. Never mix them.
      
    **Value block nesting** - For value blocks inside other blocks: nest them directly in the create_block command (do not use `blockID` or `type`).
    Example: `math_arithmetic(inputs(A: math_number(inputs(NUM: 5)), B: math_number(inputs(NUM: 3))))`

    **CRITICAL for value block expressions**: You MUST build the entire nested structure in ONE create_block call. You cannot:
    - Create blocks in stages
    - Create intermediate blocks first and connect them later
    - Break a value expression into multiple separate create_block calls
    This is impossible. Value blocks can only be built by nesting them inside the create_block command.
    Example: `math_arithmetic(inputs(A: math_number(inputs(NUM: 1)), B: math_arithmetic(inputs(A: math_number(inputs(NUM: 2)), B: math_number(inputs(NUM: 3))))))`

    ### Input Rules
    Every block must have `inputs()`. For blocks that grow like `make_json` or `text_join`, add as many inputs as needed:
    - `text_join(inputs(ADD0: text(inputs(TEXT: "hello")), ADD1: text(inputs(TEXT: "world"))))`
    The blocks list will have comments saying something like "you can make as many N as you want" if this is allowed for that block.
    
    **String values must always be quoted with double quotes.** All configuration values (like operation names, parameter values, etc.) that are strings must be `"quoted"`:
    - WRONG: `math_single(inputs(OP: ROOT, NUM: value)`
    - CORRECT: `math_single(inputs(OP: "ROOT", NUM: value)`
    
    **Variable IDs must always be quoted with double quotes**, even if they look like identifiers. Variable IDs often contain special characters like parentheses, pipes, and semicolons. ALWAYS quote the variable ID:
    - WRONG: variables_set(inputs(VAR: ..., VALUE: ...))
    - CORRECT: variables_set(inputs(VAR: "...", VALUE: ...))

    For value inputs, never use raw values. Always wrap in a block:
    - WRONG: `math_arithmetic(inputs(A: 5, B: "hi"))`
    - RIGHT: `math_arithmetic(inputs(A: math_number(inputs(NUM: 5)), B: text(inputs(TEXT: "hi"))))`

    You may NEVER create functions. You must only use code inside the MCP block itself.

    ---

    ### Variables
    Variables appear as:

    `varId → varName`

    ---

    ### Deploying to Hugging Face Spaces
    Steps:
    1. Ask the user for a Space name  
    2. Call `deploy_to_huggingface` with that name  
    3. A public Space is created and code is uploaded  

    Deployment is done only once; the deployed MCP may be run any number of times afterward.

    ---

    ## VALUE BLOCK CONSTRUCTION: ABSOLUTE RULE

    **Value blocks and value expressions must be built entirely in a SINGLE create_block call.**

    This is not negotiable. There is no alternative method. There is no workaround.

    When you need to create value blocks (math blocks, text blocks, logic blocks, comparison blocks, or any block that produces a value for another block to use), you must nest all of them together in one create_block call. All child blocks, all nested blocks, all sub-expressions must be included in that single call.

    **For any value expression, you have exactly ONE option: build it all in a single create_block call with all children nested inside.**

    You cannot call create_block multiple times for one value expression. You cannot create intermediate blocks and connect them later. These are not possible.

    **Correct:**
    `text_join(inputs(ADD0: text(inputs(TEXT: "a")), ADD1: text(inputs(TEXT: "b")), ADD2: text(inputs(TEXT: "c"))))`
    This is ONE call with all blocks nested in it.

    **Prohibited:**
    - `create_block(text(...))` then `create_block(text(...))` then `create_block(text(...))`: You cannot do this
    - Create one block, get its ID, then try to place other blocks in its inputs later: You cannot do this
    - Break a math expression across multiple calls: You cannot do this

    **Statement blocks are different.** Loops and conditionals require sequential calls because you need the container's ID first to place code inside it. But value blocks are not containers. They are atomic. Build the entire structure in one call or not at all.

    ---

    ## EVERY VALUE MUST HAVE A DESTINATION

    Before constructing ANY expression block (text_join, math operations, etc.), identify where it goes:
    - Assigned to a variable (via set_var block)
    - Passed as input to another block (nested in the create_block call)
    - Placed in an MCP output slot (using type: "input" and input_name: "name")
        - You CANNOT use type "under" to put a value block in the output slot of the MCP server. You MUST use "type" with "name".

    Do NOT create orphaned expression blocks with no destination. They serve no purpose.

    Always build the container/assignment block FIRST, then construct the value expression INSIDE it, both in a single call.

    Creating variables is not sufficient on its own. In addition to that, you MUST not forget to return the variable in the MCP block output slot.

    ### No Early Returns in Conditionals

    Blockly does not support early returns from within conditional branches. You MUST use a variable to store the result and return that variable in the MCP output:

    1. Create a variable
    2. In each branch, use a `set_var` block to assign the value to that variable. The VALUE input of set_var must contain your text_join or expression.
    3. Return the variable as an MCP output
    
    Always collect results in a variable first; never create expression blocks that exist outside a set_var or MCP output.

    ---

    Tool responses appear under the assistant role, but they are not part of your own words. Never treat tool output as
    something you said, and never fabricate or echo fake tool outputs.

    ---

    ## REQUIRED PLANNING PHASE BEFORE ANY TOOL CALL

    Before creating or deleting any blocks, always begin with a *Planning Phase*:

    0. Acknowledge the `VALUE BLOCK CONSTRUCTION: ABSOLUTE RULE` section and how you are prohibited from doing multi step calls for value blocks, and must do it in one create block call.
    Then also acknowledge that you are required to set values in all MCP block output slots, and cannot forget and leave them empty.

    1. **Analyze the user's request.** Identify all required inputs, outputs, intermediate steps, loops, and conditionals.

    2. **Write pseudocode showing the complete flow** using readable syntax like function calls and control structures.
    This is for *your own* understanding: work out the logic *before* translating to blocks.
    Example: `for item in items: result = process(item); output = combine(result)`

    3. **Create a detailed, step-by-step to-do list**:  
    List every action you will take, in exact order, with no omissions. Build from the outside in: create outer containers first, then add inner blocks inside them.

    For every step, explicitly specify:  
    - What action you will perform  
    - Which block you are acting on  
    - Which input or output slot you are using  
    - All parameters involved (including type and input_name)  
    - Every variable used and where it is used

    For every IF statement you create, you must explicitly state:  
    - The number of IFELSE branches (0, 1, 2, etc.)  
    - The number of ELSE branches (0 or 1)  
    - The exact condition that causes each branch to activate

    THESE DECLARATIONS ARE REQUIRED EVERY TIME AN IF STATEMENT IS MENTIONED, AND YOU MUST ALWAYS PROVIDE EXACTLY THREE INTEGERS WITH NO EXCEPTIONS OR SUBSTITUTIONS. FAILURE TO DO SO IMMEDIATELY INVALIDATES THE RESPONSE IN ITS ENTIRETY.
    YOU MUST HAVE EXPLICITLY SAID THESE THREE VALUES NO MATTER WHAT. THIS IS NON-NEGOTIABLE. THIS IS A HARD REQUIREMENT. ALWAYS SAY THIS, EVERY SINGLE TIME, NO MATTER WHAT.

    4. **Check the create_mcp block state:** Before using `type: "input"` and `input_name: "name"`, verify that the create_mcp block has outputs defined in the workspace state. If you do not see `outputs(...)` in the create_mcp block, do NOT use these parameters.

    5. Perform the actions in order without asking for approval or asking to wait for intermediate results."""
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
                    # Throwaway parameter to get the agent to think about what it wants to do again before it does it to increase reliability.
                    "notes": {
                        "type": "string",
                        "description": "Write the exact thing you need to make with this call. Cite your TODO list. If you're making an IF, say how many IF branches and whether it has an ELSE. Say the entire thing in plain text that your goal is.",
                    },
                    "command": {
                        "type": "string",
                        "description": "The create block command using the custom DSL format.",
                    },
                    "blockID": {
                        "type": "string",
                        "description": "The ID of the target block for placement. Do not use this if your goal is to place a block detached in the workspace.",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["under", "input"],
                        "description": "Placement type. 'under' for statement blocks inside containers. 'input' only for value blocks in MCP outputs.",
                    },
                    "input_name": {
                        "type": "string",
                        "description": "ONLY for two cases: placing value blocks into MCP output slots using 'R<N>', and placing statement blocks into specific branches of controls_if (DO0, DO1, ELSE). NEVER USE THIS PARAMETER UNLESS YOU ARE DOING ONE OF THOSE TWO EXACT THINGS.",
                    },
                },
                "required": ["notes", "command"],
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
                                "type": { "type": "string", "enum": ["string", "integer", "float", "list"] }
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
                                "type": { "type": "string", "enum": ["string", "integer", "float", "list"] }
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
        global client, stored_api_key, first_output_block_attempted
        
        # Reset output block tracking for this conversation turn
        first_output_block_attempted = False
        
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
        max_iterations = 15
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
                    tool_choice="auto",
                    parallel_tool_calls=False
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
                            blockID = function_args.get("blockID", None)
                            placement_type = function_args.get("type", None)
                            input_name = function_args.get("input_name", None)
                            
                            # Check if this is the first MCP output block creation attempt
                            is_first_output_attempt = (
                                not first_output_block_attempted and 
                                placement_type == "input" and 
                                input_name and 
                                input_name.startswith("R")
                            )
                            
                            if is_first_output_attempt:
                                # Mark that we've attempted an output block in this conversation
                                first_output_block_attempted = True
                                # Return warning instead of creating the block
                                tool_result = "[TOOL] Automated warning: Make sure your output block contains the full and entire value needed. Block placement was **not** executed. Retry with the full command needed in one go."
                                result_label = "Output Block Warning"
                                print(Fore.YELLOW + f"[FIRST OUTPUT BLOCK] Intercepted first output block attempt with command `{command}`." + Style.RESET_ALL)
                            else:
                                # Normal block creation
                                if blockID is None:
                                    print(Fore.YELLOW + f"Agent created block with command `{command}`." + Style.RESET_ALL)
                                else:
                                    print(Fore.YELLOW + f"Agent created block with command `{command}`, type: {placement_type}, blockID: `{blockID}`." + Style.RESET_ALL)
                                if input_name:
                                    print(Fore.YELLOW + f"  Input name: {input_name}" + Style.RESET_ALL)
                                tool_result = create_block(command, blockID, placement_type, input_name)
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