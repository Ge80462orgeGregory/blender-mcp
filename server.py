"""Blender MCP Server - Core server implementation for handling MCP protocol communication.

This module implements the main server logic that bridges the MCP (Model Context Protocol)
with Blender's Python API, allowing AI assistants to interact with Blender scenes.
"""

import json
import socket
import logging
import threading
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9876
BUFFER_SIZE = 4096


class CommandHandler:
    """Registry for Blender command handlers."""

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def register(self, command: str, handler: Callable) -> None:
        """Register a handler function for a given command name."""
        self._handlers[command] = handler
        logger.debug(f"Registered handler for command: {command}")

    def dispatch(self, command: str, params: Dict[str, Any]) -> Any:
        """Dispatch a command to its registered handler.

        Args:
            command: The command name to dispatch.
            params: Parameters to pass to the handler.

        Returns:
            The result from the handler.

        Raises:
            ValueError: If no handler is registered for the command.
        """
        if command not in self._handlers:
            raise ValueError(f"Unknown command: {command}")
        return self._handlers[command](**params)

    @property
    def available_commands(self):
        """Return a list of all registered command names."""
        return list(self._handlers.keys())


class BlenderMCPServer:
    """TCP server that listens for MCP commands and executes them in Blender."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.handler = CommandHandler()
        self._server_socket: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the server in a background thread."""
        if self._running:
            logger.warning("Server is already running.")
            return

        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        logger.info(f"BlenderMCP server started on {self.host}:{self.port}")

    def stop(self) -> None:
        """Stop the server and close the socket."""
        self._running = False
        if self._server_socket:
            try:
                self._server_socket.close()
            except OSError:
                pass
        logger.info("BlenderMCP server stopped.")

    def _serve(self) -> None:
        """Main server loop — accepts connections and handles requests."""
        try:
            self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind((self.host, self.port))
            self._server_socket.listen(5)
            self._server_socket.settimeout(1.0)

            while self._running:
                try:
                    conn, addr = self._server_socket.accept()
                    logger.debug(f"Connection from {addr}")
                    threading.Thread(
                        target=self._handle_connection, args=(conn,), daemon=True
                    ).start()
                except socket.timeout:
                    continue
        except OSError as e:
            if self._running:
                logger.error(f"Server socket error: {e}")

    def _handle_connection(self, conn: socket.socket) -> None:
        """Handle a single client connection, reading and responding to one command."""
        with conn:
            try:
                data = b""
                while True:
                    chunk = conn.recv(BUFFER_SIZE)
                    if not chunk:
                        break
                    data += chunk
                    if b"\n" in data:
                        break

                request = json.loads(data.decode("utf-8").strip())
                command = request.get("command", "")
                params = request.get("params", {})

                result = self.handler.dispatch(command, params)
                response = {"status": "ok", "result": result}
            except ValueError as e:
                logger.warning(f"Command error: {e}")
                response = {"status": "error", "message": str(e)}
            except Exception as e:
                logger.exception(f"Unexpected error handling command: {e}")
                response = {"status": "error", "message": f"Internal error: {e}"}

            conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
