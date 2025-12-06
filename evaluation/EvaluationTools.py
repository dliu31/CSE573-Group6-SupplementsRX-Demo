from deepeval import assert_test
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.metrics import GEval, AnswerRelevancyMetric, FaithfulnessMetric, ContextualPrecisionMetric, ContextualRecallMetric, ContextualRelevancyMetric, TaskCompletionMetric, KnowledgeRetentionMetric, TopicAdherenceMetric
from deepeval.evaluate import evaluate
from deepeval.tracing import observe
from deepeval.dataset import dataset, Golden
from GeminiAgent import GoogleVertexAI

class Evaluator():
    def __init__(self):
        self.test_cases = {
            'answer_relevancy': [],
            'faithfulness': [],
            'contextual_precision': [],
            'contextual_recall': [],
            'contextual_relevancy': [],
            'task_completeness': [],
            'conversation_completeness': [],
            'topic_adherence': [],
        }
        self.model = GoogleVertexAI()
        
        correctness_metric = GEval(
            name="Correctness",
            criteria="Determine whether the actual output is factually correct based on the expected output.",
            model=self.model,
            threshold=0.7,
            evaluation_steps=[
                "Check whether the facts in 'actual output' contradicts any facts in 'expected output'",
                "If the 'actual output' acknowledges that it doesn't know, it should recommend the user to see a medical professional, but still penalize the score",
                "It is fine if it doesn't include every detail",
                "Vague language is OK"
            ],
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
        )
        
        intent_metric = GEval(
            name="User Intent",
            model=self.model,
            threshold=0.7,
            evaluation_steps=[
                "Determine whether the model correctly identifies the user's intent in a medical context.",
                "Check whether the model's interpretation accurately reflects all medically relevant details in the user's input.",
                "Penalize the output if it attempts to answer the user’s medical question instead of describing the intent.",
                "Penalize the output if it introduces medical facts or advice not present in the user's input.",
                "Penalize the output for adding non-medical or irrelevant information not connected to identifying intent.",
                "Vague phrasing is acceptable as long as the intent is correctly captured.",
            ],
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        )
        
        # How relevant the output is to the input
        self.answer_relevancy = AnswerRelevancyMetric(threshold=0.7, model=self.model, include_reason=True)
        # Evaluates whether the output aligns with the retrieval context. (Not hallucination)
        self.answer_faithfulness = FaithfulnessMetric(threshold=0.7, model=self.model, include_reason=True)
        # Evaluates whether nodes in the retrieval context relevant to the input are ranked higher than non-relevant ones
        self.contextual_precision = ContextualPrecisionMetric(threshold=0.7, model=self.model, include_reason=True)
        # Evaluates the extent to which the retrieval context aligns with the expected output
        self.contextual_recall = ContextualRecallMetric(threshold=0.7, model=self.model, include_reason=True)
        # Evaluates the relevance of the retrieval context with regards to the input
        self.contextual_relevancy = ContextualRelevancyMetric(threshold=0.7, model=self.model, include_reason=True)
        # Evaluates how well the model retains information of the conversation
        self.knowledge_retention = KnowledgeRetentionMetric(threshold=0.7, model=self.model, include_reason=True)
        # Evaluates how well it determined the user's intent based on their query
        self.intent_metric = intent_metric
        # Evaluates how correct the answer is
        self.correctness_metric = correctness_metric