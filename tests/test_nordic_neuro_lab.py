from unittest.mock import MagicMock, patch
import pytest
from nnl_psychopy.nordic_neuro_lab import (
    Command,
    SyncBox,
    SyncBoxException,
    Trigger,
    print_error,
    print_info,
    print_success,
)


def create_mock_serial(echo_responses=True):
    mock_ser = MagicMock()
    mock_ser.is_open = True
    mock_ser.timeout = 0.5  # Ensure timeout holds a float value

    if echo_responses:

        def mock_read(size):
            # Echoes back the written payload to satisfy _send_command check
            written = (
                mock_ser.write.call_args[0][0]
                if mock_ser.write.called
                else b""
            )
            return written[:size]

        mock_ser.read.side_effect = mock_read
    return mock_ser


class TestHelperFunctions:
    """Test helper utility functions and integer conversions."""

    def test_int_to_bytes_valid(self):
        assert SyncBox.int_to_bytes(0) == b"0000"
        assert SyncBox.int_to_bytes(16) == b"0016"
        assert SyncBox.int_to_bytes(9999) == b"9999"

    def test_int_to_bytes_invalid_type(self):
        with pytest.raises(TypeError, match="Value must be an integer."):
            SyncBox.int_to_bytes("123")  # type: ignore

    def test_int_to_bytes_out_of_range(self):
        with pytest.raises(
            ValueError, match="Value must be between 0 and 9999."
        ):
            SyncBox.int_to_bytes(-1)
        with pytest.raises(
            ValueError, match="Value must be between 0 and 9999."
        ):
            SyncBox.int_to_bytes(10000)

    @patch("builtins.print")
    def test_print_helpers(self, mock_print):
        print_info("info msg")
        mock_print.assert_called_with("\033[94m[*] info msg\033[0m")

        print_success("success msg")
        mock_print.assert_called_with("\033[92m[+] success msg\033[0m")

        print_error("error msg")
        mock_print.assert_called_with("\033[91m[-] error msg\033[0m")


class TestSyncBoxException:
    """Test custom exception formatting."""

    def test_syncbox_exception_str(self):
        err = SyncBoxException("Test error")
        assert str(err) == "\033[91mSyncBoxException: Test error\033[0m"
        assert err.message == "Test error"


class TestSyncBoxInitialization:
    """Test SyncBox connection and configuration setup."""

    @patch("serial.tools.list_ports.comports")
    @patch("nnl_psychopy.nordic_neuro_lab.Serial")
    def test_auto_detect_port_success(self, mock_serial_cls, mock_comports):
        port_mock = MagicMock()
        port_mock.device = "COM3"
        mock_comports.return_value = [port_mock]

        mock_ser = create_mock_serial()
        mock_serial_cls.return_value = mock_ser
        mock_serial_cls.return_value.__enter__.return_value = mock_ser

        box = SyncBox(num_volumes=10)
        assert box.serial_port == "COM3"
        assert box._ser == mock_ser

    @patch("serial.tools.list_ports.comports")
    def test_auto_detect_no_ports_found(self, mock_comports):
        mock_comports.return_value = []
        with pytest.raises(SyncBoxException, match="No serial ports found"):
            SyncBox()

    @patch("serial.tools.list_ports.comports")
    @patch("nnl_psychopy.nordic_neuro_lab.Serial")
    def test_auto_detect_failed_to_find_syncbox(
        self, mock_serial_cls, mock_comports
    ):
        port_mock = MagicMock()
        port_mock.device = "COM3"
        mock_comports.return_value = [port_mock]

        mock_ser = MagicMock()
        mock_ser.read.return_value = b"X"
        mock_serial_cls.return_value.__enter__.return_value = mock_ser

        with pytest.raises(SyncBoxException, match="SyncBox not found"):
            SyncBox()

    @patch("nnl_psychopy.nordic_neuro_lab.Serial")
    def test_init_provided_port_success(self, mock_serial_cls):
        mock_ser = create_mock_serial()
        mock_serial_cls.return_value = mock_ser

        box = SyncBox(serial_port="COM1")
        assert box.serial_port == "COM1"

    @patch("nnl_psychopy.nordic_neuro_lab.Serial")
    def test_init_configuration_failure(self, mock_serial_cls):
        mock_ser = MagicMock()
        mock_ser.is_open = True
        mock_ser.read.return_value = b""
        mock_serial_cls.return_value = mock_ser

        with pytest.raises(
            SyncBoxException, match="Failed to configure SyncBox"
        ):
            SyncBox(serial_port="COM1")


