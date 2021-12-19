#!/usr/bin/env python3

from evdev import InputDevice, ecodes as e, categorize, UInput, list_devices
import os
from socket import socket, AF_UNIX, SOCK_STREAM
import sys
from threading import Lock, Thread
import time

# The name assigned to the emulated keyboard
UINPUT_NAME = 'Plover'
# The path of the unix domain socket interface
UDS_PATH = '/var/plover-evdevd'


# When run, there will be two threads.
# One thread (listen_kb) will wait for keyboard events, and either pass them on to uinput, or intercept them and pass them to the UDS.
# The other thread (listen_uds) will wait for commands on the socket, and potentially send keys to uinput.

# The shared resources that require locks are: uinput.
# Assigning to the set of keys to intercept does not require a lock as it is only assigned to by the listen_uds thread, and said writes are atomic.
# Writing to the UDS only occurs in the listen_kb thread.

# Communication happens over a Unix Domain Socket at `/var/plover-evdevd`.
# Each packet is a line, begining with a single char to indicate the packet type, and ending with a single newline character.
# The rest of the line is a space-separated list of args
# The packet types are: 's': suppress_keyboard, 'u': key_up, 'd': key_down


uinput = None
uinput_lock = Lock()

sock_conn = None
suppress_keys = set()


def is_keyboard(path):
    dev = InputDevice(path)
    try:
        if dev.name.startswith == UINPUT_NAME:
            return False
        cap = dev.capabilities()
        return (e.EV_KEY in cap and
                e.KEY_A in cap[e.EV_KEY])
    finally:
        dev.close()


def find_first_keyboard():
    path = next(filter(is_keyboard, list_devices()), None)
    if not path:
        sys.exit('No keyboards found')
    return path


def write_key(name, value):
    with uinput_lock:
        uinput.write(e.EV_KEY, int(name), value)
        uinput.syn()


def listen_kb():
    global sock_conn, suppress_keys, uinput, uinput_lock

    try:
        # Delay startup to allow existing keys to be released
        time.sleep(0.5)

        path = find_first_keyboard()
        dev = InputDevice(path)
        dev.grab()
        print('Using device:', path, dev.name)

        uinput = UInput.from_device(dev)

        for event in dev.read_loop():
            if event.type == e.EV_KEY and event.code in suppress_keys:
                if event.value:
                    sock_conn.write('d')
                else:
                    sock_conn.write('u')
                sock_conn.write(str(event.code))
                sock_conn.write('\n')
                sock_conn.flush()

            elif event.type != e.EV_SYN:
                with uinput_lock:
                    uinput.write_event(event)
                    uinput.syn()

        time.sleep(1)

    finally:
        dev.ungrab()

        with uinput_lock:
            uinput.close()
            uinput = None

        dev.close()
        dev = None


def listen_uds():
    global sock_conn, suppress_keys, uinput, uinput_lock

    try:
        os.unlink(UDS_PATH)
    except OSError:
        if os.path.exists(UDS_PATH):
            raise

    sock = socket(AF_UNIX, SOCK_STREAM)
    sock.bind(UDS_PATH)
    # TODO: restrict access to the keylogger, maybe
    os.chmod(UDS_PATH, 0o777)
    sock.listen()
    print('Listening on:', UDS_PATH)

    while True:
        conn, _ = sock.accept()
        with conn:
            sock_conn = conn.makefile('rw')
            while True:
                try:
                    line = sock_conn.readline()
                    if len(line) <= 1:
                        break
                    first_char = line[0]
                    content = line[1:-1]
                    if first_char == 'u':
                        write_key(content, 0)
                    elif first_char == 'd':
                        write_key(content, 1)
                    elif first_char == 's':
                        suppress_keys = set(map(int, content.split()))
                        print('Supressing keys:', suppress_keys)
                except Exception as e:
                    print(e)


listen_kb_thread = Thread(target=listen_kb)
listen_uds_thread = Thread(target=listen_uds)

listen_kb_thread.start()
listen_uds_thread.start()
