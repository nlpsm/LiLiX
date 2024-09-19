from fastapi import FastAPI, HTTPException
import subprocess

app = FastAPI()

def run_bash_command(cmd):
    process = subprocess.Popen(["/bin/bash", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    return stdout, stderr

@app.get("/run")
def run_command(command: str):
    if not command:
        raise HTTPException(status_code=400, detail="Command cannot be empty")
    stdout, stderr = run_bash_command(command)
    return {"stdout": stdout.decode(), "stderr": stderr.decode()}
