from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr
import uvicorn
import re
from dotenv import load_dotenv

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()

latest_blockly_code = ""


@app.post("/update_code")
async def update_code(request: Request):
    global latest_blockly_code
    data = await request.json()
    latest_blockly_code = data.get("code", "")
    print("\n[FASTAPI] Updated Blockly code:\n", latest_blockly_code)
    return {"ok": True}


def execute_blockly_logic(user_inputs):
    global latest_blockly_code
    if not latest_blockly_code.strip():
        return "No Blockly code available"

    result = ""

    # More comprehensive filtering of Gradio-related code
    lines = latest_blockly_code.split('\n')
    filtered_lines = []
    skip_mode = False
    in_demo_block = False
    
    for line in lines:
        # Skip import gradio line
        if 'import gradio' in line:
            continue
            
        # Skip Gradio interface creation and any demo-related lines
        if 'demo = gr.Interface' in line:
            in_demo_block = True
            skip_mode = True
            continue
        elif 'demo.launch' in line:
            skip_mode = False
            in_demo_block = False
            continue
        elif in_demo_block:
            # Skip everything in the demo block (multi-line Interface declaration)
            continue
            
        # Skip any standalone gr. calls
        if 'gr.' in line:
            continue
        
        if not skip_mode:
            filtered_lines.append(line)
    
    code_to_run = '\n'.join(filtered_lines)

    def capture_result(msg):
        nonlocal result
        result = msg

    # Set up the environment with necessary imports that might be needed
    env = {
        "reply": capture_result,
        "__builtins__": __builtins__,
    }

    try:
        # Import any required modules in the execution environment
        exec("import os", env)
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
                    # Convert using the declared type hint
                    if anno == int:
                        typed_args.append(int(arg))
                    elif anno == float:
                        typed_args.append(float(arg))
                    elif anno == bool:
                        typed_args.append(str(arg).lower() in ("true", "1"))
                    elif anno == str or anno == inspect._empty:
                        typed_args.append(str(arg))
                    else:
                        # Unknown or complex type — leave as-is
                        typed_args.append(arg)
                except Exception:
                    # If conversion fails, pass the raw input
                    typed_args.append(arg)

            result = env["create_mcp"](*typed_args)
        elif "process_input" in env:
            env["process_input"](user_inputs)
    except Exception as e:
        print("[EXECUTION ERROR]", e)
        result = f"Error: {str(e)}"

    return result if result else "No output generated"


def build_interface():
    with gr.Blocks() as demo:
        # Create a fixed number of potential input fields (max 10)
        input_fields = []
        input_labels = []
        input_group_items = []
        
        with gr.Accordion("MCP Inputs", open=True):
            for i in range(10):
                # Create inputs that can be shown/hidden
                txt = gr.Textbox(label=f"Input {i+1}", visible=False)
                input_fields.append(txt)
                input_group_items.append(txt)

        output_fields = []
        
        with gr.Accordion("MCP Outputs", open=True):
            for i in range(10):
                out = gr.Textbox(label=f"Output {i+1}", visible=False, interactive=False)
                output_fields.append(out)
        
        with gr.Row():
            submit_btn = gr.Button("Submit")
            refresh_btn = gr.Button("Refresh")

        def refresh_inputs():
            global latest_blockly_code
            import re

            # Look for the create_mcp function definition
            pattern = r'def create_mcp\((.*?)\):'
            match = re.search(pattern, latest_blockly_code)

            params = []
            if match:
                params_str = match.group(1)
                if params_str.strip():
                    # Parse parameters to extract names and types
                    for param in params_str.split(','):
                        param = param.strip()
                        if ':' in param:
                            name, type_hint = param.split(':')
                            params.append({
                                'name': name.strip(),
                                'type': type_hint.strip()
                            })
                        else:
                            params.append({
                                'name': param,
                                'type': 'str'
                            })

            # Detect output count (out_amt = N)
            out_amt_match = re.search(r'out_amt\s*=\s*(\d+)', latest_blockly_code)
            out_amt = int(out_amt_match.group(1)) if out_amt_match else 0

            # Update visibility + clear output fields
            output_updates = []
            for i, field in enumerate(output_fields):
                if i < out_amt:
                    output_updates.append(gr.update(visible=True, label=f"Output {i+1}", value=""))
                else:
                    output_updates.append(gr.update(visible=False, value=""))

            # Update visibility + clear input fields
            updates = []
            for i, field in enumerate(input_fields):
                if i < len(params):
                    param = params[i]
                    updates.append(gr.update(
                        visible=True,
                        label=f"{param['name']} ({param['type']})",
                        value=""
                    ))
                else:
                    updates.append(gr.update(visible=False, value=""))

            return updates + output_updates

        def process_input(*args):
            result = execute_blockly_logic(args)

            # If the result is a tuple or list, pad it to length 10
            if isinstance(result, (tuple, list)):
                return list(result) + [""] * (10 - len(result))
            # If it's a single value, repeat it in the first slot and pad the rest
            return [result] + [""] * 9

        # When refresh is clicked, update input field visibility and labels
        refresh_btn.click(
            refresh_inputs,
            outputs=input_fields + output_fields,
            queue=False
        )
        
        submit_btn.click(
            process_input,
            inputs=input_fields,
            outputs=output_fields
        )

    return demo


demo = build_interface()
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    print("[BOOT] Running Gradio+FastAPI combo on http://127.0.0.1:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
