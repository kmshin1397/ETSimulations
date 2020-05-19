import queue
import subprocess
import time
import threading
import requests
import logging

logger = logging.getLogger(__name__)


def load_model_from_source(model_file, volume_id, commands):
    commands.append('open #%d %s' % (volume_id, model_file))
    return volume_id


def run_commands(commands, port, server_lock):
    server_lock.acquire()
    base_request = "http://localhost:%d/run" % port

    for c in commands:
        logger.info("Making request: " + c)
        requests.get(base_request, params={'command': c})

    # Clean up
    requests.get(base_request, params={'command': 'close session'})
    server_lock.release()


class ChimeraCommandSet:
    """ Represents a package of Chimera commands to be sent to the Chimera REST Servers.

    The object has access to an acknowledge event from the Chimera server process so that it can
    send the commands off and wait for notification that the commands were received and sent along
    to the server.

    Attributes:
        commands: The list of Chimera commands to send along to the server
        pid: The process ID of the subprocess requesting the Chimera commands so that the server can
            notify the proper subprocess upon completion
        ack_event: The event which will be set by the Chimera server upon completion of command
            requests

    """
    def __init__(self, commands, pid, ack_event):
        self.commands = commands

        # The process ID of the subprocess requesting the Chimera commands so that the server can
        # notify the proper subprocess upon completion
        self.pid = pid

        # The event which will be set by the Chimera server upon completion of command requests
        self.ack_event = ack_event

    def send_and_wait(self, commands_queue):
        """
        Sends a list of Chimera commands to the main Chimera server process, which will
            eventually pull it from the queue and make the HTTP request to the Chimera REST server.
            This function will wait until the HTTP request is made before returning.

        Args:
            commands_queue: The multiprocessing queue to put the package of commands into, passed in
                from the main function which spawned both the Chimera server process and the
                simulation subprocess.

        Returns: None

        """
        logger.info("Queueing up Chimera requests")
        commands_queue.put((self.pid, self.commands))
        self.ack_event.wait()
        logger.info("Received server acknowledgement")


class ChimeraServer:
    """ Class representing a Chimera REST Server process.

    Uses the Python subprocess module to start Chimera as a REST server, and maintains the localhost
        port number the Chimera server is running at.

    Attributes:
        port: The localhost port number the Chimera server is running at
        process: The subprocess object for the Chimera server process
        chimera_exec_path: The path to the Chimera program executable to run

    """
    def __init__(self, chimera_exec_path):
        self.port = None
        self.process = None
        self.chimera_exec_path = chimera_exec_path

    def quit(self):
        """
        Terminate the Chimera server process

        Returns: None

        """
        logger.info("Shutting down Chimera server")
        # If the server has been started, terminate it
        if self.process is not None:
            self.process.terminate()
            logger.info("Chimera server shut down successfully")

    def get_port(self):
        """
        Get the Chimera server port number

        Returns: The port number

        """
        return self.port

    @staticmethod
    def __output_reader(proc, outq):
        for line in iter(proc.stdout.readline, b''):
            outq.put(line.decode('utf-8'))
            break  # Only need to read the one line for the port

    def start_chimera_server(self):
        """
        Start the Chimera REST Server as a subprocess, reading its output to figure out what port it
            lies at

        Returns: None

        """
        port = -1
        # Need to provide executable path because subprocess does not know about aliases
        command = self.chimera_exec_path + ' --start RESTServer'
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
                time.sleep(0.5)
                continue
        t.join()

        self.process = proc
        self.port = port
        logger.info("REST Server started on port %d" % self.port)
