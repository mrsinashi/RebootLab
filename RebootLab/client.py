import socket
import requests
import json

port = 9185
service_name = "redis"
api_key = "+<9AkQNWb8_"
ip_adress = "10.0.2.15"

req = dict(service_name=service_name, api_key=api_key)
json_file = json.dumps(req)

response = requests.post(f"http://{ip_adress}:{port}", json=req)
