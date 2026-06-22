import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import "./styles.css";

const API_BASE = "http://127.0.0.1:8000";

type AgentPlan = {
  user_request: string;
  original_action: {
    action_type: string;
    arguments: Record<string, unknown>;
    description: string;
  };
  planned_action: {
    action_type: string;
    arguments: Record<string, unknown>;
    description: string;
  };
  final_action: {
    action_type: string;
    arguments: Record<string, unknown>;
    description: string;
  };
  rollback_plan: {
    rollback_type: string;
    rollback_arguments: Record<string, unknown>;
    rollback_available: boolean;
    recovery_level: string;
    reason: string;
  };
  gate_result: {
    gate_decision: string;
    reason: string;
    safe_alternative: null | {
      action_type: string;
      arguments: Record<string, unknown>;
      description: string;
    };
  };
};

type HistoryItem = {
  id: number;
  user_request: string;
  action_type: string;
  original_action_type?: string;
  final_action_type?: string;
  rollback_type: string;
  rollback_available: number;
  recovery_level?: string;
  gate_decision?: string;
  status: string;
  created_at: string;
};

function App() {
  const [message, setMessage] = useState("내일 오후 3시에 운영체제 공부 일정 추가해줘");
  const [plan, setPlan] = useState<AgentPlan | null>(null);
  const [result, setResult] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [history, setHistory] = useState<HistoryItem[]>([]);

  async function refreshHistory() {
    try {
      const response = await axios.get(`${API_BASE}/agent/history`);
      setHistory(response.data);
    } catch {
      setError("백엔드 서버에 연결할 수 없습니다. uvicorn 서버가 실행 중인지 확인해 주세요.");
    }
  }

  async function createPlan() {
    try {
      setError("");
      const response = await axios.post(`${API_BASE}/agent/plan`, { message });
      setPlan(response.data);
      setResult("");
    } catch (caught) {
      const detail = axios.isAxiosError(caught)
        ? caught.response?.data?.detail || caught.message
        : "알 수 없는 오류가 발생했습니다.";
      setPlan(null);
      setError(String(detail));
    }
  }

  async function executePlan() {
    if (!plan) return;
    try {
      setError("");
      const response = await axios.post(`${API_BASE}/agent/execute`, plan);
      setResult(response.data.message);
      setPlan(null);
      await refreshHistory();
    } catch (caught) {
      const detail = axios.isAxiosError(caught)
        ? caught.response?.data?.detail || caught.message
        : "알 수 없는 오류가 발생했습니다.";
      setError(String(detail));
    }
  }

  async function rollback(id: number) {
    try {
      setError("");
      const response = await axios.post(`${API_BASE}/agent/actions/${id}/rollback`);
      setResult(response.data.message);
      await refreshHistory();
    } catch (caught) {
      const detail = axios.isAxiosError(caught)
        ? caught.response?.data?.detail || caught.message
        : "알 수 없는 오류가 발생했습니다.";
      setError(String(detail));
    }
  }

  useEffect(() => {
    refreshHistory();
  }, []);

  return (
    <main>
      <header>
        <h1>Rollback-First Agent</h1>
        <p>작업 실행 전에 Rollback Plan을 먼저 생성하는 Todo & Schedule Agent</p>
      </header>

      <section className="panel">
        <label>자연어 명령</label>
        <textarea value={message} onChange={(event) => setMessage(event.target.value)} />
        <button onClick={createPlan}>계획 생성</button>
      </section>

      {plan && (
        <section>
          {plan.gate_result.gate_decision === "transform_to_safe_action" && (
            <p className="warning">
              복구 불가능한 작업이므로 안전한 대체 작업으로 변환되었습니다.
            </p>
          )}
          <div className="grid">
          <article className="panel">
            <h2>원래 실행 계획</h2>
            <p><strong>{plan.original_action.action_type}</strong></p>
            <p>{plan.original_action.description}</p>
            <pre>{JSON.stringify(plan.original_action.arguments, null, 2)}</pre>
          </article>
          <article className="panel">
            <h2>복구 가능성 평가</h2>
            <p><strong>{plan.rollback_plan.recovery_level}</strong></p>
            <p>rollback 가능: {String(plan.rollback_plan.rollback_available)}</p>
            <p>{plan.rollback_plan.reason}</p>
          </article>
          <article className="panel">
            <h2>Execution Gate</h2>
            <p><strong>{plan.gate_result.gate_decision}</strong></p>
            <p>{plan.gate_result.reason}</p>
          </article>
          <article className="panel">
            <h2>최종 실행 작업</h2>
            <p><strong>{plan.final_action.action_type}</strong></p>
            <p>{plan.final_action.description}</p>
            <pre>{JSON.stringify(plan.final_action.arguments, null, 2)}</pre>
          </article>
          <article className="panel">
            <h2>Rollback Plan</h2>
            <p><strong>{plan.rollback_plan.rollback_type}</strong></p>
            <p>{plan.rollback_plan.reason}</p>
            <pre>{JSON.stringify(plan.rollback_plan.rollback_arguments, null, 2)}</pre>
            <button
              disabled={plan.gate_result.gate_decision === "approval_required"}
              onClick={executePlan}
            >
              {plan.gate_result.gate_decision === "transform_to_safe_action"
                ? "대체 작업 실행"
                : "실행"}
            </button>
          </article>
          </div>
        </section>
      )}

      {result && <p className="result">{result}</p>}
      {error && <p className="error">{error}</p>}

      <section className="panel">
        <h2>실행 기록</h2>
        {history.map((item) => (
          <div className="history" key={item.id}>
            <div>
              <strong>#{item.id} {item.action_type}</strong>
              <p>{item.user_request}</p>
              <small>
                {(item.original_action_type || item.action_type)}
                {" -> "}
                {(item.final_action_type || item.action_type)}
                {" / "}
                {item.gate_decision || "execute"}
                {" / "}
                {item.recovery_level || "fully_reversible"}
                {" / "}
                {item.status}
              </small>
            </div>
            <button disabled={item.status === "rolled_back"} onClick={() => rollback(item.id)}>
              되돌리기
            </button>
          </div>
        ))}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
