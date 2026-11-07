'''
Interactive SCPI REPL.

Type SCPI commands at the prompt and they're sent to the connected instrument. Anything containing a '?' is sent as
a query and the response is printed; everything else is a plain write. Lines starting with '/' are REPL commands:

    /list  [-q]                 List VISA instruments on the network (-q skips the *IDN? lookup)
    /scan  [subnet] [ports]     Scan for instruments listening on raw TCP SCPI ports (e.g. 5025, 5555)
    /connect <n | resource>     Connect by number from the device table, or by a full VISA resource string / IP[:port]
    /disconnect                 Close the current connection
    /devices                    Show the device table again
    /timeout [ms]               Show or set the I/O timeout
    /read                       Read one more response (useful after a write that produces output)
    /menu  or  /help            Show the menu
    /quit                       Exit (Ctrl-D works too)

Backends: like bode.py, discovery uses the pyvisa-py ('@py') backend, since NI-VISA doesn't enumerate correctly on
macOS Tahoe. Connections try NI-VISA ('@ivi') first and fall back to '@py'. Use --backend to force one.

Socket scan: many instruments (Keysight, Siglent, Rigol) also listen on a raw SCPI socket that VISA discovery doesn't
advertise. /scan probes every host on the subnet for those ports, sends *IDN?, and adds responders to the device
table as TCPIP::<ip>::<port>::SOCKET resources.

Examples:
    python scpi_repl.py
    python scpi_repl.py --connect TCPIP::192.168.1.22::INSTR
    python scpi_repl.py --backend @py
'''

import argparse
import ipaddress
import os
import socket
import sys
from concurrent.futures import ThreadPoolExecutor

import pyvisa

try:
    import readline  # Gives arrow-key editing and history for input()
except ImportError:
    readline = None

HISTORY_FILE = os.path.expanduser('~/.scpi_repl_history')
DEFAULT_TIMEOUT_MS = 5000
# 5025: Keysight/Agilent/Siglent standard SCPI socket. 5555: Rigol. 5024: Keysight telnet-style SCPI.
DEFAULT_SCAN_PORTS = [5025, 5555, 5024]
SCAN_CONNECT_TIMEOUT_S = 0.3
SCAN_IDN_TIMEOUT_S = 1.0

MENU = '''
SCPI REPL commands
  1) /list [-q]               List VISA instruments on the network
  2) /connect <n|resource>    Connect to a device (number from table, VISA resource, or IP[:port])
     /disconnect              Disconnect from the current device
  3) /scan [subnet] [ports]   Scan for raw-socket SCPI devices, e.g. /scan 192.168.1.0/24 5025,5555
     /devices                 Show the device table
     /timeout [ms]            Show or set I/O timeout
     /read                    Read one pending response
     /menu                    Show this menu
     /quit                    Exit
Anything else is sent to the connected device. Lines containing '?' are queries.
'''


