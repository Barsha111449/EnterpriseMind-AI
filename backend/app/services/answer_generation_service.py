from functools import lru_cache

import torch
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
)

from backend.app.services.rag_service import (
    build_grounding_instruction,
)


MODEL_NAME = "google/flan-t5-small"

MAX_INPUT_TOKENS = 512
MAX_NEW_TOKENS = 180

NO_EVIDENCE_ANSWER = (
    "The available documents do not provide enough "
    "evidence to answer this question."
)


@lru_cache(maxsize=1)
def get_answer_tokenizer():
    """Load and reuse the answer-generation tokenizer."""

    return AutoTokenizer.from_pretrained(
        MODEL_NAME,
        use_fast=True,
    )


@lru_cache(maxsize=1)
def get_answer_model():
    """Load and reuse the local answer-generation model."""

    model = AutoModelForSeq2SeqLM.from_pretrained(
        MODEL_NAME
    )

    model.eval()

    return model


def build_answer_prompt(
    question: str,
    context: str,
) -> str:
    """Build a prompt grounded in document evidence."""

    question_text = question.strip()
    context_text = context.strip()

    if not question_text:
        raise ValueError(
            "The question cannot be empty."
        )

    if not context_text:
        return ""

    grounding_instruction = (
        build_grounding_instruction()
    )

    return "\n\n".join(
        [
            grounding_instruction,
            f"Question: {question_text}",
            "Sources:",
            context_text,
            (
                "Write a concise answer using citation "
                "markers such as [1] and [2]."
            ),
            "Answer:",
        ]
    )


def generate_grounded_answer(
    question: str,
    context: str,
) -> str:
    """Generate an answer using only supplied evidence."""

    prompt = build_answer_prompt(
        question=question,
        context=context,
    )

    if not prompt:
        return NO_EVIDENCE_ANSWER

    tokenizer = get_answer_tokenizer()
    model = get_answer_model()

    model_inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_INPUT_TOKENS,
    )

    with torch.inference_mode():
        generated_tokens = model.generate(
            **model_inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
            num_beams=4,
            early_stopping=True,
        )

    generated_answer = tokenizer.decode(
        generated_tokens[0],
        skip_special_tokens=True,
    ).strip()

    if not generated_answer:
        return NO_EVIDENCE_ANSWER

    return generated_answer