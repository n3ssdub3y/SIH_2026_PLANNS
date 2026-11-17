"""
NWIS-Sentinel | SIH 2026 | PS SIH26121
Module 5: agent behaviour tests (offline: no LLM is called).

Guards the regressions found in Nov 2026:
  - the offline answer ignored the question (same template for every question),
  - off-topic questions got drilling evidence with "Low to Medium" confidence,
  - Gemini was never tried when an HF token was configured but failing.
Run from NLP/nlp_task_ddr:  python -m pytest module5_engineering_agent/test_agent.py
"""
import shutil
import sys
from pathlib import Path

import pytest

_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))

from agent.question import analyse_question, focus_hazards  # noqa: E402
from agent.local_engine import wilson_ci  # noqa: E402
from schemas.models import AskRequest, CurrentSituation  # noqa: E402


# ── question analysis (pure) ──────────────────────────────────────────────────
@pytest.mark.parametrize("q,hazard", [
    ("What should I do about rising torque?", "torque_spike"),
    ("How much mud was typically lost before circulation was regained?", "mud_loss"),
    ("Pit gain after a drilling break, is this a kick?", "kick"),
    ("Pipe is stuck after tight hole, should we jar?", "stuck_pipe"),
    ("What happened during the cement job?", "cementing"),
])
def test_question_hazard_detection(q, hazard):
    assert hazard in analyse_question(q).hazards


def test_question_intents():
    info = analyse_question("What is the most common hazard in the next 300 m and its typical NPT?")
    assert {"frequency", "npt"} <= info.intents
    assert info.lookahead_m == 300
    # "typically" alone must not trigger hazard-frequency stats
    assert "frequency" not in analyse_question("How much mud was typically lost?").intents
    # "time lost" is NPT, not mud loss
    assert "mud_loss" not in analyse_question("How much time lost to NPT?").hazards


@pytest.mark.parametrize("q", ["What is the weather like today?", "tell me a joke", "hello",
                               "who won the cricket match"])
def test_off_topic_detected(q):
    assert not analyse_question(q).in_domain


def test_question_hazard_outranks_panel_hazard():
    info = analyse_question("How do I handle lost circulation?")
    assert focus_hazards(info, "stuck_pipe")[0] == "mud_loss"
    assert focus_hazards(analyse_question("kick?"), None) == ["kick", "overpressure"]


def test_wilson_ci_bounds():
    lo, hi = wilson_ci(11, 25)
    assert 0.25 < lo < 0.30 and 0.60 < hi < 0.66
    assert wilson_ci(0, 0) == (0.0, 0.0)


# ── end-to-end against the real event store, LLMs disabled ────────────────────
@pytest.fixture(scope="module")
def agent(tmp_path_factory):
    import config
    from retrieval import vector_store
    seed = Path(config.CHROMA_SEED_DIR)
    if not (seed / "chroma.sqlite3").exists():
        pytest.skip("Chroma seed not present")
    runtime = tmp_path_factory.mktemp("chroma") / "chroma"
    shutil.copytree(seed, runtime)
    orig = vector_store.ensure_runtime_store
    vector_store.ensure_runtime_store = lambda *a, **k: runtime
    try:
        from agent.agent import EngineeringAgent
        a = EngineeringAgent()
    finally:
        vector_store.ensure_runtime_store = orig
    a.hf_client = None
    a.gemini_client = None
    return a


SIT = CurrentSituation(well_id="15/9-F-9A", depth=2500, hazard="stuck_pipe")


def test_different_questions_get_different_answers(agent):
    qs = ["What should I do about rising torque?",
          "How much mud was typically lost before circulation was regained?",
          "What kill mud weights were used after gas influx?"]
    resps = [agent.ask(AskRequest(question=q, current_situation=SIT)) for q in qs]
    assert all(r.engine == "local-evidence-engine" for r in resps)
    assert len({r.answer.split("\n")[0] for r in resps}) == 3          # different headings
    assert len({tuple(r.citations[:3]) for r in resps}) == 3           # different evidence
    assert "Torque Spike" in resps[0].answer
    assert "Volume lost per event" in resps[1].answer
    assert "Kill mud weights used" in resps[2].answer


def test_evidence_matches_question_hazard_not_panel(agent):
    r = agent.ask(AskRequest(question="How do I handle lost circulation?", current_situation=SIT))
    assert sum(e.hazard == "mud_loss" for e in r.evidence) >= 5


def test_off_topic_question_is_rejected(agent):
    r = agent.ask(AskRequest(question="What is the weather like today?", current_situation=SIT))
    assert r.engine == "scope-check"
    assert r.evidence == [] and r.uncertainty.startswith("N/A")


