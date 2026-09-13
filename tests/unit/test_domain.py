"""Unit tests for app/domain entities: content, conversation, memory, plan, session, and state."""

import time
from datetime import datetime

from app.domain.content import ArtifactHandle, ContentSource, ContentType, DocumentReference
from app.domain.conversation import ConversationState, Message, MessageAttachment, Role
from app.domain.memory import FactExtractionResult, MemoryRecord, MemoryType
from app.domain.plan import ExecutionPlan, ExecutionStep, SafetyTier, StepStatus, ToolCall
from app.domain.session import SessionState, UserPreferences
from app.domain.state import ExecutionState, IntentState, PlanState, ResponseState


def test_content_type_enum() -> None:
    assert ContentType.TEXT.value == "text"
    assert ContentType.CODE.value == "code"
    assert ContentType.FILE.value == "file"
    assert ContentType.PDF.value == "pdf"
    assert ContentType.IMAGE.value == "image"
    assert ContentType.URL.value == "url"
    assert ContentType.REPOSITORY.value == "repository"


def test_document_reference() -> None:
    ref = DocumentReference(uri="file://test.py")
    assert ref.uri == "file://test.py"
    assert ref.title is None
    assert ref.page_number is None
    assert ref.line_start is None
    assert ref.line_end is None
    assert ref.snippet is None

    custom = DocumentReference(
        uri="file://test.py",
        title="Test File",
        page_number=2,
        line_start=10,
        line_end=20,
        snippet="code snippet",
    )
    assert custom.title == "Test File"
    assert custom.page_number == 2
    assert custom.line_start == 10
    assert custom.line_end == 20
    assert custom.snippet == "code snippet"


def test_content_source_and_token_estimate() -> None:
    source = ContentSource(
        source_id="src_1",
        content_type=ContentType.TEXT,
        uri="https://example.com",
        title="Example",
    )
    assert source.raw_text == ""
    assert source.metadata == {}
    assert source.references == []
    assert isinstance(source.created_at, datetime)
    assert source.token_estimate == 1  # max(1, 0 // 4)

    source.raw_text = "a" * 10
    assert source.token_estimate == 2  # 10 // 4 = 2

    source.raw_text = "a" * 100
    assert source.token_estimate == 25


def test_artifact_handle() -> None:
    artifact = ArtifactHandle(
        source_id="art_1",
        content_type=ContentType.PDF,
        uri="/tmp/doc.pdf",
        title="Doc PDF",
    )
    assert artifact.file_path == ""
    assert artifact.mime_type == "application/octet-stream"
    assert artifact.byte_size == 0
    assert artifact.spilled_to_disk is True
    assert artifact.ocr_extracted is False

    custom_art = ArtifactHandle(
        source_id="art_2",
        content_type=ContentType.IMAGE,
        uri="/tmp/img.png",
        title="Img PNG",
        file_path="/tmp/img.png",
        mime_type="image/png",
        byte_size=1024,
        spilled_to_disk=False,
        ocr_extracted=True,
    )
    assert custom_art.file_path == "/tmp/img.png"
    assert custom_art.mime_type == "image/png"
    assert custom_art.byte_size == 1024
    assert custom_art.spilled_to_disk is False
    assert custom_art.ocr_extracted is True


def test_role_enum() -> None:
    assert Role.SYSTEM.value == "system"
    assert Role.USER.value == "user"
    assert Role.ASSISTANT.value == "assistant"
    assert Role.TOOL.value == "tool"


def test_message_attachment() -> None:
    attachment = MessageAttachment(name="report.pdf", size=2048)
    assert attachment.name == "report.pdf"
    assert attachment.size == 2048
    assert attachment.mime_type == "application/octet-stream"
    assert attachment.file_path is None
    assert attachment.content_preview is None


def test_message_to_dict() -> None:
    msg = Message(
        id="msg_1",
        role=Role.USER,
        content="Hello world",
        pinned=True,
        attachments=[
            MessageAttachment(name="a.txt", size=10, mime_type="text/plain", file_path="/a.txt")
        ],
        metadata={"key": "val"},
    )
    data = msg.to_dict()
    assert data["id"] == "msg_1"
    assert data["role"] == "user"
    assert data["content"] == "Hello world"
    assert data["pinned"] is True
    assert len(data["attachments"]) == 1
    assert data["attachments"][0]["name"] == "a.txt"
    assert data["attachments"][0]["file_path"] == "/a.txt"
    assert data["metadata"] == {"key": "val"}
    assert "created_at" in data

    # Test string role
    msg_str = Message(id="msg_2", role="assistant", content="Hi")  # type: ignore[arg-type]
    data_str = msg_str.to_dict()
    assert data_str["role"] == "assistant"


