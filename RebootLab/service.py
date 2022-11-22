import subprocess

service = "redis"
command = f"sudo systemctl status {service} | grep -P '└─|├─'| sed 's/.*─//' | sed -r 's/ .+//' | sed 's/[^0-9]*//g'"

service_proc = subprocess.Popen([command], shell=True, stdout=subprocess.PIPE)
pids = service_proc.communicate(timeout=10)[0].decode('utf-8').split()

for pid in pids:
    print(f"PID {pid}: kill...")
    subprocess.Popen([f"sudo kill {pid}"], shell=True, stdout=subprocess.PIPE)

service_proc2 = subprocess.Popen([f"sleep 1; {command}"], shell=True, stdout=subprocess.PIPE)
pids2 = service_proc2.communicate(timeout=10)[0].decode('utf-8').split()

for pid2 in pids2:
    if pid in pids2:
        print(f"Error killing PID: {pid}")
