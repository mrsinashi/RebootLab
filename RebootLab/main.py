from fastapi import FastAPI
from pydantic import BaseModel
import socket
import json
import subprocess
from datetime import datetime


api_key = "+<9AkQNWb8_"
ip_adress = socket.gethostbyname(socket.gethostname())
log_file = "/var/log/RebootLab.log"
env_file = ".env"
port = 9185


class request(BaseModel):
    service_name: str
    action: str | None = None
    api_key: str


app = FastAPI()


@app.post("/")
async def recieve_post(request: request):
    if request.api_key == api_key:
        service = get_servname_from_dict(json_file['service_name'])

        if service != -1:
            match request.action:
                case 'status':
                    code, json_response = service_status(service)
                case 'restart' | 'start':
                    code, json_response = service_restart(service)
                case 'stop' | 'kill':
                    code, json_response = service_kill(service)
                case _:
                    log_write("ERROR", "Wrong action")
                    print("[ERROR] Wrong action\n")
            json_response = json.dumps(json_response)
            self._send_response(code, json_response)
        else:
            log_write("ERROR", "Unknown service name")
            self._send_response(404)
            print("[ERROR] Unknown service name\n")
    else:
        log_write("ERROR", "Invalid API key")
        self._send_response(401)
        print("[ERROR] Invalid API key\n")
    return request
