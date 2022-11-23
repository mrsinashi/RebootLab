import socket
import requests
import json

port = 9184
service_name = "redis"
secure_key = "]<9A(QNWb8_"

req = dict(service_name=service_name, secure_key=secure_key)
json_file = json.dumps(req)

response = requests.post(f"http://127.0.0.1:{port}", json=req)
