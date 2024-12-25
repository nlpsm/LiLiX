import os
import logging
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Initialize FastAPI
app = FastAPI()

# Configure logging
logging.basicConfig(
    filename="commands.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ----------------------------------------------------------------------------
# Pydantic models for each endpoint's request body
# ----------------------------------------------------------------------------
class ExecuteWithEnvRequest(BaseModel):
    command: str
    env: Optional[Dict[str, str]] = None

class AsyncExecuteRequest(BaseModel):
    command: str

class PipelineRequest(BaseModel):
    commands: List[str]

class LogExecuteRequest(BaseModel):
    command: str

class TemplateRequest(BaseModel):
    template_name: str
    params: Dict[str, str]

# ----------------------------------------------------------------------------
# 1) Execute Command with Optional Environment Variables
# ----------------------------------------------------------------------------
@app.post("/execute/env")
def execute_command_with_env(body: ExecuteWithEnvRequest):
    """
    Executes a command with optional environment variables.
    """
    command = body.command
    env = body.env or {}
    
    try:
        final_env = {**os.environ, **env}
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            env=final_env
        )
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as e:
        logging.error(f"Error executing command: {command}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# 2) Execute Command Asynchronously
# ----------------------------------------------------------------------------
@app.post("/execute/async")
async def execute_command_async(body: AsyncExecuteRequest):
    """
    Executes a command asynchronously and returns stdout/stderr upon completion.
    """
    command = body.command
    
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        return {
            "command": command,
            "returncode": process.returncode,
            "stdout": stdout.decode(),
            "stderr": stderr.decode(),
        }
    except Exception as e:
        logging.error(f"Async command error: {command}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# 3) Execute a Pipeline of Commands Sequentially
# ----------------------------------------------------------------------------
@app.post("/execute/pipeline")
def execute_command_pipeline(body: PipelineRequest):
    """
    Executes a list of commands in sequence, returning results for each.
    """
    commands = body.commands
    results = []
    for cmd in commands:
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            results.append({
                "command": cmd,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            })
        except Exception as e:
            logging.error(f"Pipeline command error: {cmd}, Error: {str(e)}")
            results.append({
                "command": cmd,
                "error": str(e)
            })
    return results

# ----------------------------------------------------------------------------
# 4) Execute Command and Stream Output in Real-Time
# ----------------------------------------------------------------------------
# Note: This does not require a complex schema if only streaming 'command'
@app.post("/execute/stream")
def execute_command_stream(command: str):
    """
    Executes a command and streams the stdout/stderr in real-time.
    
    This endpoint still uses a simple 'command: str' because streaming
    is a bit trickier to handle with advanced JSON bodies. Alternatively,
    define a small Pydantic model if you prefer a JSON object body.
    """
    try:
        def run_command():
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            # Stream stdout in real-time
            for line in iter(process.stdout.readline, ""):
                yield line
            # Stream stderr after stdout completes
            for line in iter(process.stderr.readline, ""):
                yield line

        return StreamingResponse(run_command(), media_type="text/plain")
    except Exception as e:
        logging.error(f"Stream command error: {command}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# 5) Execute Command with Logging (Timing and Return Codes)
# ----------------------------------------------------------------------------
@app.post("/execute/log")
def execute_command_with_logging(body: LogExecuteRequest):
    """
    Executes a command and logs details: command, start time, end time, return code, etc.
    """
    command = body.command
    start_time = datetime.now()
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        end_time = datetime.now()

        logging.info(
            f"Command: {command}, "
            f"Start: {start_time}, "
            f"End: {end_time}, "
            f"Returncode: {result.returncode}"
        )

        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }
    except Exception as e:
        logging.error(f"Logging command error: {command}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------------------------------
# 6) Execute Predefined Template Commands
# ----------------------------------------------------------------------------
templates = {
    "list_dir": "ls -la {path}",
    "grep_file": "grep '{pattern}' {file}",
    # Add more template strings as needed
}

@app.post("/execute/template")
def execute_command_template(body: TemplateRequest):
    """
    Executes a predefined command template with parameters.
    """
    template_name = body.template_name
    if template_name not in templates:
        raise HTTPException(status_code=404, detail="Template not found")

    command_str = templates[template_name].format(**body.params)
    try:
        result = subprocess.run(command_str, shell=True, capture_output=True, text=True)
        return {
            "command": command_str,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except Exception as e:
        logging.error(f"Template command error: {command_str}, Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

