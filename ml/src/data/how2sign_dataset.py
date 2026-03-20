from pathlib import Path

import cv2
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
import torchvision.transforms as T


class How2SignDataset(Dataset):
    def __init__(
        self,
        csv_path,
        video_dir,
        tokenizer,
        video_column="video_name",
        text_column="text",
        num_frames=16,
        image_size=224,
        max_text_len=40,
        csv_separator=",",
    ):
        self.df = pd.read_csv(csv_path, sep=csv_separator)
        self.video_dir = Path(video_dir)
        self.tokenizer = tokenizer
        self.video_column = video_column
        self.text_column = text_column
        self.num_frames = num_frames
        self.image_size = image_size
        self.max_text_len = max_text_len

        self.transform = T.Compose([
            T.Resize((image_size, image_size)),
            T.ToTensor(),
        ])

    def __len__(self):
        return len(self.df)

    def _sample_frames(self, video_path):
        cap = cv2.VideoCapture(str(video_path))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if total_frames <= 0:
            cap.release()
            return torch.zeros(self.num_frames, 3, self.image_size, self.image_size)

        indices = torch.linspace(0, max(total_frames - 1, 0), steps=self.num_frames).long().tolist()
        target_set = set(indices)

        frames = []
        frame_id = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_id in target_set:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = Image.fromarray(frame)
                image = self.transform(image)
                frames.append(image)

                if len(frames) == self.num_frames:
                    break

            frame_id += 1

        cap.release()

        while len(frames) < self.num_frames:
            if frames:
                frames.append(frames[-1].clone())
            else:
                frames.append(torch.zeros(3, self.image_size, self.image_size))

        return torch.stack(frames)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]

        video_name = str(row[self.video_column])
        text = row[self.text_column]

        video_file = video_name if Path(video_name).suffix else f"{video_name}.mp4"
        video_path = self.video_dir / video_file
        frames = self._sample_frames(video_path)
        tokens = self.tokenizer.encode(text, max_len=self.max_text_len)

        return {
            "frames": frames,
            "tokens": tokens,
            "text": text,
            "video_name": video_name,
        }
