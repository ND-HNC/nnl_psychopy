"""Serial to Keyboard bridge module.

Converts serial port input into virtual keyboard typing events.

Examples:
    # As a module import:
    from serial_keyboard import SerialKeyboard

    sk = SerialKeyboard(port="/dev/ttyUSB0", baud_rate=9600)
    sk.listen()

    # As a CLI tool:
    python -m serial_keyboard --get-ports
    python -m serial_keyboard --port /dev/ttyUSB0 --baud 9600

"""

from __future__ import annotations

from argparse import ArgumentParser, RawTextHelpFormatter
import glob
import sys
from typing import List, Optional

from pynput.keyboard import Controller, Key
import serial


def list_ports() -> List[str]:
    """Find all openable serial ports on the current platform.

    Returns:
        List[str]: A list of available serial port names.

    Raises:
        EnvironmentError: If run on an unsupported operating system platform.
    """
    if sys.platform.startswith("win"):
        ports = [f"COM{i + 1}" for i in range(256)]
    elif sys.platform.startswith("linux") or sys.platform.startswith("cygwin"):
        ports = glob.glob("/dev/tty[A-Za-z]*")
    elif sys.platform.startswith("darwin"):
        ports = glob.glob("/dev/tty.*")
    else:
        raise EnvironmentError("Unsupported platform")

    result = []
    for port in ports:
        try:
            connection = serial.Serial(port)
            connection.close()
            result.append(port)
        except (OSError, Exception):
            pass
    return result


class SerialKeyboard:
    """Manages serial connection and translates incoming ASCII lines.

    Attributes:
        port (str): Serial port name (e.g., '/dev/ttyUSB0' or 'COM3').
        baud_rate (int): Baud rate for communication (default: 9600).
        timeout (float): Serial connection read timeout in seconds.
    """

    def __init__(
        self, port: str, baud_rate: int = 9600, timeout: float = 1.0
    ) -> None:
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.keyboard = Controller()
        self._connection: Optional[serial.Serial] = None

    def connect(self) -> serial.Serial:
        """Establish connection to specified serial port.

        Returns:
            serial.Serial: Active serial connection object.
        """
        try:
            print(
                f"Attempting to connect to port={self.port}, "
                f"baud={self.baud_rate} ..."
            )
            self._connection = serial.Serial(
                self.port, self.baud_rate, timeout=self.timeout
            )
            print("Connected!")
            return self._connection
        except Exception as error:
            print(
                f"ERROR: Failed to connect to port={self.port}, "
                f"baud={self.baud_rate}"
            )
            raise error

    def listen(self) -> None:
        """Listen continuously for incoming serial data and type characters."""
        if not self._connection or not self._connection.is_open:
            self.connect()

        try:
            while self._connection and self._connection.is_open:
                if self._connection.in_waiting > 0:
                    rx_line = (
                        self._connection.readline().decode("ascii").strip()
                    )
                    self.keyboard.type(rx_line)
                    self.keyboard.press(Key.enter)
                    self.keyboard.release(Key.enter)
        except Exception:
            print("Connection lost")
        finally:
            self.close()

    def close(self) -> None:
        """Close serial connection safely."""
        if self._connection and self._connection.is_open:
            self._connection.close()
            print("Serial connection closed.")


def _get_args() -> ArgumentParser:
    """Get and parse CLI arguments."""
    parser = ArgumentParser(
        description=__doc__, formatter_class=RawTextHelpFormatter
    )
    parser.add_argument(
        "--baud",
        default=9600,
        help="Baud rate (default: %(default)s).",
        type=int,
    )
    parser.add_argument(
        "--get-ports",
        action="store_true",
        help="List available system serial ports.",
    )
    parser.add_argument(
        "--port",
        help="Target serial port name.",
        type=str,
    )

    if len(sys.argv) <= 1:
        parser.print_help(sys.stderr)
        sys.exit(0)

    return parser


def main() -> None:
    """CLI entrypoint."""
    parser = _get_args()
    args = parser.parse_args()

    if args.get_ports:
        detected = list_ports()
        print(f"List of detected ports: {' '.join(detected)}")
        return

    if not args.port:
        parser.print_help(sys.stderr)
        sys.exit(1)

    sk = SerialKeyboard(port=args.port, baud_rate=args.baud)
    sk.listen()


if __name__ == "__main__":
    main()
