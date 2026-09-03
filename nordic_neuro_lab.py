"""NordicNeuroLab SyncBox interface.

Refactored and added SyncBox.get_response().

Source:
    - https://github.com/nordicneurolab/py_syncbox

"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Tuple, Optional
from serial import Serial, SerialException
import serial.tools.list_ports


class GetGlobals(int, Enum):
    """Set globals for better references."""

    COMMAND_PAYLOAD_SIZE = 1  # Number of bytes to read from the SyncBox
    CONFIGURE_PAYLOAD_SIZE = 12 * 4  # 12 parameters, each 4 bytes (32 bits)
    MAX_PAYLOAD_SIZE = 64  # Maximum bytes to read in one go


class Trigger(bytes, Enum):
    """SyncBox trigger response signals."""

    TRIGGER = b"s"
    LEFT_THUMB = b"a"
    LEFT_INDEX = b"b"
    RIGHT_INDEX = b"c"
    RIGHT_THUMB = b"d"
    DUMMY_PAYLOAD = b"0000"


class Command(bytes, Enum):
    """SyncBox command byte protocols."""

    START = b"S"
    CONFIGURE = b"R"
    COMPUTER_MODE = b"C"
    STOP = b"A"
    MANUAL_MODE = b"D"


class SyncBoxException(Exception):
    """Custom exception raised for SyncBox connection or protocol errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        # return f"{COLOR_RED}SyncBoxException: {self.message}{COLOR_RESET}"
        return f"SyncBoxException: {self.message}"