def test_probability_is_a_labelled_base_rate(agent):
    r = agent.ask(AskRequest(question="What is the probability this escalates into stuck pipe?",
                             current_situation=SIT))
    assert "Wilson 95% CI" in r.answer and "not a calibrated escalation probability" in r.answer


def test_gemini_tried_after_hf_fails(agent, monkeypatch):
    calls = []

    class _HF:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    calls.append("hf")
                    raise RuntimeError("Client error '402 Payment Required' for url 'https://router'")

    class _Resp:
        text = "Answer: from gemini"

    class _Models:
        @staticmethod
        def generate_content(model, **kw):
            calls.append(model)
            if len(calls) == 2:
                raise RuntimeError("503 UNAVAILABLE. high demand")
            return _Resp()

    class _Gemini:
        models = _Models

    monkeypatch.setattr(agent, "hf_client", _HF)
    monkeypatch.setattr(agent, "gemini_client", _Gemini)
    monkeypatch.setattr(agent, "_hf_disabled", None)
    r = agent.ask(AskRequest(question="What should I do about rising torque?", current_situation=SIT))
    assert r.answer == "Answer: from gemini"
    assert r.engine.startswith("Gemini (")
    assert calls[0] == "hf" and len(calls) == 3        # HF -> first Gemini model (503) -> second
    assert agent._hf_disabled                         # 402 is permanent: HF skipped from now on


# ── explicit provider choice (UI "Answer with" picker) ────────────────────────
def _stub_providers(monkeypatch, agent, hf_ok: bool, calls: list):
    class _Msg:
        content = "Answer: from qwen"

    class _Choice:
        message = _Msg

    class _ChatResp:
        choices = [_Choice]

    class _HF:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    calls.append("hf")
                    if not hf_ok:
                        raise RuntimeError("402 Payment Required")
                    return _ChatResp

    class _Resp:
        text = "Answer: from gemini"

    class _Gemini:
        class models:
            @staticmethod
            def generate_content(model, **kw):
                calls.append("gemini")
                return _Resp

    monkeypatch.setattr(agent, "hf_client", _HF)
    monkeypatch.setattr(agent, "gemini_client", _Gemini)
    monkeypatch.setattr(agent, "_hf_disabled", None)
    monkeypatch.setattr(agent, "_gemini_disabled", None)
    monkeypatch.setattr(agent, "refresh_keys", lambda: None)


@pytest.mark.parametrize("provider,expect_engine,expect_calls", [
    ("gemini", "Gemini (", ["gemini"]),          # HF never called
    ("qwen", "Qwen (", ["hf"]),
    ("local", "local-evidence-engine", []),      # no LLM call at all
    ("auto", "Qwen (", ["hf"]),
])
def test_provider_choice_routes_to_that_provider(agent, monkeypatch, provider, expect_engine, expect_calls):
    calls = []
    _stub_providers(monkeypatch, agent, hf_ok=True, calls=calls)
    r = agent.ask(AskRequest(question="What should I do about rising torque?", current_situation=SIT,
                             provider=provider))
    assert r.engine.startswith(expect_engine)
    assert calls == expect_calls
    assert "[System Notice]" not in r.answer


def test_chosen_provider_failing_falls_back_to_local_not_other_llm(agent, monkeypatch):
    calls = []
    _stub_providers(monkeypatch, agent, hf_ok=False, calls=calls)
    r = agent.ask(AskRequest(question="What should I do about rising torque?", current_situation=SIT,
                             provider="qwen"))
    assert calls == ["hf"]                                   # Gemini not silently substituted
    assert r.engine == "local-evidence-engine"
    assert "Qwen (Hugging Face) was selected but failed" in r.answer
    # an explicit choice retries even after the 402 disabled HF for auto mode
    calls.clear()
    agent.ask(AskRequest(question="rising torque?", current_situation=SIT, provider="qwen"))
    assert calls == ["hf"]


def test_new_token_in_env_rebuilds_client(agent, monkeypatch):
    import agent.agent as agent_mod
    built = []
    monkeypatch.setattr(agent, "_hf_disabled", "402 Payment Required")
    monkeypatch.setattr(agent, "_set_hf_token", lambda tok: built.append(tok))
    monkeypatch.setattr(agent_mod, "_read_env_keys",
                        lambda: {"HF_TOKEN": "hf_brand_new", "GEMINI_API_KEY": agent._gemini_key})
    agent.refresh_keys()
    assert built == ["hf_brand_new"]