class ScpiRepl:
    def __init__(self, backend=None, timeout_ms=DEFAULT_TIMEOUT_MS):
        self.backend = backend
        self.timeout_ms = timeout_ms
        self.devices = []          # list of dicts: {'resource': str, 'idn': str, 'source': 'visa'|'scan'}
        self.inst = None
        self.inst_resource = None
        self._managers = {}

    # ----- VISA helpers -----

    def resource_manager(self, backend):
        if backend not in self._managers:
            self._managers[backend] = pyvisa.ResourceManager(backend)
        return self._managers[backend]

    def connect_backends(self):
        if self.backend:
            return [self.backend]
        return ['@ivi', '@py']

    def open_resource(self, resource):
        '''Open a resource, trying each backend in turn. Returns (instrument, backend).'''
        errors = []
        for backend in self.connect_backends():
            try:
                rm = self.resource_manager(backend)
                inst = rm.open_resource(resource)
                inst.timeout = self.timeout_ms
                if resource.upper().endswith('::SOCKET'):
                    # Raw sockets have no message framing, so terminations are required.
                    inst.read_termination = '\n'
                    inst.write_termination = '\n'
                return inst, backend
            except Exception as e:  # backend missing (OSError/ValueError) or VisaIOError
                errors.append(f'{backend}: {e}')
        raise ConnectionError('; '.join(errors))

    # ----- Commands -----

    def cmd_list(self, args):
        query_idn = '-q' not in args
        discovery_backend = self.backend or '@py'
        print(f'Searching for VISA instruments ({discovery_backend})...')
        # The 'TCPIP?*' pattern restricts discovery to the network (no serial/USB probing). The VXI-11 broadcast
        # behind it occasionally misses replies, so take the union of two passes.
        found = set()
        try:
            rm = self.resource_manager(discovery_backend)
            for _ in range(2):
                found.update(rm.list_resources('TCPIP?*'))
        except Exception as e:
            print(f'Discovery failed: {e}')
            if not found:
                return
        found = [r for r in found if r.upper().endswith('::INSTR')]
        # Keep socket devices from a previous scan; replace VISA ones.
        self.devices = [d for d in self.devices if d['source'] != 'visa']
        for r in sorted(found):
            idn = ''
            if query_idn:
                idn = self.probe_idn(r)
            self.devices.append({'resource': r, 'idn': idn, 'source': 'visa'})
        if not found:
            print('No VISA network instruments found. Try /scan for raw-socket devices.')
        self.cmd_devices([])

    def probe_idn(self, resource):
        try:
            inst, _ = self.open_resource(resource)
        except Exception as e:
            return f'(could not open: {e})'
        try:
            inst.timeout = min(self.timeout_ms, 2000)
            return inst.query('*IDN?').strip()
        except Exception as e:
            return f'(no *IDN? response: {e})'
        finally:
            try:
                inst.close()
            except Exception:
                pass

    def cmd_scan(self, args):
        subnet = None
        ports = DEFAULT_SCAN_PORTS
        for a in args:
            if '/' in a or a.count('.') == 3:
                subnet = a
            else:
                try:
                    ports = [int(p) for p in a.split(',') if p]
                except ValueError:
                    print(f'Bad port list: {a}')
                    return
        if subnet is None:
            local_ip = guess_local_ip()
            if local_ip is None:
                print('Could not determine local IP. Pass a subnet, e.g. /scan 192.168.1.0/24')
                return
            subnet = f'{local_ip}/24'
        try:
            network = ipaddress.ip_network(subnet, strict=False)
        except ValueError as e:
            print(f'Bad subnet: {e}')
            return
        if network.num_addresses > 4096:
            print(f'{network} is too large to scan ({network.num_addresses} addresses). Use /22 or smaller.')
            return

        hosts = [str(h) for h in network.hosts()] or [str(network.network_address)]
        targets = [(h, p) for h in hosts for p in ports]
        print(f'Scanning {network} on port(s) {",".join(map(str, ports))} ({len(targets)} probes)...')
        with ThreadPoolExecutor(max_workers=128) as pool:
            results = [r for r in pool.map(lambda t: probe_socket(*t), targets) if r]

        self.devices = [d for d in self.devices if d['source'] != 'scan']
        for ip, port, idn in sorted(results, key=lambda r: (ipaddress.ip_address(r[0]), r[1])):
            self.devices.append({'resource': f'TCPIP::{ip}::{port}::SOCKET', 'idn': idn, 'source': 'scan'})
        print(f'Found {len(results)} socket endpoint(s).')
        self.cmd_devices([])

    def cmd_devices(self, args):
        if not self.devices:
            print('Device table is empty. Use /list or /scan.')
            return
        width = max(len(d['resource']) for d in self.devices)
        for i, d in enumerate(self.devices, 1):
            marker = '*' if d['resource'] == self.inst_resource else ' '
            print(f'{marker}{i:2d}) {d["resource"]:<{width}}  {d["idn"]}')

    def cmd_connect(self, args):
        if not args:
            print('Usage: /connect <n | resource | ip[:port]>')
            return
        target = args[0]
        if target.isdigit():
            n = int(target)
            if not 1 <= n <= len(self.devices):
                print(f'No device #{n}. Use /devices to see the table.')
                return
            resource = self.devices[n - 1]['resource']
        elif '::' in target:
            resource = target
        elif ':' in target:
            ip, port = target.rsplit(':', 1)
            resource = f'TCPIP::{ip}::{port}::SOCKET'
        else:
            resource = f'TCPIP::{target}::INSTR'

        if self.inst is not None:
            self.cmd_disconnect([])
        try:
            inst, backend = self.open_resource(resource)
        except ConnectionError as e:
            print(f'Could not connect to {resource}: {e}')
            return
        self.inst = inst
        self.inst_resource = resource
        print(f'Connected to {resource} via {backend}')
        try:
            print(f'  {inst.query("*IDN?").strip()}')
        except Exception as e:
            print(f'  (*IDN? failed: {e})')

    def cmd_disconnect(self, args):
        if self.inst is None:
            print('Not connected.')
            return
        try:
            self.inst.close()
        except Exception as e:
            print(f'Error while closing: {e}')
        print(f'Disconnected from {self.inst_resource}')
        self.inst = None
        self.inst_resource = None

    def cmd_timeout(self, args):
        if args:
            try:
                self.timeout_ms = int(args[0])
            except ValueError:
                print('Usage: /timeout <milliseconds>')
                return
            if self.inst is not None:
                self.inst.timeout = self.timeout_ms
        print(f'Timeout: {self.timeout_ms} ms')

    def cmd_read(self, args):
        if self.inst is None:
            print('Not connected.')
            return
        try:
            print(self.inst.read().rstrip())
        except pyvisa.VisaIOError as e:
            print(f'Read failed: {e}')

    def cmd_menu(self, args):
        print(MENU)

    # ----- REPL loop -----

    COMMANDS = {
        'list': 'cmd_list', '1': 'cmd_list',
        'connect': 'cmd_connect', '2': 'cmd_connect',
        'scan': 'cmd_scan', '3': 'cmd_scan',
        'disconnect': 'cmd_disconnect', 'devices': 'cmd_devices',
        'timeout': 'cmd_timeout', 'read': 'cmd_read',
        'menu': 'cmd_menu', 'help': 'cmd_menu', '?': 'cmd_menu',
    }

    def prompt(self):
        if self.inst_resource:
            return f'scpi [{self.inst_resource}]> '
        return 'scpi [not connected]> '

    def send_scpi(self, line):
        if self.inst is None:
            print('Not connected. Use /list or /scan, then /connect <n>. Type /menu for help.')
            return
        try:
            if '?' in line:
                print(self.inst.query(line).rstrip())
            else:
                self.inst.write(line)
        except pyvisa.VisaIOError as e:
            print(f'I/O error: {e}')

    def handle(self, line):
        '''Handle one line of input. Returns False when the REPL should exit.'''
        line = line.strip()
        if not line:
            return True
        if not line.startswith('/'):
            self.send_scpi(line)
            return True
        name, *args = line[1:].split()
        if name in ('quit', 'exit', 'q'):
            return False
        method = self.COMMANDS.get(name.lower())
        if method is None:
            print(f'Unknown command /{name}. Type /menu for help.')
        else:
            getattr(self, method)(args)
        return True

    def run(self):
        print(MENU)
        while True:
            try:
                line = input(self.prompt())
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()  # Ctrl-C cancels the current line, not the REPL
                continue
            try:
                if not self.handle(line):
                    break
            except KeyboardInterrupt:
                print('\nInterrupted.')
        if self.inst is not None:
            self.cmd_disconnect([])


