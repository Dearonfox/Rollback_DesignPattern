import unittest

from rollback_first_agent.core import (
    ActionType,
    GateDecision,
    RecoveryLevel,
    RollbackFirstAgent,
    RollbackType,
    SQLiteActionStore,
)


class RollbackFirstAgentTest(unittest.TestCase):
    def setUp(self):
        self.store = SQLiteActionStore()
        self.store.seed_demo_data()
        self.agent = RollbackFirstAgent(self.store)

    def test_create_schedule_prepares_rollback_before_execution(self):
        plan = self.agent.plan("내일 오후 3시에 운영체제 공부 일정 추가해줘")

        self.assertEqual(plan.planned_action.action_type, ActionType.CREATE_SCHEDULE)
        self.assertEqual(plan.gate_result.gate_decision, GateDecision.EXECUTE)
        self.assertEqual(plan.rollback_plan.recovery_level, RecoveryLevel.FULLY_REVERSIBLE)
        self.assertEqual(
            plan.rollback_plan.rollback_type,
            RollbackType.DELETE_CREATED_SCHEDULE,
        )
        self.assertTrue(plan.rollback_plan.rollback_available)

        result = self.agent.execute(plan)

        self.assertEqual(result["status"], "executed")
        self.assertIn("created_schedule_id", result["result"])
        self.assertIsInstance(result["rollback_plan"]["rollback_arguments"]["target"], int)

    def test_rollback_created_schedule_deletes_it(self):
        result = self.agent.run("내일 오후 3시에 운영체제 공부 일정 추가해줘")
        action_id = result["execution"]["action_id"]
        schedule_id = result["execution"]["result"]["created_schedule_id"]

        rollback = self.agent.rollback(action_id)

        self.assertEqual(rollback["status"], "rolled_back")
        self.assertIsNone(self.store.get_schedule(schedule_id))

    def test_delete_completed_todos_backups_and_restores(self):
        done_before = self.store.fetch_todos(status="done")
        result = self.agent.run("완료된 할 일 정리해줘")

        self.assertEqual(result["execution"]["result"]["deleted_count"], len(done_before))
        self.assertEqual(self.store.fetch_todos(status="done"), [])

        self.agent.rollback(result["execution"]["action_id"])

        restored = self.store.fetch_todos(status="done")
        self.assertEqual(len(restored), len(done_before))

    def test_update_schedule_restores_previous_state(self):
        original = self.store.find_schedule_by_title("운영체제")

        result = self.agent.run("내일 운영체제 공부 일정을 오후 5시로 바꿔줘")
        updated = self.store.get_schedule(original["id"])

        self.assertEqual(updated["start_time"], "2026-06-22 17:00")

        self.agent.rollback(result["execution"]["action_id"])
        restored = self.store.get_schedule(original["id"])

        self.assertEqual(restored["start_time"], original["start_time"])

    def test_irreversible_notice_send_is_transformed_to_draft(self):
        plan = self.agent.plan("팀원들에게 내일 회의 취소됐다고 공지 보내줘")

        self.assertEqual(plan.original_action.action_type, ActionType.SEND_NOTICE)
        self.assertEqual(plan.rollback_plan.recovery_level, RecoveryLevel.IRREVERSIBLE)
        self.assertEqual(
            plan.gate_result.gate_decision,
            GateDecision.TRANSFORM_TO_SAFE_ACTION,
        )
        self.assertEqual(plan.final_action.action_type, ActionType.CREATE_NOTICE_DRAFT)

        result = self.agent.execute(plan)

        self.assertEqual(result["status"], "transformed")
        self.assertEqual(
            result["rollback_plan"]["rollback_type"],
            RollbackType.DELETE_NOTICE_DRAFT.value,
        )

    def test_rollback_transformed_notice_draft_deletes_draft(self):
        result = self.agent.run("팀원들에게 내일 회의 취소됐다고 공지 보내줘")
        action_id = result["execution"]["action_id"]
        notice_id = result["execution"]["result"]["created_notice_draft_id"]

        rollback = self.agent.rollback(action_id)

        self.assertEqual(rollback["status"], "rolled_back")
        self.assertIsNone(self.store.get_notice(notice_id))


if __name__ == "__main__":
    unittest.main()
