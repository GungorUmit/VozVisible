# -*- coding: utf-8 -*-
"""
Created on Sat May 16 15:58:20 2026

@author: Alonso
"""

import argparse
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split

def prepare_splits(metadata_csv, wavs_dir, out_dir, wav_column='filename', text_column='transcription', random_state=42):
    metadata = pd.read_csv(metadata_csv)
    
    if wav_column not in metadata.columns or text_column not in metadata.columns:
        raise ValueError(f"CSV must contain columns '{wav_column}' and '{text_column}'")
    
    # Create full path column (adjust to make relative if you prefer)
    wavs_dir = Path(wavs_dir)
    metadata['wav_path'] = metadata[wav_column].apply(lambda fn: str((wavs_dir / (fn + ".wav")).resolve()))
    
    # Optionally filter missing files
    exists_mask = metadata['wav_path'].apply(lambda p: Path(p).exists())
    if not exists_mask.all():
        missing = metadata.loc[~exists_mask, wav_column].tolist()
        print(f"Warning: {len(missing)} files listed in CSV not found in {wavs_dir}. They will be dropped.")
        metadata = metadata.loc[exists_mask].reset_index(drop=True)
    
    # Keep only required columns in output
    df = metadata[['wav_path', text_column]].rename(columns={text_column: 'transcription'})
    
    # First split: train (80%) and rest (20%)
    train_df, rest_df = train_test_split(df, train_size=0.8, random_state=random_state, shuffle=True)
    
    # Second split: validation (10%) and test (10%) — split rest in half
    val_df, test_df = train_test_split(rest_df, test_size=0.5, random_state=random_state, shuffle=True)
    
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    train_df.to_csv(out_dir / 'train.csv', index=False)
    val_df.to_csv(out_dir / 'val.csv', index=False)
    test_df.to_csv(out_dir / 'test.csv', index=False)
    
    print(f"Wrote: {len(train_df)} train, {len(val_df)} validation, {len(test_df)} test rows to {out_dir}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Split wav metadata CSV into train/validation/test CSVs (80/10/10).')
    parser.add_argument('--metadata', required=True, help='Input CSV with at least columns: filename, transcription')
    parser.add_argument('--wavs_dir', required=True, help='Directory where .wav files are stored')
    parser.add_argument('--out_dir', default='csv_output', help='Output directory for train/validation/test CSVs')
    parser.add_argument('--wav_column', default='file_name', help='Column name in metadata CSV for wav filenames')
    parser.add_argument('--text_column', default='transcription', help='Column name in metadata CSV for transcriptions')
    parser.add_argument('--random_state', type=int, default=42, help='Random seed for reproducible splits')
    args = parser.parse_args()
    prepare_splits(args.metadata, args.wavs_dir, args.out_dir, args.wav_column, args.text_column, args.random_state)