def test_conversation_state() -> None:
    state = ConversationState(id="conv_1")
    assert state.title == "New Chat"
    assert state.messages == []
    assert state.metadata == {}
    assert state.message_count == 0
    assert state.preview == "Empty chat"

    # Add assistant message only
    msg_assistant = Message(id="m0", role=Role.ASSISTANT, content="System initialized.")
    state.add_message(msg_assistant)
    assert state.message_count == 1
    assert state.preview == "System initialized."

    # Add user message
    msg1 = Message(id="m1", role=Role.USER, content="   What is Python?   ")
    prev_updated = state.updated_at
    time.sleep(0.001)
    state.add_message(msg1)
    assert state.message_count == 2
    assert state.updated_at >= prev_updated
    assert state.preview == "What is Python?"

    # Preview cuts at 80 chars
    long_msg = Message(id="m2", role=Role.USER, content="A" * 100)
    state_long = ConversationState(id="conv_2", messages=[long_msg])
    assert state_long.preview == "A" * 80


def test_memory_records() -> None:
    assert MemoryType.FACT.value == "fact"
    assert MemoryType.PREFERENCE.value == "preference"
    assert MemoryType.PROJECT.value == "project"
    assert MemoryType.ENTITY.value == "entity"
    assert MemoryType.INSTRUCTION.value == "instruction"

    record = MemoryRecord(id="rec_1", key="user_lang", value="Python")
    assert record.category == "general"
    assert record.memory_type == MemoryType.FACT
    assert record.confidence == 1.0
    assert record.access_count == 0
    assert record.last_accessed_at is None
    assert record.embedding is None
    assert record.metadata == {}

    extraction = FactExtractionResult(facts=[record], source_message_id="msg_1")
    assert len(extraction.facts) == 1
    assert extraction.source_message_id == "msg_1"
    assert isinstance(extraction.extracted_at, datetime)


def test_plan_entities() -> None:
    assert SafetyTier.SAFE.value == "safe"
    assert SafetyTier.SENSITIVE.value == "sensitive"
    assert SafetyTier.DESTRUCTIVE.value == "destructive"

    assert StepStatus.PENDING.value == "pending"
    assert StepStatus.IN_PROGRESS.value == "in_progress"
    assert StepStatus.AWAITING_APPROVAL.value == "awaiting_approval"
    assert StepStatus.COMPLETED.value == "completed"
    assert StepStatus.FAILED.value == "failed"
    assert StepStatus.SKIPPED.value == "skipped"

    tc_safe = ToolCall(tool_name="read_file", arguments={"path": "a.txt"})
    assert tc_safe.safety_tier == SafetyTier.SAFE
    assert tc_safe.description == ""

    tc_destructive = ToolCall(
        tool_name="run_command",
        arguments={"cmd": "rm -rf /"},
        safety_tier=SafetyTier.DESTRUCTIVE,
    )

    step1 = ExecutionStep(step_id="step_1", title="Read config", tool_call=tc_safe)
    assert not step1.is_destructive
    assert step1.status == StepStatus.PENDING
    assert step1.result is None
    assert step1.error is None
    assert step1.hitl_required is False
    assert step1.hitl_approved is None

    step2 = ExecutionStep(step_id="step_2", title="Delete files", tool_call=tc_destructive)
    assert step2.is_destructive

    step_no_tool = ExecutionStep(step_id="step_3", title="No tool")
    assert not step_no_tool.is_destructive

    plan = ExecutionPlan(plan_id="p1", goal="Clean workspace", steps=[step1, step2])
    assert not plan.is_complete
    assert not plan.has_failed
    assert plan.current_step == step1

    # advance step
    plan.current_step_index = 1
    assert plan.current_step == step2

    # out of range step
    plan.current_step_index = 5
    assert plan.current_step is None

    plan.current_step_index = -1
    assert plan.current_step is None

    # completion check
    step1.status = StepStatus.COMPLETED
    step2.status = StepStatus.SKIPPED
    assert plan.is_complete
    assert not plan.has_failed

    # failure check
    step2.status = StepStatus.FAILED
    assert not plan.is_complete
    assert plan.has_failed


def test_session_entities() -> None:
    pref = UserPreferences()
    assert pref.active_model_id == "omni"
    assert pref.use_developer_keys is False
    assert pref.hitl_auto_approve_sensitive is True
    assert pref.theme == "dark"
    assert pref.custom_instructions == ""

    session = SessionState(session_id="sess_1")
    assert session.user_id == "default_user"
    assert session.active_conversation_id is None
    assert session.preferences.active_model_id == "omni"
    assert session.metadata == {}
    assert isinstance(session.created_at, datetime)
    assert isinstance(session.last_active_at, datetime)


def test_typed_states() -> None:
    intent_state: IntentState = {
        "analysis": {"intent": "build"},
        "session_id": "s1",
        "prompt": "build app",
    }
    assert intent_state["session_id"] == "s1"

    plan_state: PlanState = {"plan": {"id": "p1"}, "analysis": {"intent": "build"}}
    assert plan_state["analysis"]["intent"] == "build"

    exec_state: ExecutionState = {"executed": {}, "hitl_approvals": {"appr_1": True}}
    assert exec_state["hitl_approvals"]["appr_1"] is True

    resp_state: ResponseState = {"synthesized": "Done!", "session_id": "s1"}
    assert resp_state["synthesized"] == "Done!"
