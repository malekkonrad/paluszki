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