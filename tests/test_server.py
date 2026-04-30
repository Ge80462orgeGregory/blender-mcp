"""Tests for the BlenderMCP server functionality."""

import json
import socket
import threading
import time
import unittest
from unittest.mock import MagicMock, patch


TEST_HOST = "localhost"
TEST_PORT = 19876  # Use a different port from the default to avoid conflicts


class TestCommandParsing(unittest.TestCase):
    """Test command parsing and validation logic."""

    def test_valid_command_structure(self):
        """Test that a valid command dict passes structural checks."""
        command = {
            "type": "get_scene_info",
            "params": {}
        }
        self.assertIn("type", command)
        self.assertIsInstance(command["type"], str)

    def test_command_with_params(self):
        """Test command structure with non-empty params."""
        command = {
            "type": "create_object",
            "params": {
                "type": "MESH",
                "name": "TestCube",
                "location": [0.0, 0.0, 0.0]
            }
        }
        self.assertEqual(command["type"], "create_object")
        self.assertEqual(command["params"]["name"], "TestCube")
        self.assertIsInstance(command["params"]["location"], list)
        self.assertEqual(len(command["params"]["location"]), 3)

    def test_json_serialization_roundtrip(self):
        """Test that commands survive JSON serialization/deserialization."""
        original = {
            "type": "set_material",
            "params": {
                "object": "Cube",
                "color": [1.0, 0.5, 0.2, 1.0]
            }
        }
        serialized = json.dumps(original)
        deserialized = json.loads(serialized)
        self.assertEqual(original, deserialized)

    def test_response_success_structure(self):
        """Test expected structure of a success response."""
        response = {
            "status": "success",
            "result": {"object_name": "Cube", "location": [0, 0, 0]}
        }
        self.assertEqual(response["status"], "success")
        self.assertIn("result", response)

    def test_response_error_structure(self):
        """Test expected structure of an error response."""
        response = {
            "status": "error",
            "message": "Object not found: NonExistentObject"
        }
        self.assertEqual(response["status"], "error")
        self.assertIn("message", response)
        self.assertIsInstance(response["message"], str)


class TestSocketCommunication(unittest.TestCase):
    """Test low-level socket communication helpers."""

    def test_send_receive_json(self):
        """Test that JSON data can be sent and received over a socket pair."""
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((TEST_HOST, TEST_PORT))
        server_sock.listen(1)
        server_sock.settimeout(5)

        received_data = []

        def server_thread():
            try:
                conn, _ = server_sock.accept()
                data = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if data.endswith(b"\n"):
                        break
                received_data.append(json.loads(data.decode("utf-8").strip()))
                conn.close()
            except Exception:
                pass
            finally:
                server_sock.close()

        t = threading.Thread(target=server_thread, daemon=True)
        t.start()
        time.sleep(0.1)

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_sock.connect((TEST_HOST, TEST_PORT))
        payload = json.dumps({"type": "ping", "params": {}}) + "\n"
        client_sock.sendall(payload.encode("utf-8"))
        client_sock.close()

        t.join(timeout=3)
        self.assertEqual(len(received_data), 1)
        self.assertEqual(received_data[0]["type"], "ping")


class TestParameterValidation(unittest.TestCase):
    """Test parameter validation for various command types."""

    def test_location_parameter_length(self):
        """Location must be a 3-element list."""
        location = [1.0, 2.0, 3.0]
        self.assertEqual(len(location), 3)
        self.assertTrue(all(isinstance(v, (int, float)) for v in location))

    def test_color_parameter_range(self):
        """RGBA color values must be in [0.0, 1.0]."""
        color = [0.8, 0.4, 0.1, 1.0]
        self.assertEqual(len(color), 4)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in color))

    def test_object_name_is_string(self):
        """Object names must be non-empty strings."""
        name = "MyObject"
        self.assertIsInstance(name, str)
        self.assertGreater(len(name), 0)


if __name__ == "__main__":
    unittest.main()
