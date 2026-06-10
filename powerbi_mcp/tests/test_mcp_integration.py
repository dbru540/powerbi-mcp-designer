import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, stdio_client
from powerbi_mcp.tests._temp_roots import named_temp_root


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PROJECT_PATH = REPO_ROOT / "example"
TEMP_ROOT = named_temp_root("mcp_integration")


def _parse_json_tool_result(result) -> dict:
    if result.isError:
        raise AssertionError(f"Tool call failed: {result.content}")
    if not result.content:
        raise AssertionError("Tool call returned no content")
    text_item = result.content[0]
    return json.loads(text_item.text)


class MCPIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def make_fixture_copy(self) -> Path:
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        project_dir = TEMP_ROOT / f"project-{uuid.uuid4().hex}"
        shutil.copytree(FIXTURE_PROJECT_PATH, project_dir)
        self.addCleanup(shutil.rmtree, project_dir, True)
        self.addCleanup(self._cleanup_root)
        return project_dir

    def _cleanup_root(self) -> None:
        if TEMP_ROOT.exists() and not any(TEMP_ROOT.iterdir()):
            TEMP_ROOT.rmdir()

    async def test_stdio_client_lists_tools_and_executes_read_then_write(self) -> None:
        project_copy = self.make_fixture_copy()
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "powerbi_mcp.server"],
            cwd=str(REPO_ROOT),
        )

        try:
            async with stdio_client(server) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    init = await session.initialize()
                    self.assertEqual(init.serverInfo.name, "PowerBI-MCP-Server")

                    tools = await session.list_tools()
                    tools_by_name = {tool.name: tool for tool in tools.tools}
                    tool_names = set(tools_by_name)
                    self.assertIn("project_get_summary", tool_names)
                    self.assertIn("report_get_visual_bindings", tool_names)
                    self.assertIn("model_upsert_measure", tool_names)
                    self.assertIn("get_project_info", tool_names)
                    self.assertIn("list_pages", tool_names)
                    self.assertIn("get_visual", tool_names)
                    self.assertIn("visual_examples_list", tool_names)
                    self.assertIn("visual_template_recommend", tool_names)
                    self.assertIn("visual_template_library", tool_names)
                    self.assertIn("visual_role_examples", tool_names)
                    self.assertIn("custom_visual_eligibility", tool_names)
                    self.assertIn("visual_vocabulary_classify", tool_names)
                    self.assertIn("report_design_audit", tool_names)
                    self.assertIn("page_design_audit", tool_names)
                    self.assertIn("visual_design_audit", tool_names)
                    self.assertIn("report_design_improve_plan", tool_names)
                    self.assertIn("page_design_improve_plan", tool_names)
                    self.assertIn("page_design_action_plan", tool_names)
                    self.assertIn("page_design_apply_quick_wins", tool_names)
                    self.assertIn("report_design_apply_quick_wins", tool_names)
                    self.assertIn("page_layout_action_plan", tool_names)
                    self.assertIn("page_layout_apply_quick_wins", tool_names)
                    self.assertIn("report_layout_apply_quick_wins", tool_names)
                    self.assertIn("page_layout_analyze", tool_names)
                    self.assertIn("page_layout_blueprint_generate", tool_names)
                    self.assertIn("page_layout_recommend", tool_names)
                    self.assertIn("page_layout_reflow_plan", tool_names)
                    self.assertIn("page_layout_apply_reflow_plan", tool_names)
                    self.assertIn("report_design_studio_plan", tool_names)
                    self.assertIn("report_design_readiness_check", tool_names)
                    self.assertIn("report_design_visual_qa_loop", tool_names)
                    self.assertIn("report_design_desktop_evidence_summary", tool_names)

                    for tool_name, tool in tools_by_name.items():
                        with self.subTest(tool_name=tool_name):
                            self.assertIsNotNone(tool.annotations)
                            self.assertIsNotNone(tool.annotations.readOnlyHint)
                            self.assertIsNotNone(tool.annotations.destructiveHint)
                            self.assertIsNotNone(tool.annotations.idempotentHint)
                            self.assertIsNotNone(tool.annotations.openWorldHint)

                    read_annotations = tools_by_name["project_get_summary"].annotations
                    self.assertIsNotNone(read_annotations)
                    self.assertIs(read_annotations.readOnlyHint, True)
                    self.assertIs(read_annotations.destructiveHint, False)
                    self.assertIs(read_annotations.idempotentHint, True)
                    self.assertIs(read_annotations.openWorldHint, False)

                    write_annotations = tools_by_name["create_page"].annotations
                    self.assertIsNotNone(write_annotations)
                    self.assertIs(write_annotations.readOnlyHint, False)
                    self.assertIs(write_annotations.destructiveHint, True)
                    self.assertIs(write_annotations.idempotentHint, False)
                    self.assertIs(write_annotations.openWorldHint, False)

                    open_world_annotations = tools_by_name["report_design_visual_qa_loop"].annotations
                    self.assertIsNotNone(open_world_annotations)
                    self.assertIs(open_world_annotations.readOnlyHint, False)
                    self.assertIs(open_world_annotations.destructiveHint, False)
                    self.assertIs(open_world_annotations.idempotentHint, False)
                    self.assertIs(open_world_annotations.openWorldHint, True)

                    summary = _parse_json_tool_result(
                        await session.call_tool(
                            "project_get_summary",
                            {"project_path": str(project_copy)},
                        )
                    )
                    self.assertEqual(summary["page_count"], 13)
                    self.assertEqual(summary["table_count"], 11)

                    before_pages = _parse_json_tool_result(
                        await session.call_tool(
                            "report_list_pages",
                            {"project_path": str(project_copy)},
                        )
                    )
                    self.assertEqual(before_pages["count"], 13)

                    created_page = _parse_json_tool_result(
                        await session.call_tool(
                            "create_page",
                            {
                                "project_path": str(project_copy),
                                "display_name": "Integration Test Page",
                            },
                        )
                    )
                    self.assertTrue(created_page["success"])
                    self.assertEqual(created_page["displayName"], "Integration Test Page")

                    after_pages = _parse_json_tool_result(
                        await session.call_tool(
                            "report_list_pages",
                            {"project_path": str(project_copy)},
                        )
                    )
                    self.assertEqual(after_pages["count"], before_pages["count"] + 1)
                    self.assertIn(
                        created_page["page_id"],
                        {page["id"] for page in after_pages["pages"]},
                    )
        except PermissionError as exc:
            self.skipTest(f"stdio MCP integration requires subprocess pipe access: {exc}")
