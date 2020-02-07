import queue
import subprocess
import time
import threading
import requests


def load_model_from_source(model_file, volume_id, commands):
    commands.append('open #%d %s' % (volume_id, model_file))
    return volume_id


def run_commands(commands, port, server_lock):
    server_lock.acquire()
    base_request = "http://localhost:%d/run" % port

    for c in commands:
        print("Making request: " + c)
        requests.get(base_request, params={'command': c})

    # Clean up
    requests.get(base_request, params={'command': 'close session'})
    server_lock.release()


class ChimeraServer:
    def __init__(self):
        self.port = None
        self.process = None

    def quit(self):
        # If the server has been started, terminate it
        if self.process is not None:
            self.process.terminate()

    @staticmethod
    def __output_reader(proc, outq):
        for line in iter(proc.stdout.readline, b''):
            outq.put(line.decode('utf-8'))
            break  # Only need to read the one line for the port

    def start_chimera_server(self):
        port = -1
        # Need to provide executable path because subprocess does not know about aliases
        # chimera_exec_path = '/usr/sbin/chimera'
        chimera_exec_path = "/Applications/Chimera.app/Contents/MacOS/chimera"
        command = chimera_exec_path + ' --start RESTServer'
        proc = subprocess.Popen(command.split(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        outq = queue.Queue()
        t = threading.Thread(target=self.__output_reader, args=(proc, outq))
        t.start()

        time.sleep(0.5)

        while True:
            try:
                line = outq.get(block=False)
                port = int(line.split("REST server on host 127.0.0.1 port ")[1])
                break
            except queue.Empty:
                # print("Sleeping")
                time.sleep(0.5)
                continue
        t.join()

        self.process = proc
        self.port = port
        print("REST Server started on port %d" % self.port)
