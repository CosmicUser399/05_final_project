"""Allowed Fabricate MCP tool names for the runtime adapter."""

FABRICATE_WHITELIST: frozenset[str] = frozenset(
    {
        "list_conversation_options",
        "create_upload",
        "start_conversation",
        "get_conversation_status",
        "get_conversation_result",
        "download_conversation_file",
        "send_message",
        "retry_conversation",
        "stop_conversation",
        "list_databases",
        "query_database",
    }
)
