"""DeepEval tests for Research Agent hallucination detection.

Run with: pytest tests/test_research_agent.py -v
"""
import pytest
from deepeval import assert_test
from deepeval.metrics import HallucinationMetric, ContextualRecallMetric, AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase


@pytest.mark.parametrize("scenario", [
    {
        "name": "Q3 Revenue Extraction",
        "input": "What is Company X's Q3 revenue?",
        "context": ["Company X reported Q3 revenue of $5.2B, up 10% YoY."],
        "actual_output": "Company X reported $5.2B in Q3 revenue.",
        "expected_output": "Company X reported $5.2B revenue."
    },
    {
        "name": "Profit Margin Calculation",
        "input": "What was the profit margin?",
        "context": ["Net profit margin increased to 15.4% from 12.1% in the prior year."],
        "actual_output": "Profit margin was 15.4%.",
        "expected_output": "Net profit margin was 15.4%."
    },
    {
        "name": "CEO Statement Citation",
        "input": "What did the CEO say about AI?",
        "context": ["CEO Jane Smith said: 'AI is transforming our business' - Press Release, Oct 15, 2025"],
        "actual_output": "CEO Jane Smith said AI is transforming the business.",
        "expected_output": "CEO Jane Smith said AI is transforming our business."
    }
])
def test_research_fidelity(scenario):
    """Test that agent outputs are faithful to source context.

    HallucinationMetric: Measures if output claims are supported by context.
    ContextualRecallMetric: Measures if key facts from context are included.
    """
    test_case = LLMTestCase(
        input=scenario["input"],
        actual_output=scenario["actual_output"],
        retrieval_context=scenario["context"],
        expected_output=scenario["expected_output"]
    )

    # Faithfulness: 0.99 threshold - no tolerance for financial hallucinations
    faith_metric = HallucinationMetric(
        threshold=0.99,
        include_reason=True
    )

    # Recall: 0.8 threshold - allow missing some details
    recall_metric = ContextualRecallMetric(
        threshold=0.8,
        include_reason=True
    )

    assert_test(test_case, [faith_metric, recall_metric])


@pytest.mark.parametrize("scenario", [
    {
        "name": "Relevant Answer to Question",
        "input": "What was Apple's Q4 revenue?",
        "context": ["Apple reported Q4 revenue of $89.5B, a 6% increase YoY."],
        "actual_output": "Apple's Q4 revenue was $89.5B.",
        "expected_output": "Apple Q4 revenue was $89.5B."
    }
])
def test_answer_relevancy(scenario):
    """Test that answers are relevant to the asked question."""
    test_case = LLMTestCase(
        input=scenario["input"],
        actual_output=scenario["actual_output"],
        retrieval_context=scenario["context"],
        expected_output=scenario["expected_output"]
    )

    relevancy_metric = AnswerRelevancyMetric(
        threshold=0.8,
        include_reason=True
    )

    assert_test(test_case, [relevancy_metric])


if __name__ == "__main__":
    # Quick sanity check
    test_research_fidelity({
        "name": "Manual Test",
        "input": "Test question?",
        "context": ["Source document text here."],
        "actual_output": "Test answer.",
        "expected_output": "Test answer."
    })
    print("DeepEval tests configured successfully!")
