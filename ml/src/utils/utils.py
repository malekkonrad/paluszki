# src/utils.py
import torch

@torch.no_grad()
def greedy_decode(model, frames, bos_id, eos_id, pad_id, max_len=40, device="cpu"):
    model.eval()
    frames = frames.unsqueeze(0).to(device)  # [1, T, C, H, W]

    generated = torch.tensor([[bos_id]], dtype=torch.long, device=device)

    for _ in range(max_len - 1):
        logits = model(frames, generated)      # [1, L, vocab]
        next_token = logits[:, -1, :].argmax(dim=-1, keepdim=True)
        generated = torch.cat([generated, next_token], dim=1)

        if next_token.item() == eos_id:
            break

    return generated.squeeze(0).tolist()