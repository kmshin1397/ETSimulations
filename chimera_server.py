import queue
import subprocess
import time
import threading


def load_model_from_source(model_file, volume_id, commands):
    commands.append('open #%d %s' % (volume_id, model_file))
    return volume_id


def output_reader(proc, outq):
    for line in iter(proc.stdout.readline, b''):
        outq.put(line.decode('utf-8'))
        break  # Only need to read the one line for the port


def start_chimera_server():
    port = -1
    chimera_exec_path = '/usr/sbin/chimera'
    command = chimera_exec_path + ' --start RESTServer'

    proc = subprocess.Popen(command.split(),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    outq = queue.Queue()
    t = threading.Thread(target=output_reader, args=(proc, outq))
    t.start()

    time.sleep(0.5)

    while True:
        try:
            line = outq.get(block=False)
            port = int(line.split("REST server on host 127.0.0.1 port ")[1])
            break
        except queue.Empty:
            time.sleep(0.5)
            continue
    t.join()

    return proc, port
