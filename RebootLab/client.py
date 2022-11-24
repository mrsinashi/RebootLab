import socket
import requests
import json

port = 9184
service_name = "redis"
api_key = "+<9AkQNWb8_"

req = dict(service_name=service_name, api_key=api_key)
json_file = json.dumps(req)

response = requests.post(f"http://192.168.50.253:{port}", json=req)
