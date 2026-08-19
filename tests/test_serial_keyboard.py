import sys
from unittest.mock import MagicMock, PropertyMock, patch
import pytest

from nnl_psychopy.serial_keyboard import (
    Key,
    SerialKeyboard,
    _get_args,
    list_ports,
    main,
)

# --- Tests for list_ports ---


@patch("serial.Serial")
@patch("glob.glob")
def test_list_ports_darwin(mock_glob, mock_serial):
    """Test discovering valid ports on macOS."""
    mock_glob.return_value = ["/dev/tty.usbmodem14101"]

    mock_connection = MagicMock()
    mock_serial.return_value = mock_connection

    with patch("sys.platform", "darwin"):
        ports = list_ports()
        assert ports == ["/dev/tty.usbmodem14101"]
        mock_serial.assert_called_once_with("/dev/tty.usbmodem14101")
        mock_connection.close.assert_called_once()


@patch("sys.platform", "unsupported_os")
def test_list_ports_unsupported_os():
    """Test that an unsupported OS platform raises an EnvironmentError."""
    with pytest.raises(EnvironmentError, match="Unsupported platform"):
        list_ports()


# --- Tests for SerialKeyboard Class ---


@patch("serial.Serial")
def test_connect_success(mock_serial):
    """Test successful serial connection initialization."""
    mock_connection = MagicMock()
    mock_serial.return_value = mock_connection

    sk = SerialKeyboard(port="/dev/ttyUSB0", baud_rate=115200)
    connection = sk.connect()

    assert connection == mock_connection
    mock_serial.assert_called_once_with("/dev/ttyUSB0", 115200, timeout=1.0)


@patch("serial.Serial", side_effect=Exception("Connection error"))
def test_connect_failure(mock_serial):
    """Test failed serial connection raises exception."""
    sk = SerialKeyboard(port="/dev/ttyUSB0")
    with pytest.raises(Exception, match="Connection error"):
        sk.connect()


@patch("nnl_psychopy.serial_keyboard.Controller")
@patch("serial.Serial")
def test_listen_reads_and_types_data(mock_serial, mock_controller_cls):
    """Test reading incoming lines from serial input and typing them via pynput."""
    mock_keyboard = MagicMock()
    mock_controller_cls.return_value = mock_keyboard

    # Mock the serial connection
    mock_connection = MagicMock()
    mock_connection.is_open = True

    # First iteration: data waiting; Second iteration: close connection to exit loop
    type(mock_connection).in_waiting = PropertyMock(side_effect=[1, 0])

    def mock_readline():
        mock_connection.is_open = False
        return b"test_key_input\r\n"

    mock_connection.readline.side_effect = mock_readline
    mock_serial.return_value = mock_connection

    # Initialize SerialKeyboard
    sk = SerialKeyboard(port="/dev/ttyUSB0")
    # Explicitly assign mock controller to override any real instance
    sk.keyboard = mock_keyboard
    sk._connection = mock_connection

    sk.listen()

    mock_keyboard.type.assert_called_once_with("test_key_input")
    mock_keyboard.press.assert_called_once_with(Key.enter)
    mock_keyboard.release.assert_called_once_with(Key.enter)
    # mock_connection.close.assert_called_once()


@patch("serial.Serial")
def test_listen_handles_cable_disconnect_gracefully(mock_serial, capsys):
    """Test that serial cable disconnect is handled without crashing."""
    mock_connection = MagicMock()
    mock_connection.is_open = True
    type(mock_connection).in_waiting = PropertyMock(return_value=1)
    mock_connection.readline.side_effect = Exception("Device disconnected")
    mock_serial.return_value = mock_connection

    sk = SerialKeyboard(port="/dev/ttyUSB0")
    sk.listen()

    captured = capsys.readouterr()
    assert (
        "Something happened... did you just yank the thing out?"
        in captured.out
    )
    assert "Serial connection closed." in captured.out


# --- Tests for CLI Helpers and Main Entrypoint ---


def test_get_args_no_args_exit():
    """Test running CLI with no arguments exits with status 0."""
    with patch.object(sys, "argv", ["serial_keyboard"]):
        with pytest.raises(SystemExit) as exc_info:
            _get_args()
        assert exc_info.value.code == 0


@patch("nnl_psychopy.serial_keyboard.list_ports")
def test_main_get_ports_flag(mock_list_ports, capsys):
    """Test main function with --get-ports argument."""
    mock_list_ports.return_value = ["/dev/ttyUSB0", "/dev/ttyUSB1"]
    test_argv = ["serial_keyboard", "--get-ports"]

    with patch.object(sys, "argv", test_argv):
        main()

    captured = capsys.readouterr()
    assert "List of detected ports: /dev/ttyUSB0 /dev/ttyUSB1" in captured.out


@patch.object(SerialKeyboard, "listen")
def test_main_start_listening(mock_listen):
    """Test main function invoking SerialKeyboard.listen()."""
    test_argv = ["serial_keyboard", "--port", "/dev/ttyUSB0", "--baud", "9600"]

    with patch.object(sys, "argv", test_argv):
        main()

    mock_listen.assert_called_once()
