"""Convert serial input to keyboard.

Create PsychoPy code object, call for script via:
    os.system("python serial_keyboard.py --port /dev/tty")

Sources:
    - https://github.com/Robotto/serial2keyboard/blob/master/serial2keyboard.py
    - https://discourse.psychopy.org/t/nnl-syncbox-for-mri-trigger-input/4297/11

Examples:
    python serial2keyboard.py --get-ports
    python serial2keyboard.py --port /dev/tty.*
    python serial2keyboard.py --port /dev/tty.* --baud 8400

"""

import sys
import glob
from argparse import ArgumentParser, RawTextHelpFormatter
import serial
from pynput.keyboard import Key, Controller


def _get_args():
    """Get and parse arguments."""
    parser = ArgumentParser(
        description=__doc__, formatter_class=RawTextHelpFormatter
    )
    parser.add_argument(
        "--baud",
        default=9600,
        help="Baud rate (default : %(default)s).",
        type=int,
    )
    parser.add_argument(
        "--get-ports",
        action="store_true",
        help="Caculate topo metrics for each subject",
    )
    parser.add_argument(
        "--port",
        help="Port name",
        type=str,
    )

    if len(sys.argv) <= 1:
        parser.print_help(sys.stderr)
        sys.exit(0)

    return parser


def _list_ports() -> list:
    """Finds all serial ports and returns a list containing them.

    Raise:
        EnvironmentError: Unexpected system platform.

    """
    if sys.platform.startswith("win"):
        ports = ["COM%s" % (i + 1) for i in range(256)]
    elif sys.platform.startswith("linux") or sys.platform.startswith("cygwin"):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob("/dev/tty[A-Za-z]*")
    elif sys.platform.startswith("darwin"):
        ports = glob.glob("/dev/tty.*")
    else:
        raise EnvironmentError("Unsupported platform")

    # Build list of ports sucessfully opened
    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, Exception):
            pass
    return result


def _serial_connect(serial_port: str, baud_rate: int) -> serial.Serial:
    """Connect to serial device and return connection."""
    try:
        serial_cx = serial.Serial(serial_port, baud_rate, timeout=1)
    except Exception as error:
        print(
            f"ERROR: Failed to connect to port={serial_port}, baud={baud_rate}"
        )
        raise error
    return serial_cx


def main():
    """Get input and trigger work."""

    # Get user input
    g_args = _get_args()
    args = g_args.parse_args()

    # Evaluate user input
    if args.get_ports:
        print(f"List of detected ports: {' '.join(_list_ports())}")
        return

    if not args.port:
        g_args.print_help(sys.stderr)
        sys.exit(1)

    # Start connection
    baud_rate = args.baud
    serial_port = args.port
    print(f"Attempting to connect to port={serial_port}, baud={baud_rate} ...")
    serial_cx = _serial_connect(serial_port, baud_rate)

    # Get keyboard
    keyboard = Controller()
    try:
        while serial_cx.is_open:
            if serial_cx.in_waiting > 0:
                rx_line = serial_cx.readline().decode("ascii").strip()
                keyboard.type(rx_line)
                keyboard.press(Key.enter)
                keyboard.release(Key.enter)
    except Exception as error:
        print("ERROR: Missing keyboard controller.")
        raise error


if __name__ == "__main__":
    main()