def guess_local_ip():
    '''Find the IP of the interface used for outbound traffic. No packets are sent by a UDP connect().'''
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def probe_socket(ip, port):
    '''Return (ip, port, idn) if something accepts TCP on ip:port, else None.'''
    try:
        with socket.create_connection((ip, port), timeout=SCAN_CONNECT_TIMEOUT_S) as s:
            s.settimeout(SCAN_IDN_TIMEOUT_S)
            idn = ''
            try:
                s.sendall(b'*IDN?\n')
                data = b''
                while not data.endswith(b'\n') and len(data) < 1024:
                    chunk = s.recv(1024)
                    if not chunk:
                        break
                    data += chunk
                idn = data.decode(errors='replace').strip()
            except OSError:
                pass
            return ip, port, idn or '(port open, no *IDN? response)'
    except OSError:
        return None


def main():
    parser = argparse.ArgumentParser(description='Interactive SCPI REPL for network instruments.')
    parser.add_argument('--backend', help="Force a pyvisa backend, e.g. '@py' or '@ivi' (default: try @ivi then @py)")
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT_MS, help='I/O timeout in ms')
    parser.add_argument('--connect', metavar='RESOURCE', help='Connect to this resource (or IP[:port]) on startup')
    args = parser.parse_args()

    if readline is not None:
        try:
            readline.read_history_file(HISTORY_FILE)
        except (FileNotFoundError, OSError):
            pass

    repl = ScpiRepl(backend=args.backend, timeout_ms=args.timeout)
    if args.connect:
        repl.cmd_connect([args.connect])
    try:
        repl.run()
    finally:
        if readline is not None:
            try:
                readline.set_history_length(1000)
                readline.write_history_file(HISTORY_FILE)
            except OSError:
                pass


if __name__ == '__main__':
    sys.exit(main())