@dataclass
class SyncBox:
    """Finds and establishes serial connection with the SyncBox.

    Args:
        num_volumes: Number of volumes.
        num_slices: Number of slices in each volume.
        trigger_slice: Slice number to trigger on.
        trigger_volume: How often to trigger on a volume.
        pulse_length: Pulse length in ms (simulation mode).
        tr_time: TR time in ms (simulation mode).
        optional_trigger_slice: 0=specific, 1=each, 2=random slice.
        optional_trigger_volume: 0=specific, 1=each, 2=random volume.
        simulation: False for synchronization mode, True for simulation mode.
        serial_port: Serial port device name. If None,
            auto-detects available ports.
        baud_rate: Baud rate for serial communication (default: 57600).
        timeout: Serial communication timeout in seconds (default: 0.5s).
        manual_mode: True for manual sync, False for computer mode.
    """

    num_volumes: int = 16
    num_slices: int = 1
    trigger_slice: int = 1
    trigger_volume: int = 1
    pulse_length: int = 100
    tr_time: int = 3000
    optional_trigger_slice: int = 0
    optional_trigger_volume: int = 0
    simulation: bool = False
    serial_port: Optional[str] = None
    baud_rate: int = 57600
    timeout: float = 0.5
    manual_mode: bool = False
    _ser: Optional[Serial] = field(init=False, default=None)

    def __post_init__(self) -> None:
        try:
            if self.serial_port is None:
                self.serial_port = self._find_sync_box()
            if not self.serial_port:
                raise SyncBoxException("SyncBox not found.")

            self._ser = Serial(
                self.serial_port, self.baud_rate, timeout=self.timeout
            )
            print(f"Connected to SyncBox on {self.serial_port}")
        except Exception as error:
            raise SyncBoxException(
                f"Failed to connect to SyncBox on {self.serial_port}: {error}"
            ) from error

        try:
            print("Checking communication with SyncBox.")

            payload = (
                Trigger.DUMMY_PAYLOAD
                + self.int_to_bytes(self.num_volumes)
                + self.int_to_bytes(self.num_slices)
                + self.int_to_bytes(self.pulse_length)
                + self.int_to_bytes(self.tr_time)
                + self.int_to_bytes(self.trigger_slice)
                + self.int_to_bytes(self.trigger_volume)
                + Trigger.DUMMY_PAYLOAD
                + Trigger.DUMMY_PAYLOAD
                + self.int_to_bytes(self.optional_trigger_slice)
                + self.int_to_bytes(self.optional_trigger_volume)
                + self.int_to_bytes(0 if self.simulation else 1)
            )

            if not self._send_command(
                Command.COMPUTER_MODE, GetGlobals.COMMAND_PAYLOAD_SIZE
            ):
                raise SyncBoxException(
                    "Failed to enter computer mode on SyncBox."
                )

            if not self._send_command(
                Command.CONFIGURE, GetGlobals.COMMAND_PAYLOAD_SIZE
            ):
                raise SyncBoxException(
                    "Failed to send configure command to SyncBox."
                )

            if not self._send_command(
                payload, GetGlobals.CONFIGURE_PAYLOAD_SIZE
            ):
                raise SyncBoxException(
                    "Failed to send configuration to SyncBox."
                )

            if self.manual_mode:
                if not self._send_command(
                    Command.MANUAL_MODE, GetGlobals.COMMAND_PAYLOAD_SIZE
                ):
                    raise SyncBoxException(
                        "Failed to enter manual mode on SyncBox."
                    )

        except Exception as error:
            self.close()
            raise SyncBoxException(
                f"Failed to configure SyncBox: {error}"
            ) from error

        self.print_configuration()
        print("SyncBox configured successfully.")

    def __enter__(self) -> SyncBox:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    def start(self) -> None:
        """Start a SyncBox synchronization or simulation session."""
        try:
            if not self._send_command(
                Command.START, GetGlobals.COMMAND_PAYLOAD_SIZE
            ):
                raise SyncBoxException("Failed to start SyncBox session.")
        except Exception as error:
            self.close()
            raise SyncBoxException(
                f"Failed to start SyncBox session: {error}"
            ) from error

        print("SyncBox session started.")

    def stop(self) -> None:
        """Stop an ongoing SyncBox synchronization or simulation session."""
        try:
            if not self._send_command(
                Command.STOP, GetGlobals.COMMAND_PAYLOAD_SIZE
            ):
                raise SyncBoxException("Failed to stop SyncBox session.")
        except Exception as error:
            self.close()
            raise SyncBoxException(
                f"Failed to stop SyncBox session: {error}"
            ) from error

        print("SyncBox session stopped.")

    def close(self) -> None:
        """Close serial port connection and turn off SyncBox Computer Mode."""
        if self._ser and self._ser.is_open:
            try:
                self._send_command(
                    Command.MANUAL_MODE, GetGlobals.COMMAND_PAYLOAD_SIZE
                )
                self._ser.close()
                print("Disconnected from SyncBox.")
            except Exception as error:
                print(f"Error while disconnecting from SyncBox: {error}")
            finally:
                self._ser = None

    def read_current_input_buffer(self) -> str:
        """Read current input buffer immediately (even if empty)."""
        if self._ser is None or not self._ser.is_open:
            raise SyncBoxException(
                "No active connection to SyncBox. "
                + "Please connect and try again."
            )

        try:
            out = self._ser.read(self._ser.in_waiting)
            return out.decode("utf-8") if out else ""
        except Exception as error:
            self.close()
            raise SyncBoxException(
                f"Error while reading from SyncBox: {error}"
            ) from error

    def get_trigger(self, timeout: float = 0) -> str:
        """Get the trigger sent from SyncBox to the host machine."""
        if self._ser is None or not self._ser.is_open:
            raise SyncBoxException(
                "No active connection to SyncBox. "
                + "Please connect and try again."
            )

        old_timeout = self._ser.timeout
        try:
            self._ser.timeout = timeout
            out = self._ser.read(GetGlobals.COMMAND_PAYLOAD_SIZE)
            if not out:
                raise SyncBoxException(
                    "No trigger received from SyncBox "
                    + f"within {timeout} seconds."
                )
            return out.decode("utf-8")
        except Exception as error:
            self.close()
            raise SyncBoxException(
                f"Error while getting trigger from SyncBox: {error}"
            ) from error
        finally:
            if self._ser is not None and self._ser.is_open:
                self._ser.timeout = old_timeout

    def get_response(
        self, begin_time: float, timeout: float = 0.1
    ) -> Tuple[str, float, float]:
        """Get the trigger, response time, and duration from SyncBox.

        Args:
            begin_time: Time of trial start.
            timeout:Max time to wait for a keypress in seconds.

        Returns:
            (trigger_char, response_time, duration_in_seconds)
            if detected, otherwise (False, False, False).
        """
        if self._ser is None or not self._ser.is_open:
            raise SyncBoxException(
                "No active connection to SyncBox. "
                + "Please connect and try again."
            )

        # Listen for initial key press,
        # L-Thumb=a, L-Index=b, R-Index=c, R-Thumb=d.
        self._ser.timeout = timeout
        exp_resp = [b"a", b"b", b"c", b"d"]
        out = self._ser.read(GetGlobals.COMMAND_PAYLOAD_SIZE)
        if out and out in exp_resp:
            press_time = time.perf_counter()
            trigger_char = out.decode("utf-8")

            # Track duration by checking when key signal stops
            last_held_time = press_time
            key_held = True

            # Micro-timeout to rapidly poll key hold state
            self._ser.timeout = 0.005
            while key_held:
                next_byte = self._ser.read(GetGlobals.COMMAND_PAYLOAD_SIZE)
                if next_byte == out:
                    last_held_time = time.perf_counter()
                else:
                    key_held = False

            duration = last_held_time - press_time
            resp_time = press_time - begin_time

            # Reset serial timeout back to default class setting
            self._ser.timeout = self.timeout
            return trigger_char, resp_time, duration

        self._ser.timeout = self.timeout
        return False, False, False

    def _find_sync_box(self) -> Optional[str]:
        ports = serial.tools.list_ports.comports()
        if not ports:
            raise SyncBoxException(
                "No serial ports found. Please connect "
                + "the SyncBox and try again."
            )

        print(
            f"Found {len(ports)} serial ports: "
            + f"{[port.device for port in ports]}"
        )

        for port in ports:
            com = port.device
            try:
                with Serial(com, self.baud_rate, timeout=self.timeout) as ser:
                    ser.write(Command.COMPUTER_MODE)
                    time.sleep(self.timeout)
                    response = ser.read(GetGlobals.COMMAND_PAYLOAD_SIZE)
                    if response == Command.COMPUTER_MODE:
                        print(f"SyncBox found on {com}")
                        return com
            except SerialException:
                continue

        return None

    def _send_command(self, payload: bytes, payload_size: int) -> bool:
        if not self._ser or not self._ser.is_open:
            return False

        self._ser.write(payload)
        time.sleep(self.timeout)
        response = self._ser.read(payload_size)

        if not response:
            print(f"No response received for command {payload!r}.")
            return False

        print(f"Received response: {response!r}")
        if response != payload:
            print(f"Unexpected response: {response!r} (expected: {payload!r})")
            return False

        return True

    @staticmethod
    def int_to_bytes(value: int) -> bytes:
        """Format integer into a 4-byte string representation."""
        if not isinstance(value, int):
            raise TypeError("Value must be an integer.")
        if not (0 <= value <= 9999):
            raise ValueError("Value must be between 0 and 9999.")
        return f"{value:04d}".encode()

    def print_configuration(self) -> None:
        """Display current configuration parameters."""
        config_str = (
            "Current SyncBox Configuration:\n"
            f"\tNumber of Volumes: {self.num_volumes}\n"
            f"\tNumber of Slices: {self.num_slices}\n"
            f"\tTrigger Slice: {self.trigger_slice}\n"
            f"\tTrigger Volume: {self.trigger_volume}\n"
            f"\tPulse Length (ms): {self.pulse_length}\n"
            f"\tTR Time (ms): {self.tr_time}\n"
            f"\tOptional Trigger Slice: {self.optional_trigger_slice}\n"
            f"\tOptional Trigger Volume: {self.optional_trigger_volume}\n"
            f"\tSimulation Mode: {'On' if self.simulation else 'Off'}\n"
        )
        print(config_str)
