import socket
import json

port = 9183
service_name = "redis"
secure_key = "]<9A'QNWb8_"

sock = socket.socket()
sock.connect(('localhost', port))

req = dict(service_name=service_name, secure_key=secure_key)
sock.send(json.dumps(req).encode('utf-8'))
data = sock.recv(1024)

print(str(data))

sock.close()
