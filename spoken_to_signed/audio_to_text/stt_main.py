 # -*- coding: utf-8 -*-
"""
Created on Sat May  9 10:56:44 2026

@author: Alonso
"""

from transformers import (WhisperProcessor, Seq2SeqTrainingArguments, 
                          WhisperForConditionalGeneration, Seq2SeqTrainer)

import librosa, torch, evaluate
 
import numpy as np

from datasets import load_dataset, Features, Value

from dataclasses import dataclass

from typing import Any, Dict, List, Union

##################################################

sampling_rate = 16000 # Target audio sampling rate


##### Choose model to use #######################
model_name = "openai/whisper-small"
model = WhisperForConditionalGeneration.from_pretrained(model_name)
processor = WhisperProcessor.from_pretrained(model_name)
tokenizer = processor.tokenizer 
#################################################
 
##### Configure model to operate in Spanish #####
forced_decoder_ids = processor.get_decoder_prompt_ids(language="spanish", task="transcribe")
model.config.forced_decoder_ids = forced_decoder_ids
model.config.suppress_tokens = []
#################################################

# Metrics function (optional)
wer_metric = evaluate.load("wer")

# Custom data collator needed to make the thing work, given by Perplexity
@dataclass
class DataCollatorSpeechSeq2SeqWithPadding:
    processor: Any

    def __call__(self, features: List[Dict[str, Union[List[int], torch.Tensor]]]) -> Dict[str, torch.Tensor]:
        input_features = [{"input_features": feature["input_features"]} for feature in features]
        batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")

        label_features = [{"input_ids": feature["labels"]} for feature in features]
        labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")

        labels = labels_batch["input_ids"].masked_fill(labels_batch.attention_mask.ne(1), -100)

        if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all().item():
            labels = labels[:, 1:]

        batch["labels"] = labels
        return batch
##################################################

##### Data preprocessing auxiliary function ######
    
def process(example):
    audio_path = example["path"]
    audio_array, sr = librosa.load(audio_path, sr=16000)  # Resample to 16kHz
    
    # Use processor for mel spectrogram
    inputs = processor(audio_array, sampling_rate=16000, return_tensors="pt")
    mel = inputs.input_features[0]  # Shape: [80, 3000]
        
    # Tokenize transcription
    labels = processor.tokenizer(example["transcription"], return_tensors="pt").input_ids[0]
    
    return {"input_features": mel, "labels": labels}

#################################################

##### Model metrics auxiliary functions #########
wer_metric = evaluate.load("wer")

def compute_metrics(pred):
    pred_ids = pred.predictions
    label_ids = pred.label_ids
    # Replace -100 with pad_token_id
    label_ids[label_ids == -100] = processor.tokenizer.pad_token_id
    # Decode
    pred_str = processor.batch_decode(pred_ids, skip_special_tokens=True)
    label_str = processor.batch_decode(label_ids, skip_special_tokens=True)
    wer = 100 * wer_metric.compute(predictions=pred_str, references=label_str)
    return {"wer": wer}
#################################################


def finetune_training():

    ##### Load the datasets #########################
    
    # Load datasets 
    
    # Define features ON LOAD - this bypasses cast_column entirely
    features = Features({
        "path": Value("string"),           
        "transcription": Value("string")   
    })
    
    # Load CSV with simple string features first
    train_dataset = load_dataset("csv", data_files="csv_output/train.csv", features=features)["train"]
    val_dataset = load_dataset("csv", data_files="csv_output/val.csv", features=features)["train"]
    
    print("Data loading done!")
    #################################################
    
    
    
    ##### Data processing ###########################
    train_dataset = train_dataset.map(process, remove_columns=train_dataset.column_names)
    val_dataset = val_dataset.map(process, remove_columns=val_dataset.column_names)
    #################################################
    
    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)
    
    # Training arguments for the model ##############
    # For CPU training, use fp16=False to avoid slowing down the training too much, 
    # and reduce batch size to match the available RAM. For GPU training, fp16=True 
    # normally works fine and fast, but the batch size should similarly be adjusted
    # to match the available VRAM.
    training_args = Seq2SeqTrainingArguments(
        output_dir="./whisper-finetuned",
    
        num_train_epochs=3,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,   # effective batch size = 8
        learning_rate=1e-5,
        warmup_steps=100,
        fp16=True,
    
        eval_strategy="epoch",
        predict_with_generate=True,
        generation_max_length=225,
    
        logging_steps=25,
        save_steps=500,
        save_total_limit=2,
        report_to="tensorboard",
    
        dataloader_drop_last=True,
        remove_unused_columns=False,
    
        gradient_checkpointing=True,
    )
    #################################################
    
    ###### Train the model ##########################
    print("Starting model finetuning!")
    
    model = WhisperForConditionalGeneration.from_pretrained(model_name)
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []
    model.config.use_cache = False  # Recommended during training
    
    # Set data collator's model reference
    data_collator.model = model
       
    
    rows = len(train_dataset)
    cols = len(train_dataset.column_names)
    print(train_dataset.column_names)
    print((rows, cols))
    print(np.array(train_dataset["input_features"][0]).shape)
    
    batch = data_collator([train_dataset[0], train_dataset[1]])
    print(batch["input_features"].shape)
    
    # Initialize trainer
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        processing_class=processor,
    )
    
    # Launch training!
    trainer.train()
    trainer.save_model("whisper-es-finetuned")
    processor.save_pretrained("whisper-es-finetuned")
    #################################################
    
