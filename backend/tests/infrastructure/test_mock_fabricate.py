"""Contract tests for MockFabricateProvider."""

from app.application.ports import ExternalCallStatus
from app.infrastructure.mcp.fabricate_whitelist import FABRICATE_WHITELIST
from app.infrastructure.mcp.mock_fabricate import MockFabricateProvider


def test_whitelist_excludes_delete_tools() -> None:
    assert "delete_project" not in FABRICATE_WHITELIST
    assert "delete_workspace" not in FABRICATE_WHITELIST


def test_mock_conversation_lifecycle() -> None:
    fab = MockFabricateProvider()
    options = fab.list_conversation_options()
    assert options.status is ExternalCallStatus.SUCCESS

    upload = fab.create_upload(filename="schema.json", content=b"{}")
    upload_id = str(upload.data["upload_id"])

    started = fab.start_conversation(
        message="build plant",
        upload_ids=[upload_id],
    )
    conversation_id = str(started.data["conversation_id"])

    status1 = fab.get_conversation_status(conversation_id)
    assert status1.data["status"] == "running"
    status2 = fab.get_conversation_status(conversation_id)
    assert status2.data["status"] == "completed"

    result = fab.get_conversation_result(conversation_id)
    file_id = str(result.data["files"][0]["file_id"])
    download = fab.download_conversation_file(
        conversation_id=conversation_id,
        file_id=file_id,
    )
    assert download.status is ExternalCallStatus.SUCCESS
    assert isinstance(download.data["bytes"], (bytes, bytearray))
    assert download.data["bytes"][:15] == b"SQLite format 3"

    tools = [name for name, _ in fab.calls]
    assert "list_conversation_options" in tools
    assert "start_conversation" in tools