class TestSyncBoxMethods:
    """Test standard SyncBox operational methods."""

    @pytest.fixture
    def mock_syncbox(self):
        with patch("nnl_psychopy.nordic_neuro_lab.Serial") as mock_serial_cls:
            mock_ser = create_mock_serial()
            mock_serial_cls.return_value = mock_ser
            box = SyncBox(serial_port="COM1")
            yield box, mock_ser

    def test_start_success(self, mock_syncbox):
        box, mock_ser = mock_syncbox
        box.start()
        mock_ser.write.assert_called_with(Command.START)

    def test_start_failure(self, mock_syncbox):
        box, mock_ser = mock_syncbox
        mock_ser.read.side_effect = None
        mock_ser.read.return_value = b"FAIL"
        with pytest.raises(
            SyncBoxException, match="Failed to start SyncBox session"
        ):
            box.start()

    def test_stop_success(self, mock_syncbox):
        box, mock_ser = mock_syncbox
        box.stop()
        mock_ser.write.assert_called_with(Command.STOP)

    def test_stop_failure(self, mock_syncbox):
        box, mock_ser = mock_syncbox
        mock_ser.read.side_effect = None
        mock_ser.read.return_value = b"FAIL"
        with pytest.raises(
            SyncBoxException, match="Failed to stop SyncBox session"
        ):
            box.stop()

    def test_close(self, mock_syncbox):
        box, mock_ser = mock_syncbox
        box.close()
        mock_ser.write.assert_called_with(Command.MANUAL_MODE)
        mock_ser.close.assert_called_once()
        assert box._ser is None

    def test_read_current_input_buffer_success(self, mock_syncbox):
        box, mock_ser = mock_syncbox
        mock_ser.in_waiting = 5
        mock_ser.read.side_effect = None
        mock_ser.read.return_value = b"D"

        data = box.read_current_input_buffer()
        assert data == "D"

    def test_read_current_input_buffer_disconnected(self):
        with patch("nnl_psychopy.nordic_neuro_lab.Serial") as mock_serial_cls:
            mock_ser = create_mock_serial()
            mock_serial_cls.return_value = mock_ser
            box = SyncBox(serial_port="COM1")
            box.close()

            with pytest.raises(
                SyncBoxException, match="No active connection to SyncBox"
            ):
                box.read_current_input_buffer()

    def test_get_trigger_success(self, mock_syncbox):
        box, mock_ser = mock_syncbox

        # Restore mock echo after get_trigger finishes so teardown close() passes
        def mock_read_trigger(size):
            mock_ser.read.side_effect = lambda s: mock_ser.write.call_args[0][
                0
            ][:s]
            return Trigger.TRIGGER.value

        mock_ser.read.side_effect = mock_read_trigger

        trigger = box.get_trigger(timeout=1.0)
        assert trigger == "s"
        assert mock_ser.timeout == 0.5

    def test_get_trigger_timeout(self, mock_syncbox):
        box, mock_ser = mock_syncbox
        mock_ser.read.side_effect = None
        mock_ser.read.return_value = b""

        with pytest.raises(
            SyncBoxException, match="No trigger received from SyncBox"
        ):
            box.get_trigger(timeout=0.1)

    def test_context_manager(self):
        with patch("nnl_psychopy.nordic_neuro_lab.Serial") as mock_serial_cls:
            mock_ser = create_mock_serial()
            mock_serial_cls.return_value = mock_ser

            with SyncBox(serial_port="COM1") as box:
                assert box._ser is not None

            mock_ser.close.assert_called_once()
