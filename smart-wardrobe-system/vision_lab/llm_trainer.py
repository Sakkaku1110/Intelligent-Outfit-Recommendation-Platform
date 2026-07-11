#!/usr/bin/env python3
"""LoRA training entrypoint for the smart-wardrobe outfit LLM.

This module is intentionally offline-only. It is meant to run on a PC or GPU
training machine, not on the SS928 board service.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from dataclasses import dataclass
from typing import Any, Dict, Optional

from llm_training import SYSTEM_PROMPT, validate_jsonl, write_json


@dataclass
class LoraTrainingConfig:
    mode: str
    train_file: pathlib.Path
    output_dir: pathlib.Path
    base_model: str
    validation_file: Optional[pathlib.Path] = None
    epochs: float = 3.0
    learning_rate: float = 2e-5
    batch_size: int = 1
    gradient_accumulation_steps: int = 8
    max_seq_length: int = 2048
    max_prompt_length: int = 1024
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    warmup_ratio: float = 0.03
    logging_steps: int = 10
    save_steps: int = 200
    load_in_4bit: bool = False
    bf16: bool = False
    fp16: bool = False
    seed: int = 42
    dry_run: bool = False


def validate_training_file(path: pathlib.Path, mode: str) -> int:
    count = validate_jsonl(path)
    if count <= 0:
        raise ValueError("training file has no examples: %s" % path)
    with path.open("r", encoding="utf-8") as handle:
        first = json.loads(next(line for line in handle if line.strip()))
    if mode == "sft" and "messages" not in first:
        raise ValueError("SFT file must contain chat rows with a messages field")
    if mode == "dpo" and not {"prompt", "chosen", "rejected"}.issubset(first):
        raise ValueError("DPO file must contain prompt, chosen, and rejected fields")
    return count


def run_lora_training(config: LoraTrainingConfig) -> Dict[str, Any]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    train_examples = validate_training_file(config.train_file, config.mode)
    validation_examples = (
        validate_training_file(config.validation_file, config.mode) if config.validation_file else 0
    )
    training_plan = {
        "mode": config.mode,
        "base_model": config.base_model,
        "train_file": str(config.train_file),
        "validation_file": str(config.validation_file) if config.validation_file else "",
        "output_dir": str(config.output_dir),
        "train_examples": train_examples,
        "validation_examples": validation_examples,
        "hyperparameters": {
            "epochs": config.epochs,
            "learning_rate": config.learning_rate,
            "batch_size": config.batch_size,
            "gradient_accumulation_steps": config.gradient_accumulation_steps,
            "max_seq_length": config.max_seq_length,
            "max_prompt_length": config.max_prompt_length,
            "lora_rank": config.lora_rank,
            "lora_alpha": config.lora_alpha,
            "lora_dropout": config.lora_dropout,
            "load_in_4bit": config.load_in_4bit,
            "bf16": config.bf16,
            "fp16": config.fp16,
            "seed": config.seed,
        },
        "dry_run": config.dry_run,
    }
    write_json(config.output_dir / "training_plan.json", training_plan)
    if config.dry_run:
        return {**training_plan, "training_started": False, "reason": "dry_run"}

    try:
        import torch  # type: ignore
        from datasets import load_dataset  # type: ignore
        from peft import LoraConfig  # type: ignore
        from transformers import (  # type: ignore
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            TrainingArguments,
        )
        from trl import DPOTrainer, SFTTrainer  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "Missing LLM training dependency: %s\n"
            "Install dependencies with: pip install -r smart-wardrobe-system/vision_lab/llm_requirements.txt"
            % exc
        )

    tokenizer = AutoTokenizer.from_pretrained(config.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    quantization_config = None
    if config.load_in_4bit:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16 if config.bf16 else torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
    model = AutoModelForCausalLM.from_pretrained(
        config.base_model,
        trust_remote_code=True,
        device_map="auto",
        quantization_config=quantization_config,
    )
    model.config.use_cache = False
    peft_config = LoraConfig(
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules="all-linear",
    )
    data_files: Dict[str, str] = {"train": str(config.train_file)}
    if config.validation_file:
        data_files["validation"] = str(config.validation_file)
    dataset = load_dataset("json", data_files=data_files)
    train_dataset = dataset["train"]
    eval_dataset = dataset.get("validation")
    training_args = TrainingArguments(
        output_dir=str(config.output_dir),
        num_train_epochs=config.epochs,
        learning_rate=config.learning_rate,
        per_device_train_batch_size=config.batch_size,
        per_device_eval_batch_size=config.batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        warmup_ratio=config.warmup_ratio,
        logging_steps=config.logging_steps,
        save_steps=config.save_steps,
        save_total_limit=3,
        evaluation_strategy="steps" if eval_dataset is not None else "no",
        eval_steps=config.save_steps if eval_dataset is not None else None,
        bf16=config.bf16,
        fp16=config.fp16,
        report_to="none",
        seed=config.seed,
    )
    if config.mode == "sft":
        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            peft_config=peft_config,
            max_seq_length=config.max_seq_length,
            formatting_func=_format_sft_row(tokenizer),
        )
    elif config.mode == "dpo":
        trainer = DPOTrainer(
            model=model,
            ref_model=None,
            tokenizer=tokenizer,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            peft_config=peft_config,
            max_length=config.max_seq_length,
            max_prompt_length=config.max_prompt_length,
        )
    else:
        raise ValueError("mode must be sft or dpo")
    trainer.train()
    trainer.save_model(str(config.output_dir))
    tokenizer.save_pretrained(str(config.output_dir))
    result = {**training_plan, "training_started": True, "adapter_dir": str(config.output_dir)}
    write_json(config.output_dir / "training_result.json", result)
    return result


def _format_sft_row(tokenizer: Any):
    def format_row(row: Dict[str, Any]) -> str:
        messages = row.get("messages") or []
        if hasattr(tokenizer, "apply_chat_template") and getattr(tokenizer, "chat_template", None):
            return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        parts = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            parts.append("[%s]\n%s" % (role, content))
        return "\n\n".join(parts)

    return format_row


def parse_args() -> LoraTrainingConfig:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["sft", "dpo"], required=True)
    parser.add_argument("--train-file", required=True)
    parser.add_argument("--validation-file", default="")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--max-prompt-length", type=int, default=1024)
    parser.add_argument("--lora-rank", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument("--save-steps", type=int, default=200)
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--bf16", action="store_true")
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return LoraTrainingConfig(
        mode=args.mode,
        train_file=pathlib.Path(args.train_file),
        validation_file=pathlib.Path(args.validation_file) if args.validation_file else None,
        output_dir=pathlib.Path(args.output_dir),
        base_model=args.base_model,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        max_seq_length=args.max_seq_length,
        max_prompt_length=args.max_prompt_length,
        lora_rank=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        warmup_ratio=args.warmup_ratio,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        load_in_4bit=args.load_in_4bit,
        bf16=args.bf16,
        fp16=args.fp16,
        seed=args.seed,
        dry_run=args.dry_run,
    )


def main() -> int:
    result = run_lora_training(parse_args())
    print("mode=%s" % result["mode"])
    print("train_examples=%s" % result["train_examples"])
    print("output_dir=%s" % result["output_dir"])
    print("training_started=%s" % str(result["training_started"]).lower())
    if result.get("reason"):
        print("reason=%s" % result["reason"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
