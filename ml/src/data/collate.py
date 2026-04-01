import torch


def collate_fn(batch):
    frames = torch.stack([item["frames"] for item in batch])
    tokens = torch.stack([item["tokens"] for item in batch])

    return {
        "frames": frames,
        "tokens": tokens,
        "texts": [item["text"] for item in batch],
        "video_names": [item["video_name"] for item in batch],
    }


def classification_collate_fn(batch):
    frames = torch.stack([item["frames"] for item in batch])
    labels = torch.tensor([item["label"] for item in batch], dtype=torch.long)

    return {
        "frames": frames,
        "labels": labels,
        "glosses": [item["gloss"] for item in batch],
        "video_ids": [item["video_id"] for item in batch],
    }